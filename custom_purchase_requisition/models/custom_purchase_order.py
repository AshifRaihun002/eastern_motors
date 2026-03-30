from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'


    requisition_id = fields.Many2one(
        comodel_name='custom.purchase.requisition',
        string='Purchase Requisition',
        compute='_compute_requisition_id',
    )
    requisition_line_id = fields.Many2one(comodel_name='custom.purchase.requisition.line', string='Requisition Lines')

    size = fields.Char(string="Size")
    pr = fields.Char(string="PR")
    pattern = fields.Char(string="Pattern")
    hs_code = fields.Char(string="HS Code")

    @api.depends('requisition_line_id', 'requisition_line_id.requisition_id')
    def _compute_requisition_id(self):
        """Compute requisition_id from requisition_line_id"""
        for line in self:
            line.requisition_id = line.requisition_line_id.requisition_id if line.requisition_line_id else False