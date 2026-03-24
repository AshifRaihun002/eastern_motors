from odoo import models, fields, api


class ResPurchaseRequisition(models.Model):
    _inherit = 'custom.purchase.requisition'

    indent_ids = fields.Many2many('indent.process', string='Indent Reference', tracking=True)


class ResPurchaseRequisitionLine(models.Model):
    _inherit = 'custom.purchase.requisition.line'

    indent_ids = fields.Many2many('indent.process', string='Indent Reference', tracking=True)
    indent_line_id = fields.Many2one('indent.line', string='Indent Line')
