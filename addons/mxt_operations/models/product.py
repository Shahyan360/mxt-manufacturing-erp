from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    mxt_material_class = fields.Selection([
        ('raw', 'Raw Material'), ('component', 'Component'),
        ('finished', 'Finished Goods'), ('supply', 'Administrative Supply'),
    ], string='Lab Material Class')
    mxt_safety_stock = fields.Float(string='Default Safety Stock', default=0)
    mxt_vendor_lead_days = fields.Float(compute='_compute_mxt_vendor_lead_days')

    @api.depends('seller_ids.delay')
    def _compute_mxt_vendor_lead_days(self):
        for product in self:
            product.mxt_vendor_lead_days = min(product.seller_ids.mapped('delay'), default=0)

    @api.constrains('mxt_safety_stock')
    def _check_mxt_safety_stock(self):
        if any(p.mxt_safety_stock < 0 for p in self):
            raise ValidationError(_('Safety stock cannot be negative.'))


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mxt_planning_note = fields.Text(string='Production Planning Note')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    mxt_transfer_note = fields.Text(string='Material Coordination Note')
