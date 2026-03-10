from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime


class LCShipmentVendorBillWizard(models.TransientModel):
    _name = "lc.shipment.vendor.bill.wizard"
    _description = "LC Shipment Vendor Bill Wizard"

    shipment_id = fields.Many2one('lc.shipment', string="LC Shipment", required=True)
    vendor_id = fields.Many2one('res.partner', string="Vendor",
                                domain="[('supplier_rank', '>', 0), ('is_vendor', '=', True)]",
                                required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )
    bill_line_ids = fields.One2many('lc.shipment.vendor.bill.wizard.line', 'wizard_id', string="Charge Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        shipment = self.env['lc.shipment'].browse(self._context.get('active_id'))

        # Get cost lines from shipment instead of letter.credit
        lines = []
        for line in shipment.cost_line_ids.filtered(lambda l: l.amount > 0 and l.landed_cost_type == 'cnf_charge'):
            lines.append((0, 0, {
                'product_id': line.product_id.id,
                'description': line.product_id.name,
                'amount': line.amount,
                'account_id': line.account_id.id,
                'original_line_id': line.id,
            }))

        res.update({
            'shipment_id': shipment.id,
            'vendor_id': shipment.partner_id.id,  # Use partner_id from shipment
            'currency_id': shipment.company_id.currency_id.id,
            'bill_line_ids': lines,
        })
        return res

    @api.onchange('shipment_id')
    def _onchange_shipment_id(self):
        if self.shipment_id:
            self.vendor_id = self.shipment_id.partner_id
            self.currency_id = self.shipment_id.company_id.currency_id

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

        bill = self.env['account.move'].with_company(self.shipment_id.company_id).create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': f"{self.shipment_id.lc_id.name} - {self.shipment_id.name}",
            'company_id': self.shipment_id.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_line_ids': invoice_lines,
        })
        self.shipment_id.write({
            'add_charge_vendor_bill': [(4, bill.id)]
        })



        # Link the bill to the shipment (you might want to add a field for this)
        # For example, if you have a Many2many field in lc.shipment for vendor bills:
        # self.shipment_id.vendor_bill_ids = [(4, bill.id)]

        # Or if you want to track in messages and potentially add a field later:
        self.shipment_id.message_post(
            body=f"Vendor Bill <a href='/web#id={bill.id}&model=account.move'>{bill.name}</a> created for additional charges."
        )

        # Update cost lines to mark as billed if needed
        for line in self.bill_line_ids:
            if line.original_line_id:
                line.original_line_id.write({'is_payed': True})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': bill.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'create': False, 'edit': False}
        }


class LCShipmentVendorBillWizardLine(models.TransientModel):
    _name = "lc.shipment.vendor.bill.wizard.line"
    _description = "LC Shipment Vendor Bill Wizard Line"

    wizard_id = fields.Many2one('lc.shipment.vendor.bill.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    description = fields.Char(string="Description")
    amount = fields.Float(string="Amount", required=True)
    account_id = fields.Many2one('account.account', string="Account", required=True)
    original_line_id = fields.Many2one('shipment.cost.line', string="Original Cost Line", readonly=True)