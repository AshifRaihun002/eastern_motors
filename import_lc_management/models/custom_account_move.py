from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime


class AccountInvoiceCustom(models.Model):
    _inherit = 'account.move'

    picking_ids = fields.Many2many('stock.picking', string='Pickings')
    pic_count = fields.Integer(string="Picking Count", compute="_compute_picking_count", store=True)
    custom_conversion_rate = fields.Float(string="Conversion Rate", default=1.0)
    manual_currency_rate = fields.Boolean(
        string='Manual Currency Rate',
        help="If checked, the system won't automatically update the currency rate"
    )

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for order in self:
            order.pic_count = len(order.picking_ids)
    @api.depends('currency_id', 'company_currency_id', 'company_id', 'invoice_date')
    def _compute_invoice_currency_rate(self):
        # custome_reate = self.custom_conversion_rate
        super()._compute_invoice_currency_rate()
        for move in self:
            custom_rate = move.custom_conversion_rate
            if move.manual_currency_rate:
                move.invoice_currency_rate = 1 / custom_rate if custom_rate else 1.0
            else:
                move.invoice_currency_rate = 1
            # Skip computation if manual rate is set



    @api.depends('custom_conversion_rate', 'line_ids.price_unit', 'line_ids.debit', 'line_ids.credit')
    def _recompute_dynamic_lines(self, recompute_tax_base_amount=False):
        """
        Override dynamic line recomputation to use custom conversion rate.
        """
        for move in self:
            if move.custom_conversion_rate > 0:
                for line in move.line_ids:
                    # Apply the custom conversion rate to debit and credit values
                    if line.debit > 0:
                        line.debit = line.debit * move.custom_conversion_rate
                    if line.credit > 0:
                        line.credit = line.credit * move.custom_conversion_rate

                    # Update the price_unit if applicable
                    if line.price_unit > 0:
                        line.price_unit = line.price_unit * move.custom_conversion_rate

        # Call the base implementation for taxes and other computations
        super(AccountInvoiceCustom, self)._recompute_dynamic_lines(recompute_tax_base_amount=recompute_tax_base_amount)




class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.depends('currency_id', 'company_id', 'move_id.date')
    def _compute_currency_rate(self):
        super()._compute_currency_rate()

        for line in self:
            #[TODO]
            if line.purchase_order_id and line.purchase_order_id.local_currency>0:
                line.currency_rate = 1/line.purchase_order_id.local_currency
                # if line.currency_id:
                #     # line.currency_rate = self.env['res.currency']._get_conversion_rate(
                #     #     from_currency=line.company_currency_id,
                #     #     to_currency=line.currency_id,
                #     #     company=line.company_id,
                #     #     date=line.move_id.invoice_date or line.move_id.date or fields.Date.context_today(line),
                #     # )
                #     line.currency_rate =
                # else:
                #     line.currency_rate = 1
