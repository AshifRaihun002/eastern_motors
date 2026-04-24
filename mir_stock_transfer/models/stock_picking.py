from odoo import models, fields, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    inter_company_transfer_id = fields.Many2one('inter.company.transfer', string="Inter Company Transfer Reference")


class StockMove(models.Model):
    _inherit = 'stock.move'

    inter_company_transfer_line_id = fields.Many2one('inter.company.transfer.line',
                                                     string="Inter Company Transfer Line Reference")
    requisition_line_id = fields.Many2one('custom.purchase.requisition.line', string='Requisition Line No')

class AccountMove(models.Model):
    _inherit = 'account.move'

    inter_company_transfer_id = fields.Many2one('inter.company.transfer', string='Inter Company Transfer')