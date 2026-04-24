from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    lc_id = fields.Many2one(
        "letter.credit",
        string="L/C",
        index=True,
        domain="[('company_id', '=?', company_id), ('state', 'in', ('confirm', 'approve'))]",
        ondelete="cascade",
        check_company=True,
    )
    lc_count = fields.Integer(
        string="LC Count", compute="_compute_lc_count", store=True
    )

    purchase_process = fields.Selection(
        [
            ('local_purchase', 'Local'),
            ('foreign_purchase', 'Foreign')
        ],
        string='Currency Type',
        default='local_purchase',
        required=True
    )
    local_currency = fields.Float(string="Conversion Rate", default=0.0, tracking=True)

    @api.constrains('currency_id')
    def currency_id_need_to_change_for_foreign_currency(self):
        self.ensure_one()
        if self.purchase_process == 'foreign_purchase' and self.currency_id.id == self.env.company.currency_id.id:
            raise ValidationError("Foreign Currency cannot be Company Currency!")

    @api.onchange('local_currency')
    def get_local_and_foreign_currecy(self):
        for rec in self:
            if rec.purchase_process == 'local_purchase':
                continue
            for line in rec.order_line:
                line.foreign_currency = line.price_unit * rec.local_currency

    def _prepare_invoice(self):
        # Base invoice values
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()

        # Add custom conversion rate if applicable
        if self.local_currency > 0 and self.currency_id != self.company_id.currency_id:
            invoice_vals.update({
                'custom_conversion_rate': self.local_currency,
                'invoice_currency_rate': 1 / self.local_currency,
                'manual_currency_rate': True,  # Set to True when using custom rate
            })
        else:
            # Ensure automatic rate computation when no custom rate is provided
            invoice_vals.update({
                'manual_currency_rate': False,
            })

        return invoice_vals

    def action_create_lc(self):
        self.ensure_one()
        # requisition_ids = self.order_line.mapped('requisition_id').ids if self.order_line else []
        lc = self.env['letter.credit'].create({
            'name': self.env['ir.sequence'].next_by_code('letter.credit') or _('New'),
            'po_id': self.id,
            # 'requisition_id': [(6, 0, requisition_ids)] if requisition_ids else False,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'purchase_process': self.purchase_process,
            'local_currency': self.local_currency,
            'currency_id': self.currency_id.id,
            'warehouse_id': self.picking_type_id.warehouse_id.id,
            'state': 'draft',
        })


        lc_lines = [
            (0, 0, {
                'lc_id': lc.id,
                'po_id': self.id,  # pass purchase order id
                'purchase_line_id': po_line.id,  # pass purchase order line id
                'product_id': po_line.product_id.id,
                'product_uom': po_line.product_uom_id.id,
                'product_qty': po_line.product_qty,
                # 'requisition_id': po_line.requisition_id.id if po_line.requisition_id else False,
                'price_unit': po_line.price_unit,
                'foreign_currency': po_line.foreign_currency,
                'foreign_price_subtotal': po_line.foreign_price_subtotal,
                # 'requisition_line_id': po_line.requisition_line_id.id if po_line.requisition_line_id else False,
            }) for po_line in self.order_line
        ]
        lc.lc_lines = lc_lines

        # Link LC back to PO
        self.lc_id = lc.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Letter of Credit',
            'view_mode': 'form',
            'res_model': 'letter.credit',
            'res_id': lc.id,
            'target': 'current',
        }

    @api.depends("lc_id", "lc_id.state")
    def _compute_lc_count(self):
        for po in self:
            po.lc_count = self.env['letter.credit'].search_count([
                ('po_id', '=', po.id),
                ('state', 'in', ('draft', 'done', 'confirm', 'approve', 'cancel'))
            ])

    def action_view_lcs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Letters of Credit',
            'view_mode': 'list,form',
            'res_model': 'letter.credit',
            'domain': [('po_id', '=', self.id), ('state', 'in', ('draft', 'done', 'confirm', 'approve', 'cancel'))],
            'context': dict(self._context, default_po_id=self.id),
        }

    @api.onchange("lc_id")
    def _onchange_lc_id(self):
        lc = self.lc_id
        if not lc:
            return
        if lc.state == "done":
            raise ValidationError("L/C is already done.")
        self.partner_id = lc.partner_id.id
        self.payment_term_id = self.partner_id.property_supplier_payment_term_id.id
        self.company_id = lc.company_id.id
        self.currency_id = lc.company_id.currency_id.id
        self.picking_type_id = lc.warehouse_id.in_type_id.id
        if not self.origin or lc.name not in self.origin.split(", "):
            self.origin = f"{self.origin}, {lc.name}" if self.origin else lc.name
        self.notes = lc.description
        self.date_order = lc.date_end or fields.Datetime.now()
        POL = self.env["purchase.order.line"]
        order_lines = [
            (0, 0, {
                **POL._prepare_purchase_order_line(
                    line.product_id,
                    line.product_qty - line.ordered_qty,
                    line.product_uom,
                    lc.company_id,
                    lc,
                    self,
                ),
                "product_qty": line.product_qty,
                "product_uom": line.product_uom,
            }) for line in lc.lc_lines if (line.product_qty - line.ordered_qty) > 0
        ]
        self.order_line = [(6, 0, [])]
        self.order_line = order_lines

    def button_confirm(self):
        if self.lc_id and self.lc_id.state == "done":
            raise ValidationError("L/C is already done.")
        res = super().button_confirm()
        po_with_lc_approved = self.filtered(lambda po: po.lc_id and po.lc_id.state == "confirm")
        if po_with_lc_approved:
            po_with_lc_approved.lc_id.write({"state": "approve"})
        return res

    def button_cancel(self):
        if self.lc_id and self.lc_id.state == "done" and self.state in ("done", "purchase"):
            raise ValidationError("L/C is already done.")
        res = super().button_cancel()
        po_with_lc = self.filtered(lambda po: po.lc_id)
        if po_with_lc:
            po_with_lc.lc_id._compute_purchase_related()
        return res

    @api.depends('order_line.price_subtotal', 'company_id', 'local_currency')
    def _amount_all(self):
        AccountTax = self.env['account.tax']
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)

            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )

            # defaults
            amount_untaxed = tax_totals.get('base_amount_currency', 0.0)
            amount_tax = tax_totals.get('tax_amount_currency', 0.0)
            amount_total = tax_totals.get('total_amount_currency', 0.0)
            amount_total_cc = tax_totals.get('total_amount', 0.0)

            # applying for Pasha group only (multiplier if local_currency > 0)
            factor = order.local_currency if order.local_currency > 0 else 1.0

            order.amount_untaxed = amount_untaxed * factor
            order.amount_tax = amount_tax * factor
            order.amount_total = amount_total * factor
            order.amount_total_cc = amount_total_cc * factor



