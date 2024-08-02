from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class PlanningPolicy(models.Model):
    _name = 'mxt.planning.policy'
    _description = 'Warehouse Material Planning Policy'
    _inherit = ['mail.thread']
    _check_company_auto = True

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    product_id = fields.Many2one('product.product', required=True, check_company=True,
                                 domain="[('type', '=', 'product')]")
    warehouse_id = fields.Many2one('stock.warehouse', required=True, check_company=True)
    route_id = fields.Many2one('stock.route', required=True, check_company=True)
    min_qty = fields.Float(default=0, required=True)
    max_qty = fields.Float(default=0, required=True)
    safety_qty = fields.Float(default=0, required=True)
    visibility_days = fields.Float(default=0)
    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', readonly=True, copy=False, check_company=True)
    forecast_qty = fields.Float(compute='_compute_forecast')
    suggested_qty = fields.Float(compute='_compute_forecast')
    last_evaluated = fields.Datetime(readonly=True)
    last_decision = fields.Char(readonly=True)

    _sql_constraints = [
        ('product_warehouse_unique', 'unique(product_id, warehouse_id)',
         'One lab policy per product and warehouse is permitted.'),
    ]

    @api.depends('orderpoint_id.qty_forecast', 'orderpoint_id.qty_to_order')
    def _compute_forecast(self):
        for policy in self:
            policy.forecast_qty = policy.orderpoint_id.qty_forecast
            policy.suggested_qty = policy.orderpoint_id.qty_to_order

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.safety_qty = self.product_id.mxt_safety_stock

    @api.constrains('min_qty', 'max_qty', 'safety_qty', 'visibility_days',
                    'product_id', 'warehouse_id', 'company_id', 'route_id')
    def _check_policy(self):
        for policy in self:
            if min(policy.min_qty, policy.safety_qty, policy.visibility_days) < 0 or policy.max_qty < policy.min_qty:
                raise ValidationError(_('Quantities and horizon must be nonnegative; maximum must be at least minimum.'))
            if policy.product_id.type != 'product':
                raise ValidationError(_('Planning requires a storable product.'))
            if policy.warehouse_id.company_id != policy.company_id:
                raise ValidationError(_('The warehouse must belong to the policy company.'))

    def _check_manager(self):
        if not self.env.user.has_group('mxt_operations.group_planning_manager'):
            raise AccessError(_('Only planning managers may evaluate replenishment.'))
        self.check_access_rights('write')
        self.check_access_rule('write')

    def action_evaluate(self):
        self._check_manager()
        for company in self.company_id:
            policies = self.filtered(lambda p: p.company_id == company and p.active).with_company(company)
            if not policies:
                continue
            # Serialize custom UI/cron evaluations, including overlapping policy sets.
            # SQL only acquires a lock; all business data access remains in the ORM.
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (170170, company.id))
            policies.invalidate_recordset(['orderpoint_id'])
            for policy in policies.sorted('id'):
                vals = {
                    'product_id': policy.product_id.id,
                    'warehouse_id': policy.warehouse_id.id,
                    'location_id': policy.warehouse_id.lot_stock_id.id,
                    'company_id': company.id,
                    'route_id': policy.route_id.id,
                    'product_min_qty': policy.min_qty + policy.safety_qty,
                    'product_max_qty': policy.max_qty + policy.safety_qty,
                    'visibility_days': policy.visibility_days,
                    'trigger': 'manual',
                }
                # Manual native trigger prevents the unrelated native cron from
                # racing the explicitly serialized lab scheduler.
                if not policy.orderpoint_id:
                    existing = self.env['stock.warehouse.orderpoint'].search([
                        ('product_id', '=', policy.product_id.id),
                        ('location_id', '=', policy.warehouse_id.lot_stock_id.id),
                    ])
                    if existing:
                        raise ValidationError(_('An existing native orderpoint conflicts with %s. Review it before enabling this policy.') % policy.name)
                    policy.orderpoint_id = self.env['stock.warehouse.orderpoint'].create(vals)
                else:
                    policy.orderpoint_id.write(vals)
                point = policy.orderpoint_id
                point.invalidate_recordset(['qty_forecast', 'qty_to_order'])
                quantity = point.qty_to_order
                forecast = point.qty_forecast
                point._procure_orderpoint_confirm(company_id=company, raise_user_error=True)
                decision = _('Forecast %(forecast)s. Supply requested %(quantity)s %(uom)s via %(route)s.') % {
                    'forecast': forecast, 'quantity': quantity,
                    'uom': policy.product_id.uom_id.name, 'route': policy.route_id.name,
                }
                policy.write({'last_evaluated': fields.Datetime.now(), 'last_decision': decision})
                if quantity > 0:
                    policy.message_post(body=decision)
        return True

    @api.model
    def _cron_evaluate(self):
        # Runs as the configured scheduler user, without privilege elevation.
        for company in self.env.companies:
            self.search([('company_id', '=', company.id)]).action_evaluate()

    def unlink(self):
        self._check_manager()
        points = self.orderpoint_id
        result = super().unlink()
        points.unlink()
        return result

    @api.model
    def _seed_demo(self):
        """Install-only fictional scenario; external IDs make it reproducible."""
        if self.env['ir.config_parameter'].sudo().get_param('mxt_operations.demo_seeded'):
            return
        ref = lambda key: self.env.ref('mxt_operations.' + key)
        production_wh = ref('warehouse_production')
        supply_wh = ref('warehouse_supply')
        resupply = production_wh.resupply_route_ids.filtered(
            lambda route: route.supplier_wh_id == supply_wh)
        if len(resupply) != 1:
            raise ValidationError(_('Expected one native secondary-to-production resupply route.'))
        self.env.ref('stock.route_warehouse0_mto').active = True
        self.env['stock.quant']._update_available_quantity(ref('component_a'), supply_wh.lot_stock_id, 40)
        self.env['stock.quant']._update_available_quantity(ref('component_b'), production_wh.lot_stock_id, 1)
        for key, product, route, maximum, safety in [
            ('policy_panel', ref('component_a'), resupply, 4, 2),
            ('policy_pack', ref('component_b'), self.env.ref('purchase_stock.route_warehouse0_buy'), 2, 1),
        ]:
            policy = self.create({
                'name': product.name + ' at Production', 'product_id': product.id,
                'warehouse_id': production_wh.id, 'route_id': route.id,
                'min_qty': 0, 'max_qty': maximum, 'safety_qty': safety,
                'company_id': production_wh.company_id.id,
            })
            self.env['ir.model.data'].create({'module': 'mxt_operations', 'name': key,
                                             'model': self._name, 'res_id': policy.id, 'noupdate': True})
        sale = self.env['sale.order'].create({
            'partner_id': ref('customer').id, 'warehouse_id': production_wh.id,
            'mxt_planning_note': 'Confirm to create native MTO manufacturing demand; evaluate the two material policies.',
            'order_line': [fields.Command.create({
                'product_id': ref('finished_product').id, 'product_uom_qty': 3,
                'price_unit': 300,
            })],
        })
        self.env['ir.model.data'].create({'module': 'mxt_operations', 'name': 'demo_sale',
                                         'model': 'sale.order', 'res_id': sale.id, 'noupdate': True})
        self.env.company.name = 'Example Fabrication Lab'
        self.env.company.logo = False
        self.env['ir.config_parameter'].sudo().set_param('mxt_operations.demo_seeded', '1')
