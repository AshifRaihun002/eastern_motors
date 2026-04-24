from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.onchange('move_type')
    def onchange_move_type(self):
        partner_domain = []
        if self.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
            partner_domain = [('is_vendor', '=', True)]
        elif self.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
            partner_domain = [('is_customer', '=', True)]

        return {'domain': {'partner_id': partner_domain}}