class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # requisition_line_id = fields.Many2one('requisition.product.service', string='Requisition Line id', readonly=True, tracking=True)

    foreign_currency = fields.Float(string='Unit Rate(Local)', default=0.0, compute='compute_foreign_currency',compute_sudo=True,
                                    store=False)
    # foreign_currency_id = fields.Many2one('res.currency', string='Foreign Currency')
    foreign_price_subtotal = fields.Float(string='Subtotal(Local)', default=0.0, compute='compute_foreign_currency', compute_sudo=True)


    @api.depends('price_unit', 'order_id.currency_id', 'order_id.purchase_process', 'order_id.local_currency',
                 'product_qty')
    def compute_foreign_currency(self):
        for line in self:
            if line.order_id.purchase_process == 'foreign_purchase':
                line.foreign_currency = line.price_unit * line.order_id.local_currency
                line.foreign_price_subtotal = line.foreign_currency * line.product_qty
            else:
                line.foreign_currency = line.price_unit * line.order_id.local_currency
                line.foreign_price_subtotal = 0

    @api.onchange('price_unit')
    def _compute_price_unit(self):
        for rec in self:
            if rec.order_id.purchase_process == 'local_purchase':
                continue
            rec.foreign_currency = rec.order_id.local_currency * rec.price_unit

    @api.constrains("product_id", "order_id.state")
    def _check_product_qty(self):
        for line in self:
            lc = line.order_id.lc_id
            if not lc:
                continue
            if line.requisition_line_id:
                if line.product_qty > line.requisition_line_id.remaining_qty:
                    raise ValidationError(
                        _(
                            "The product qty must be less than the requisition remaining qty."
                        )
                    )
                if lc:
                    lc_line = lc.lc_lines.filtered(
                        lambda rec: rec.requisition_line_id
                                    == line.requisition_line_id
                    )
                    if line.product_qty > (lc_line.product_qty - lc_line.ordered_qty):
                        raise ValidationError(
                            _(
                                "The product qty must be less than the L/C remaining qty."
                            )
                        )





