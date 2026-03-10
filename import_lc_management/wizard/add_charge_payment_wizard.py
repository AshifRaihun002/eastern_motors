from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime


class LCVendorPaymentWizard(models.TransientModel):
    _name = 'lc.vendor.payment.wizard'
    _description = 'Vendor Payment Wizard'

    lc_id = fields.Many2one('letter.credit', string='Letter of Credit', required=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True,
                                 domain=[('supplier_rank', '>', 0), ('is_vendor', '=', True)])
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True)
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lc = self.env['letter.credit'].browse(self.env.context.get('active_id'))
        res['lc_id'] = lc.id
        res['currency_id'] = lc.company_id.currency_id.id
        return res

    def action_create_payment(self):
        self.ensure_one()

        payment_vals = {
            'partner_id': self.partner_id.id,
            'partner_type': 'supplier',
            'payment_type': 'outbound',
            'journal_id': self.journal_id.id,
            'amount': self.amount,
            'custom_currency_rate':1,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,  # <--- Add this
            'date': fields.Date.context_today(self),
            'memo': f'LC Payment ({self.lc_id.name})',
        }

        payment = self.env['account.payment'].create(payment_vals)
        if payment.move_id:
            payment.move_id.custom_conversion_rate = payment.custom_currency_rate

        payment.action_post()

        # Link to LC
        self.lc_id.payment_ids = [(4, payment.id)]

        self.lc_id.message_post(
            body=f"Vendor Payment <a href='/web#id={payment.id}&model=account.payment'>{payment.name}</a> created via wizard."
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': payment.id
        }