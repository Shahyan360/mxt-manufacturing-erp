from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user
from psycopg2.errors import UniqueViolation


@tagged('post_install', '-at_install')
class TestManufacturingLab(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.buyer = new_test_user(cls.env, login='mxt_test_buyer',
                                 groups='base.group_user,mxt_operations.group_procurement_user')
        cls.manager = new_test_user(cls.env, login='mxt_test_manager',
                                   groups='base.group_user,mxt_operations.group_procurement_manager')
        cls.final = new_test_user(cls.env, login='mxt_test_final',
                                 groups='base.group_user,mxt_operations.group_final_approver')
        cls.operator = new_test_user(cls.env, login='mxt_test_operator',
                                    groups='base.group_user,mxt_operations.group_manufacturing_operator')
        cls.reviewer = new_test_user(cls.env, login='mxt_test_reviewer',
                                    groups='base.group_user,mxt_operations.group_quality_reviewer')
        cls.planner = new_test_user(cls.env, login='mxt_test_planner',
                                   groups='base.group_user,mxt_operations.group_planning_manager')
        cls.vendor = cls.env['res.partner'].create({'name': 'Test Fictional Supplier'})
        cls.customer = cls.env['res.partner'].create({'name': 'Test Fictional Customer'})
        cls.supply = cls.env['stock.warehouse'].create({'name': 'Test Supply', 'code': 'TSP', 'company_id': cls.company.id})
        cls.production = cls.env['stock.warehouse'].create({
            'name': 'Test Production', 'code': 'TMP', 'company_id': cls.company.id,
            'resupply_wh_ids': [Command.link(cls.supply.id)],
        })
        cls.panel = cls.env['product.product'].create({'name': 'Test Panel', 'type': 'product', 'mxt_safety_stock': 2})
        cls.pack = cls.env['product.product'].create({'name': 'Test Fastener', 'type': 'product'})
        cls.finished = cls.env['product.product'].create({
            'name': 'Test Cabinet', 'type': 'product',
            'route_ids': [Command.set([cls.env.ref('stock.route_warehouse0_mto').id,
                                       cls.env.ref('mrp.route_warehouse0_manufacture').id])],
        })
        cls.env.ref('stock.route_warehouse0_mto').active = True
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.finished.product_tmpl_id.id,
            'product_id': cls.finished.id, 'product_qty': 1,
            'product_uom_id': cls.finished.uom_id.id,
            'bom_line_ids': [
                Command.create({'product_id': cls.panel.id, 'product_qty': 2}),
                Command.create({'product_id': cls.pack.id, 'product_qty': 1}),
            ],
        })
        for product, price in [(cls.panel, 20), (cls.pack, 5)]:
            cls.env['product.supplierinfo'].create({
                'partner_id': cls.vendor.id, 'product_tmpl_id': product.product_tmpl_id.id,
                'price': price, 'delay': 2, 'company_id': cls.company.id,
            })

    def _mo(self, quantity=3):
        mo = self.env['mrp.production'].create({
            'product_id': self.finished.id, 'product_qty': quantity,
            'product_uom_id': self.finished.uom_id.id, 'bom_id': self.bom.id,
            'picking_type_id': self.production.manu_type_id.id,
            'location_src_id': self.production.lot_stock_id.id,
            'location_dest_id': self.production.lot_stock_id.id,
        })
        mo.action_confirm()
        return mo

    def _policy(self, product=None, route=None, safety=0, maximum=0):
        return self.env['mxt.planning.policy'].create({
            'name': 'Test requirement', 'product_id': (product or self.pack).id,
            'warehouse_id': self.production.id,
            'route_id': (route or self.env.ref('purchase_stock.route_warehouse0_buy')).id,
            'min_qty': 0, 'max_qty': maximum, 'safety_qty': safety,
        })

    def _po(self, amount=100):
        return self.env['purchase.order'].with_user(self.buyer).create({
            'partner_id': self.vendor.id,
            'picking_type_id': self.production.in_type_id.id,
            'order_line': [Command.create({'product_id': self.pack.id, 'product_qty': 1,
                                           'price_unit': amount, 'taxes_id': [Command.clear()]})],
        })

    def _approve(self, po):
        po.with_user(self.buyer).action_mxt_submit()
        po.with_user(self.manager).action_mxt_manager_approve()
        if po.mxt_needs_final:
            po.with_user(self.final).action_mxt_final_approve()
        po.with_user(self.buyer).button_confirm()

    def _receive(self, picking):
        picking.action_assign()
        for move in picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            move.quantity = move.product_uom_qty
            move.picked = True
        return picking.with_context(skip_backorder=True).button_validate()

    def _stages_to_quality(self, mo):
        mo.action_mxt_material_review()
        mo.action_mxt_material_ready()
        mo.action_mxt_start()
        mo.action_mxt_inspect()

    def test_bom_component_requirements(self):
        mo = self._mo()
        self.assertEqual(mo.move_raw_ids.filtered(lambda m: m.product_id == self.panel).product_uom_qty, 6)
        self.assertEqual(mo.move_raw_ids.filtered(lambda m: m.product_id == self.pack).product_uom_qty, 3)

    def test_buy_shortage_and_scheduler_idempotency(self):
        self._mo()
        policy = self._policy(safety=1, maximum=2)
        policy.with_user(self.planner).action_evaluate()
        lines = self.env['purchase.order.line'].search([('orderpoint_id', '=', policy.orderpoint_id.id)])
        self.assertEqual(sum(lines.mapped('product_qty')), 6)
        original_ids = lines.ids
        policy.with_user(self.planner).action_evaluate()
        self.assertEqual(self.env['purchase.order.line'].search([('orderpoint_id', '=', policy.orderpoint_id.id)]).ids, original_ids)
        self.assertEqual(sum(lines.mapped('product_qty')), 6)

    def test_existing_confirmed_supply_is_counted(self):
        self._mo()
        po = self._po()
        po.order_line.product_qty = 3
        self._approve(po)
        policy = self._policy()
        policy.with_user(self.planner).action_evaluate()
        self.assertFalse(self.env['purchase.order.line'].search([('orderpoint_id', '=', policy.orderpoint_id.id)]))

    def test_native_multi_warehouse_resupply(self):
        self._mo()
        self.env['stock.quant']._update_available_quantity(self.panel, self.supply.lot_stock_id, 20)
        route = self.production.resupply_route_ids.filtered(lambda r: r.supplier_wh_id == self.supply)
        policy = self._policy(self.panel, route)
        policy.with_user(self.planner).action_evaluate()
        transfers = self.env['stock.move'].search([
            ('product_id', '=', self.panel.id), ('location_dest_id', '=', self.production.lot_stock_id.id),
            ('state', 'not in', ['cancel', 'done']),
        ])
        self.assertEqual(sum(transfers.mapped('product_uom_qty')), 6)
        self.assertFalse(self.env['purchase.order.line'].search([('product_id', '=', self.panel.id)]))
        ids = transfers.ids
        policy.with_user(self.planner).action_evaluate()
        self.assertEqual(self.env['stock.move'].search([('id', 'in', ids)]).ids, ids)
        supply_out = self.env['stock.picking'].search([
            ('picking_type_id', '=', self.supply.out_type_id.id), ('state', '!=', 'cancel')])
        self._receive(supply_out)
        incoming = transfers.picking_id
        self._receive(incoming)
        self.assertEqual(self.panel.with_context(location=self.production.lot_stock_id.id).qty_available, 6)
        self.assertEqual(self.panel.with_context(location=self.supply.lot_stock_id.id).qty_available, 14)

    def test_unit_conversion_in_bom(self):
        self.bom.bom_line_ids.filtered(lambda l: l.product_id == self.pack).write({
            'product_uom_id': self.env.ref('uom.product_uom_dozen').id, 'product_qty': 1,
        })
        mo = self._mo(2)
        move = mo.move_raw_ids.filtered(lambda m: m.product_id == self.pack)
        self.assertEqual(move.product_uom._compute_quantity(move.product_uom_qty, self.pack.uom_id), 24)

    def test_bad_planning_limits_and_duplicate_policy(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._policy(maximum=-1)
        self._policy()
        with self.assertRaises(UniqueViolation), self.cr.savepoint():
            self._policy()

    def test_planning_unauthorized_action(self):
        policy = self._policy()
        with self.assertRaises(AccessError):
            policy.with_user(self.operator).action_evaluate()

    def test_low_value_purchase_approval(self):
        po = self._po(100)
        self._approve(po)
        self.assertEqual(po.state, 'purchase')
        self.assertEqual(po.mxt_approval_state, 'approved')
        self.assertEqual(len(po.mxt_event_ids), 2)

    def test_high_value_purchase_requires_final(self):
        po = self._po(5000)
        po.action_mxt_submit()
        po.with_user(self.manager).action_mxt_manager_approve()
        self.assertEqual(po.mxt_approval_state, 'manager')
        with self.assertRaises(UserError):
            po.button_confirm()
        po.with_user(self.final).action_mxt_final_approve()
        po.button_confirm()
        self.assertEqual(po.state, 'purchase')

    def test_approval_role_and_rpc_bypass(self):
        po = self._po()
        po.action_mxt_submit()
        with self.assertRaises(AccessError):
            po.action_mxt_manager_approve()
        with self.assertRaises(AccessError):
            po.write({'mxt_approval_state': 'approved'})
        with self.assertRaises(UserError):
            po.write({'state': 'purchase'})
        with self.assertRaises(UserError):
            po.button_approve(force=True)
        with self.assertRaises(AccessError):
            self.env['purchase.order'].with_user(self.buyer).create({
                'partner_id': self.vendor.id, 'mxt_approval_state': 'approved'})

    def test_requester_cannot_self_approve(self):
        po = self._po().with_user(self.manager)
        po.action_mxt_submit()
        with self.assertRaises(AccessError):
            po.action_mxt_manager_approve()

    def test_approved_lines_cannot_change(self):
        po = self._po()
        po.action_mxt_submit()
        po.with_user(self.manager).action_mxt_manager_approve()
        with self.assertRaises(UserError):
            po.order_line.write({'price_unit': 50000})
        with self.assertRaises(UserError):
            po.order_line.unlink()
        po.action_mxt_reset()
        po.order_line.price_unit = 50000
        self.assertEqual(po.mxt_approval_state, 'draft')

    def test_rejection_and_duplicate_actions(self):
        po = self._po()
        po.action_mxt_submit()
        with self.assertRaises(UserError):
            po.action_mxt_submit()
        po.with_user(self.manager).mxt_rejection_reason = 'Fictional missing specification'
        po.with_user(self.manager).action_mxt_reject()
        self.assertEqual(po.mxt_approval_state, 'rejected')
        po.action_mxt_reset()
        self.assertEqual(len(po.mxt_event_ids), 3)

    def test_history_is_immutable(self):
        po = self._po()
        po.action_mxt_submit()
        with self.assertRaises(AccessError):
            po.mxt_event_ids.write({'action': 'Forged'})
        with self.assertRaises(AccessError):
            po.mxt_event_ids.unlink()

    def test_stage_and_quality_bypass_blocked(self):
        mo = self._mo().with_user(self.operator)
        with self.assertRaises(UserError):
            mo.write({'mxt_stage_id': self.env.ref('mxt_operations.stage_done').id})
        with self.assertRaises(UserError):
            mo.button_mark_done()
        with self.assertRaises(AccessError):
            mo.write({'mxt_quality_status': 'pass'})
        with self.assertRaises(AccessError):
            mo.action_mxt_quality_pass()
        mo.action_mxt_material_review()
        with self.assertRaises(UserError):
            mo.action_mxt_material_ready()

    def test_full_manufacturing_workflow_and_stock(self):
        mo = self._mo()
        for product, quantity in [(self.panel, 6), (self.pack, 3)]:
            self.env['stock.quant']._update_available_quantity(product, self.production.lot_stock_id, quantity)
        mo.action_assign()
        self._stages_to_quality(mo)
        mo.mxt_inspection_note = 'Dimensions and finish checked using fictional criteria.'
        mo.qty_producing = 3
        mo._set_qty_producing()
        mo.with_user(self.reviewer).action_mxt_quality_pass()
        mo.with_context(skip_backorder=True).button_mark_done()
        self.assertEqual(mo.state, 'done')
        self.assertEqual(mo.mxt_stage_id.code, 'done')
        self.assertEqual(self.finished.with_context(location=self.production.lot_stock_id.id).qty_available, 3)
        self.assertEqual(self.panel.with_context(location=self.production.lot_stock_id.id).qty_available, 0)

    def test_rework_revokes_quality_and_returns_to_production(self):
        mo = self._mo()
        for product in (self.panel, self.pack):
            self.env['stock.quant']._update_available_quantity(product, self.production.lot_stock_id, 20)
        self._stages_to_quality(mo)
        mo.mxt_inspection_note = 'Rework the fictional surface finish.'
        mo.with_user(self.reviewer).action_mxt_rework()
        self.assertEqual(mo.mxt_stage_id.code, 'production')
        with self.assertRaises(UserError):
            mo.button_mark_done()

    def test_sale_creates_native_manufacturing_demand(self):
        sale = self.env['sale.order'].create({
            'partner_id': self.customer.id, 'warehouse_id': self.production.id,
            'order_line': [Command.create({'product_id': self.finished.id,
                                           'product_uom_qty': 2, 'price_unit': 300})],
        })
        sale.action_confirm()
        mo = self.env['mrp.production'].search([('origin', '=', sale.name), ('product_id', '=', self.finished.id)])
        self.assertEqual(len(mo), 1)
        self.assertEqual(mo.product_qty, 2)
        self.assertEqual(sum(mo.move_raw_ids.filtered(lambda m: m.product_id == self.panel).mapped('product_uom_qty')), 4)

    def test_company_isolation(self):
        other = self.env['res.company'].create({'name': 'Other Fictional Company'})
        other_wh = self.env['stock.warehouse'].with_company(other).search([('company_id', '=', other.id)], limit=1)
        policy = self.env['mxt.planning.policy'].with_company(other).create({
            'name': 'Other company policy', 'company_id': other.id,
            'warehouse_id': other_wh.id, 'product_id': self.pack.id,
            'route_id': self.env.ref('purchase_stock.route_warehouse0_buy').id,
        })
        with self.assertRaises(AccessError):
            policy.with_user(self.planner).with_context(allowed_company_ids=[self.company.id]).read(['name'])

    def test_qweb_reports_render(self):
        mo = self._mo()
        report = self.env['ir.actions.report']
        html, _ = report._render_qweb_html('mxt_operations.material_summary', mo.ids)
        self.assertIn(b'Test Cabinet', html)
        pdf, kind = report.with_context(force_report_rendering=True)._render_qweb_pdf('mxt_operations.material_summary', mo.ids)
        self.assertEqual(kind, 'pdf')
        self.assertTrue(pdf.startswith(b'%PDF'))
        policy = self._policy()
        html, _ = report._render_qweb_html('mxt_operations.policy_summary', policy.ids)
        self.assertIn(b'Test requirement', html)

    def test_variant_specific_bom_requirements(self):
        attribute = self.env['product.attribute'].create({'name': 'Fictional Size'})
        small, large = self.env['product.attribute.value'].create([
            {'name': 'Small', 'attribute_id': attribute.id},
            {'name': 'Large', 'attribute_id': attribute.id},
        ])
        template = self.env['product.template'].create({
            'name': 'Variant Cabinet', 'type': 'product',
            'attribute_line_ids': [Command.create({'attribute_id': attribute.id,
                                                   'value_ids': [Command.set([small.id, large.id])]})],
        })
        large_ptav = template.attribute_line_ids.product_template_value_ids.filtered(
            lambda v: v.product_attribute_value_id == large)
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': template.id, 'product_qty': 1,
            'bom_line_ids': [
                Command.create({'product_id': self.pack.id, 'product_qty': 1}),
                Command.create({'product_id': self.panel.id, 'product_qty': 2,
                                'bom_product_template_attribute_value_ids': [Command.set(large_ptav.ids)]}),
            ],
        })
        for variant in template.product_variant_ids:
            mo = self.env['mrp.production'].create({
                'product_id': variant.id, 'product_qty': 1, 'bom_id': bom.id,
                'picking_type_id': self.production.manu_type_id.id,
            })
            mo.action_confirm()
            panels = mo.move_raw_ids.filtered(lambda m: m.product_id == self.panel)
            expected = 2 if large_ptav in variant.product_template_attribute_value_ids else 0
            self.assertEqual(sum(panels.mapped('product_uom_qty')), expected)

    def test_cron_counts_prior_supply_on_repeated_runs(self):
        self._mo()
        policy = self._policy()
        self.env['mxt.planning.policy'].with_user(self.planner)._cron_evaluate()
        lines = self.env['purchase.order.line'].search([('orderpoint_id', '=', policy.orderpoint_id.id)])
        self.assertEqual(sum(lines.mapped('product_qty')), 3)
        self.env['mxt.planning.policy'].with_user(self.planner)._cron_evaluate()
        self.assertEqual(sum(lines.mapped('product_qty')), 3)
        self.assertEqual(self.env['purchase.order.line'].search([('orderpoint_id', '=', policy.orderpoint_id.id)]).ids, lines.ids)

    def test_foreign_currency_threshold_uses_company_currency(self):
        currency = self.env['res.currency'].create({
            'name': 'XTS', 'symbol': 'T', 'rounding': 0.01,
        })
        self.env['res.currency.rate'].create({
            'currency_id': currency.id, 'company_id': self.company.id,
            'rate': 10, 'name': '2000-01-01',
        })
        po = self._po(2000)
        po.currency_id = currency
        self.assertFalse(po.mxt_needs_final)
        po.order_line.price_unit = 20000
        self.assertTrue(po.mxt_needs_final)

    def test_changed_consumption_revokes_effective_inspection(self):
        mo = self._mo()
        for product in (self.panel, self.pack):
            self.env['stock.quant']._update_available_quantity(product, self.production.lot_stock_id, 20)
        self._stages_to_quality(mo)
        mo.qty_producing = 3
        mo._set_qty_producing()
        mo.mxt_inspection_note = 'Actual quantities inspected.'
        mo.with_user(self.reviewer).action_mxt_quality_pass()
        mo.move_raw_ids.filtered(lambda m: m.product_id == self.panel).quantity = 4
        with self.assertRaises(UserError):
            mo.with_user(self.operator).button_mark_done()