class AccountPaymentRegisterInherit(models.TransientModel):
    _inherit = 'account.payment.register'

    custom_conversion_rate = fields.Float(string="Conversion Rate", default=1.0)

    @api.model
    def default_get(self, fields):
        res = super(AccountPaymentRegisterInherit, self).default_get(fields)
        if 'line_ids' in res:
            # Fetch the account move from the context using `line_ids`
            lines = self.env['account.move.line'].browse(res['line_ids'][0][2])
            moves = lines.mapped('move_id')
            in_invoice_move = moves.filtered(lambda m: m.move_type == 'in_invoice')
            for move in in_invoice_move:
                if move.custom_conversion_rate:
                    res['custom_conversion_rate'] = move.custom_conversion_rate
                    break  # stop after first valid rate
        return res

    def _create_payments(self):
        """
        Override to pass the custom_conversion_rate to account.payment.
        """
        payments = super(AccountPaymentRegisterInherit, self)._create_payments()

        # Update the custom_currency_rate on payments
        for payment in payments:
            if self.custom_conversion_rate and self.custom_conversion_rate != 1.0:
                payment.custom_currency_rate = self.custom_conversion_rate

        return payments

    def _apply_custom_conversion_rate(self, payment_vals):
        """
        Adjust payment values based on custom conversion rate for foreign currency transactions.
        """
        self.ensure_one()

        # Get the adjusted amount using the custom conversion rate
        adjusted_amount = self.source_amount_currency * self.custom_conversion_rate

        # Update the payment values
        payment_vals.update({
            'amount': adjusted_amount,
            'custom_conversion_rate': self.custom_conversion_rate,
        })

        # Create a journal entry to account for the currency adjustment
        self._create_conversion_rate_journal_entry(adjusted_amount, payment_vals)

    # def _create_conversion_rate_journal_entry(self, adjusted_amount, payment_vals):
    #     """
    #     Create a journal entry to account for the custom conversion rate adjustment.
    #     """
    #     self.ensure_one()
    #
    #     # Calculate the difference due to the custom conversion rate
    #     original_amount = self.source_amount_currency
    #     rate_difference = adjusted_amount - original_amount
    #
    #     if not rate_difference:
    #         return

    def _create_payment_vals_from_wizard(self, batch_result):
        """
        Override the method to include custom_conversion_rate in the payment values.
        """
        payment_vals = super(AccountPaymentRegisterInherit, self)._create_payment_vals_from_wizard(batch_result)

        # Apply custom conversion rate if set
        if self.custom_conversion_rate != 0 and self.currency_id != self.company_currency_id:
            # Adjust the amount using the custom conversion rate
            # adjusted_amount = self.amount * self.custom_conversion_rate

            # Update the payment values with the adjusted amount and custom conversion rate
            payment_vals.update({
                # 'amount': adjusted_amount,
                'custom_currency_rate': self.custom_conversion_rate,
            })

        return payment_vals


