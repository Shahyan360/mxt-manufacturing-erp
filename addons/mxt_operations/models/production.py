import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ProductionStage(models.Model):
    _name = 'mxt.production.stage'
    _description = 'Manufacturing Lab Stage'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    code = fields.Selection([
        ('planned', 'Planned'), ('review', 'Material Review'), ('ready', 'Materials Ready'),
        ('production', 'In Production'), ('quality', 'Quality Review'), ('done', 'Completed'),
    ], required=True)
    sequence = fields.Integer()
    fold = fields.Boolean()
    _sql_constraints = [('code_unique', 'unique(code)', 'Stage code must be unique.')]


class Production(models.Model):
    _inherit = 'mrp.production'

    mxt_stage_id = fields.Many2one(
        'mxt.production.stage', string='Lab Stage', tracking=True, copy=False,
        default=lambda s: s.env.ref('mxt_operations.stage_planned', raise_if_not_found=False),
        group_expand='_mxt_expand_stages')
    mxt_quality_status = fields.Selection([
        ('pending', 'Pending Inspection'), ('pass', 'Passed'),
        ('rework', 'Rework Required'), ('reject', 'Rejected'),
    ], default='pending', readonly=True, copy=False, tracking=True)
    mxt_quality_reviewer_id = fields.Many2one('res.users', readonly=True, copy=False)
    mxt_inspection_fingerprint = fields.Char(readonly=True, copy=False)
    mxt_inspection_note = fields.Text(string='Inspection / Rework Notes')
    mxt_material_ready = fields.Boolean(compute='_compute_mxt_material_ready')

    @api.depends('move_raw_ids.state', 'state')
    def _compute_mxt_material_ready(self):
        for production in self:
            moves = production.move_raw_ids.filtered(lambda m: m.state != 'cancel')
            production.mxt_material_ready = bool(moves) and all(m.state in ('assigned', 'done') for m in moves)

    @api.model
    def _mxt_expand_stages(self, stages, domain, order):
        return self.env['mxt.production.stage'].search([], order=order)

    def _mxt_access(self):
        self.check_access_rights('write')
        self.check_access_rule('write')
        if not self.env.user.has_group('mrp.group_mrp_user'):
            raise AccessError(_('Manufacturing access is required.'))
        if self:
            self.env.cr.execute('SELECT id FROM mrp_production WHERE id IN %s ORDER BY id FOR UPDATE',
                                (tuple(self.ids),))
            self.invalidate_recordset(['mxt_stage_id', 'mxt_quality_status', 'state'])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (vals.get('mxt_quality_status', 'pending') != 'pending'
                    or vals.get('mxt_quality_reviewer_id') or vals.get('mxt_inspection_fingerprint')):
                raise AccessError(_('Use inspection actions.'))
            if vals.get('state', 'draft') != 'draft':
                raise UserError(_('Manufacturing orders must start in draft.'))
            if vals.get('mxt_stage_id') and self.env['mxt.production.stage'].browse(vals['mxt_stage_id']).code != 'planned':
                raise UserError(_('Manufacturing orders start at Planned.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'mxt_quality_status', 'mxt_quality_reviewer_id', 'mxt_inspection_fingerprint'}.intersection(vals):
            raise AccessError(_('Use inspection actions.'))
        if 'mxt_stage_id' in vals:
            self._mxt_access()
            target = self.env['mxt.production.stage'].browse(vals['mxt_stage_id']).exists()
            if not target:
                raise UserError(_('A workflow stage is required.'))
            transitions = {
                'planned': {'review'}, 'review': {'ready'}, 'ready': {'production', 'review'},
                'production': {'quality'}, 'quality': set(), 'done': set(),
            }
            for production in self:
                current = production.mxt_stage_id.code
                if target == production.mxt_stage_id:
                    continue
                if production.state in ('done', 'cancel') or target.code not in transitions.get(current, set()):
                    raise UserError(_('This stage transition is not allowed.'))
                if target.code in ('ready', 'production'):
                    production.action_assign()
                    if not production.mxt_material_ready:
                        raise UserError(_('Reserve all required components before progressing.'))
                if target.code == 'quality' and production.state not in ('confirmed', 'progress', 'to_close'):
                    raise UserError(_('Confirm manufacturing before inspection.'))
        if vals.get('state') == 'done':
            self._mxt_require_quality()
        # Any material/quantity/BOM edit revokes a prior inspection result.
        if {'product_id', 'product_qty', 'product_uom_id', 'bom_id', 'location_src_id',
            'location_dest_id', 'move_raw_ids', 'move_finished_ids', 'mxt_inspection_note'}.intersection(vals):
            for production in self.filtered(lambda p: p.mxt_quality_status == 'pass'):
                raise UserError(_('Request rework before changing inspected manufacturing data.'))
        return super().write(vals)

    def _mxt_require_quality(self):
        for production in self:
            if production.mxt_stage_id.code != 'quality' or production.mxt_quality_status != 'pass':
                raise UserError(_('A passed quality inspection is required before completing production.'))
            if production.mxt_inspection_fingerprint != production._mxt_fingerprint():
                raise UserError(_('Production quantities or traceability changed after inspection. Request rework and repeat inspection.'))

    def _mxt_fingerprint(self):
        self.ensure_one()
        data = [self.product_id.id, self.product_qty, self.qty_producing,
                self.product_uom_id.id, self.location_src_id.id, self.location_dest_id.id,
                self.lot_producing_id.id]
        for move in (self.move_raw_ids | self.move_finished_ids).sorted('id'):
            if move.state == 'cancel':
                continue
            data.append([move.id, move.product_id.id, move.product_uom_qty,
                         move.quantity, move.product_uom.id, move.location_id.id, move.location_dest_id.id,
                         sorted((line.product_id.id, line.quantity, line.product_uom_id.id,
                                 line.lot_id.id, line.location_id.id, line.location_dest_id.id)
                                for line in move.move_line_ids)])
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _mxt_move_to(self, code):
        self._mxt_access()
        self.write({'mxt_stage_id': self.env.ref('mxt_operations.stage_' + code).id})
        return True

    def action_mxt_material_review(self):
        return self._mxt_move_to('review')

    def action_mxt_material_ready(self):
        return self._mxt_move_to('ready')

    def action_mxt_start(self):
        return self._mxt_move_to('production')

    def action_mxt_inspect(self):
        return self._mxt_move_to('quality')

    def _mxt_inspection(self, result):
        self._mxt_access()
        if not self.env.user.has_group('mxt_operations.group_quality_reviewer'):
            raise AccessError(_('Only quality reviewers may record an inspection.'))
        for production in self:
            if production.state in ('done', 'cancel') or production.mxt_stage_id.code != 'quality':
                raise UserError(_('Only active orders in Quality Review may be inspected.'))
            if not production.mxt_inspection_note:
                raise UserError(_('Record inspection findings first.'))
            if production.mxt_quality_status == result:
                raise UserError(_('This inspection outcome is already recorded.'))
            if production.mxt_quality_status == 'reject' and result == 'pass':
                raise UserError(_('Request rework and repeat production before passing a rejected inspection.'))
            if result == 'pass' and production.qty_producing <= 0:
                raise UserError(_('Record actual production quantities before inspection.'))
            values = {'mxt_quality_status': result, 'mxt_quality_reviewer_id': self.env.uid,
                      'mxt_inspection_fingerprint': production._mxt_fingerprint() if result == 'pass' else False}
            if result == 'rework':
                values['mxt_stage_id'] = self.env.ref('mxt_operations.stage_production').id
            super(Production, production).write(values)
            production.message_post(body=_('Inspection result: %s') % result)
        return True

    def action_mxt_quality_pass(self):
        return self._mxt_inspection('pass')

    def action_mxt_rework(self):
        return self._mxt_inspection('rework')

    def action_mxt_quality_reject(self):
        return self._mxt_inspection('reject')

    def _post_inventory(self, cancel_backorder=False):
        self._mxt_require_quality()
        return super()._post_inventory(cancel_backorder=cancel_backorder)

    def button_mark_done(self):
        self._mxt_access()
        self._mxt_require_quality()
        result = super().button_mark_done()
        completed = self.filtered(lambda p: p.state == 'done')
        if completed:
            super(Production, completed).write({'mxt_stage_id': self.env.ref('mxt_operations.stage_done').id})
        return result
