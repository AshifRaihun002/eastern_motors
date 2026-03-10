from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime

class LCVendorBillWizard(models.TransientModel):
    _name = "lc.vendor.bill.wizard"
    _description = "LC Vendor Bill Wizard"

    lc_id = fields.Many2one('letter.credit', string="Letter of Credit", required=True)
    vendor_id = fields.Many2one('res.partner', string="Vendor", domain="[('supplier_rank', '>', 0),('is_vendor', '=', True)]", required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )
    bill_line_ids = fields.One2many('lc.vendor.bill.wizard.line', 'wizard_id', string="Charge Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lc = self.env['letter.credit'].browse(self._context.get('active_id'))
        lines = []
        for line in lc.lc_cost_line_ids.filtered(lambda l: l.amount > 0 and l.landed_cost_type == 'cnf_charge'):
            lines.append((0, 0, {
                'product_id': line.product_id.id,
                'description': line.product_id.name,
                'amount': line.amount,
                'account_id': line.account_id.id,
                'original_line_id': line.id,
            }))
        res.update({
            'lc_id': lc.id,
            'currency_id': lc.company_id.currency_id.id,
            'bill_line_ids': lines,
        })
        return res

    def action_create_vendor_bill(self):
        self.ensure_one()

        invoice_lines = []
        for line in self.bill_line_ids:
            invoice_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.description,
                'quantity': 1,
                'price_unit': line.amount,
                'account_id': line.account_id.id,
                'currency_id': self.currency_id.id,
            }))

        bill = self.env['account.move'].with_company(self.lc_id.company_id).create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': self.lc_id.name,
            'company_id': self.lc_id.company_id.id,
            'currency_id': self.currency_id.id,
            'purchase_requisition_type': self.lc_id.po_id.purchase_payment_type,
            'invoice_line_ids': invoice_lines,
        })

        self.lc_id.write({
            'add_charge_vendor_bill': [(4, bill.id)]
        })

        self.lc_id.message_post(
            body=f"Vendor Bill <a href='/web#id={bill.id}&model=account.move'>{bill.name}</a> created via wizard."
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': bill.id,
            'view_mode': 'form',
            'target': 'current',
        }

class LCVendorBillWizardLine(models.TransientModel):
    _name = "lc.vendor.bill.wizard.line"
    _description = "LC Vendor Bill Wizard Line"

    wizard_id = fields.Many2one('lc.vendor.bill.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    description = fields.Char(string="Description")
    amount = fields.Float(string="Amount", required=True)
    account_id = fields.Many2one('account.account', string="Account", required=True)
    original_line_id = fields.Many2one('letter.credit.cost.line', string="Original Cost Line", readonly=True)