class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'

    custom_currency_rate = fields.Float(string="Custom Conversion Rate", default=1.0)

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        """
        Override to apply custom currency conversion on foreign purchases.
        """
        self.ensure_one()

        # Base move lines from super
        line_vals_list = super()._prepare_move_line_default_vals(write_off_line_vals, force_balance)

        account_move_obj = self.move_id
        if not account_move_obj:
            return line_vals_list

        conversion_rate = account_move_obj.custom_conversion_rate or 1.0

        if account_move_obj.move_type == 'in_invoice' \
                and any(
            l.purchase_line_id.order_id.purchase_process == 'foreign_purchase' for l in account_move_obj.line_ids) \
                and conversion_rate != 1.0 \
                and self.currency_id != self.company_id.currency_id:

            for line_vals in line_vals_list:
                # Modify debit/credit based on conversion rate
                if abs(line_vals.get('amount_currency', 0.0)) not in [0.0, line_vals.get('debit', 0.0)] \
                        and abs(line_vals.get('amount_currency', 0.0)) not in [0.0, line_vals.get('credit', 0.0)]:

                    if line_vals.get('debit', 0.0) > 0.0:
                        line_vals['debit'] = abs(line_vals['amount_currency']) * conversion_rate
                    if line_vals.get('credit', 0.0) > 0.0:
                        line_vals['credit'] = abs(line_vals['amount_currency']) * conversion_rate
                else:
                    line_vals['debit'] = line_vals.get('debit', 0.0) * conversion_rate
                    line_vals['credit'] = line_vals.get('credit', 0.0) * conversion_rate

        return line_vals_list


class CurrencyRateInherited(models.Model):
    _inherit = 'res.currency'

    # def _convert(self, from_amount, to_currency, company=None, date=None,
    #              round=True):  # noqa: A002 builtin-argument-shadowing
    #     res = super()._convert(from_amount, to_currency, company=company, date=date, round=round)
    #
    #     if self.env.context.get('active_model', None) == 'purchase.order':
    #         po = self.env['purchase.order'].browse(self.env.context.get('active_id', None))
    #
    #         if from_amount:
    #             if to_currency.id == po.company_id.currency_id.id:
    #                 to_amount = from_amount * po.local_currency
    #
    #                 res = to_currency.round(to_amount) if round else to_amount
    #         else:
    #             return 0.0
    #
    #             # apply rounding
    #
    #     return res

    def _convert(self, from_amount, to_currency, company=None, date=None, round=True):
        res = super()._convert(from_amount, to_currency, company=company, date=date, round=round)

        po = None
        lc_shipment = None

        # Check if directly from purchase.order
        if self.env.context.get('active_model') == 'purchase.order':
            po = self.env['purchase.order'].browse(self.env.context.get('active_id'))

        # If from stock.picking, try to get PO via picking > move_lines > purchase_line_id > order_id
        elif self.env.context.get('active_model') == 'stock.picking':
            picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
            po = picking.mapped('move_ids.purchase_line_id.order_id')[:1]

        # If from Letter of Credit, resolve related PO
        elif self.env.context.get('active_model') == 'letter.credit':
            letter = self.env['letter.credit'].browse(self.env.context.get('active_id'))
            po = letter.po_id if letter else None

        # If from LC Shipment, resolve related LC for conversion
        elif self.env.context.get('active_model') == 'lc.shipment':
            lc_shipment = self.env['lc.shipment'].browse(self.env.context.get('active_id'))

        # ----- Apply custom conversion -----
        if po and from_amount and to_currency.id == po.company_id.currency_id.id:
            # Use PO's local_currency
            to_amount = from_amount * po.local_currency
            res = to_currency.round(to_amount) if round else to_amount

        elif lc_shipment and from_amount and to_currency.id == lc_shipment.company_id.currency_id.id:
            # Use LC Shipment's related local_currency (via lc_id)
            to_amount = from_amount * lc_shipment.local_currency
            res = to_currency.round(to_amount) if round else to_amount

        return res