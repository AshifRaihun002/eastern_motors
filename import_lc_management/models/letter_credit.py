from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime


class LetterOfCredit(models.Model):
    _name = "letter.credit"
    _description = "Letter of Credit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    def _default_warehouse_id(self):
        """Return the default warehouse for the current user and company."""
        warehouse = self.env.user.property_warehouse_id
        if warehouse and warehouse.company_id == self.env.company:
            return warehouse

        # Fallback: search for any warehouse in the current company
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        return warehouse or False

    name = fields.Char(
        string="Letter of Credit",
        default=lambda s: _("New"),
        index="trigram",
        copy=False,
        readonly=True,
        required=True,
    )

    po_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        copy=True,
        index=True,
        readonly=False,
        domain="[('state', '=', 'purchase'), ('company_id', '=', company_id)]",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        check_company=True,
        readonly=True,
        copy=False,
    )

    purchase_process = fields.Selection(
        [
            ('local_purchase', 'Local'),
            ('foreign_purchase', 'Foreign')
        ],
        string='Currency Type',
        default='foreign_purchase',
        required=False
    )

    # requisition_id = fields.Many2many(
    #     "requisition.master",
    #     string="Requisition",
    #     copy=True,
    #     index=True,
    #     readonly=False,
    #     domain="[('state', '=', 'done'), ('company_id', '=', company_id)]", )
    origin = fields.Char(string="Source Document", tracking=True)
    lc_number = fields.Char(string="L/C Number", copy=False, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Vendor", tracking=True)
    related_partner_id = fields.Many2one(
        "res.partner", string="Beneficiary Name", tracking=True)
    ordering_date = fields.Date(string="Ordering Date", tracking=True)
    date_end = fields.Datetime(string="Offer Agreement Deadline", tracking=True)
    schedule_date = fields.Date(
        string="Delivery Date",
        tracking=True,
        help="The expected and scheduled delivery date where all the products are received",
    )
    description = fields.Text(string="Description", tracking=True)
    purchase_ids = fields.One2many("purchase.order", "lc_id", string="Purchase Orders", copy=False)
    lc_lines = fields.One2many("letter.credit.line", "lc_id", string="Products to Purchase", copy=True, tracking=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirm", "Confirmed"),
            ("approve", "Rate Approved"),
            ("lc_open", "LC Opening"),
            ("lc_document", "LC Paid"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="State",
        index=True,
        tracking=True,
        copy=False,
        default="draft",
        readonly=True,
    )

    advise_bank = fields.Char(string="Advising Bank", tracking=True)
    issue_bank = fields.Many2one("res.bank", string="Issuing Bank", tracking=True)
    port_land = fields.Char(string="Port of Land", tracking=True)
    port_destination = fields.Char(string="Port of Destination", tracking=True)
    proforma_invoice = fields.Char(string="PI Number", size=100, copy=False, tracking=True)
    customer_invoice = fields.Char(string="CI Number", size=100, copy=False, tracking=True)
    opening_date = fields.Date(string="LC Opening Date", tracking=True)
    last_shipment_date = fields.Date(string="Last Date of Shipment", tracking=True)
    expire_date = fields.Date(string="LC Expire Date", tracking=True)
    internal_notes = fields.Html("Internal Notes")

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one('res.currency', string='Account Currency', tracking=True)
    local_currency = fields.Float(string="Conversion Rate", default=0.0, tracking=True)
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        domain="[('company_id', '=?', company_id)]",
        check_company=True,
        index=True,
        required=True,
        readonly=True,
        help="Location where the system will look for components.",
        default=_default_warehouse_id,
    )
    lc_journal_id = fields.Many2one(
        'account.journal',
        string="Custom Duty Journal"
    )
    add_journal_id = fields.Many2one(
        'account.journal',
        string="Additional Journal"
    )
    add_payment_entry = fields.Many2one('account.move', string="Additional Duty Payment", readonly=True)
    lc_margin_acc = fields.Many2one(
        'account.account',
        string="LC Margin Acc",
        domain="[('account_type', '=', 'asset_current')]"
    )
    lc_margin_journal = fields.Many2one(
        'account.journal',
        string="Margin Journal",
        domain = "[('type', 'in', ['bank', 'cash'])]"
    )
    lc_vendor_payment_journal = fields.Many2one(
        'account.journal',
        string="Vendor Journal"
    )
    po_count = fields.Integer(string="Purchase Order Count", compute="_compute_purchase_related")
    offer_count = fields.Integer(string="Quotation Count", compute="_compute_purchase_related")
    picking_ready_count = fields.Integer(string="Receipt Ready Count", compute="_compute_incoming_picking_count")
    picking_done_count = fields.Integer(string="Receipt Done Count", compute="_compute_incoming_picking_count")
    landed_cost_count = fields.Integer(string="Landed Cost Count", compute="_compute_incoming_picking_count")
    landed_cost_posted_count = fields.Integer(string="Landed Cost Posted Count",
                                              compute="_compute_incoming_picking_count")
    landed_cost_actual_count = fields.Integer(string="Landed Cost Actual Count",
                                              compute="_compute_incoming_picking_count")

    shipment_ids = fields.One2many(
        "lc.shipment",
        "lc_id",
        string="Shipments",
        copy=False
    )

    shipment_count = fields.Integer(
        string="Shipment Count",
        compute="_compute_shipment_count"
    )

    lc_value = fields.Monetary(string="LC value(foreign)", tracking=True, currency_field='currency_id')
    lc_value_bdt = fields.Float(string="LC Value(BDT)", tracking=True, compute='_compute_lc_value_bdt')
    lc_margin_amount = fields.Monetary(string="LC Margin Value based on LC Value", compute="_compute_lc_margin", store=True, currency_field="currency_id")

    @api.constrains('schedule_date', 'expire_date')
    def _check_delivery_before_expiration(self):
        for record in self:
            if record.schedule_date and record.expire_date:
                if record.schedule_date > record.expire_date:
                    raise ValidationError(
                        "Delivery Date must be before the LC Expire Date!"
                    )
    @api.depends('lc_margin', 'lc_value')
    def _compute_lc_margin(self):
        for rec in self:
            rec.lc_margin_amount = (
                                          rec.lc_value * rec.lc_margin) / 100.0 if rec.lc_value and rec.lc_margin else 0.0


    @api.depends('lc_margin_currency_rate', 'lc_value')
    def _compute_lc_value_bdt(self):
        for record in self:
            record.lc_value_bdt = record.lc_margin_currency_rate * record.lc_value






    def get_lc_cost_line_values(self):
        """Auto-fill those fields that are related to the LC product"""
        self.ensure_one()
        lc_product_ids = self.lc_lines.mapped('product_id')
        if not lc_product_ids:
            return

        lc_templates = self.env['landed.cost.template'].search([('product_id', 'in', lc_product_ids.ids)])
        if not lc_templates:
            return

        lc_cost_line_vals = []
        for template in lc_templates:
            for line in template.cost_lines:
                lc_cost_line_vals.append((
                    0, 0, {
                        'lc_id': self.id,
                        'lc_product_id': template.product_id.id,
                        'product_id': line.product_id.id,
                        'landed_cost_type': line.landed_cost_type,
                        'split_method': line.split_method,
                        'account_id': line.account_id.id,
                        'amount': line.price_unit,
                    }
                ))

        # Write the One2many field with new lines
        if lc_cost_line_vals:
            self.lc_cost_line_ids = None
            self.write({'lc_cost_line_ids': lc_cost_line_vals})

        # Return action to reload current record
        return {
            'name': _('Letter of Credit'),
            'view_mode': 'form',
            'res_model': 'letter.credit',
            'res_id': self.id,
            'type': 'ir.actions.act_window'
        }

    def _compute_shipment_count(self):
        for lc in self:
            lc.shipment_count = len(lc.shipment_ids)

    def action_create_shipment(self):
        self.ensure_one()

        # Prepare wizard lines with available quantities
        wizard_lines = []
        for line in self.lc_lines:
            if line.remaining_qty > 0:
                wizard_lines.append((0, 0, {
                    'lc_line_id': line.id,
                    'quantity': 0.0  # Default to 0
                }))

        if not wizard_lines:
            raise UserError(_("No products available for shipment."))

        # Create and return wizard action
        wizard = self.env['lc.shipment.wizard'].create({
            'lc_id': self.id,
            'shipment_line_ids': wizard_lines
        })

        return {
            'name': _('Create LC Shipment'),
            'view_mode': 'form',
            'res_model': 'lc.shipment.wizard',
            'res_id': wizard.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': self.env.context,
        }

    def action_view_shipments(self):
        self.ensure_one()
        action = {
            'name': _('LC Shipments'),
            'type': 'ir.actions.act_window',
            'res_model': 'lc.shipment',
            'view_mode': 'list,form',
            'domain': [('lc_id', '=', self.id)],
            'context': {
                'default_lc_id': self.id,
                'create': True,
                'edit': True,
            },
        }

        # If there's only one shipment, open it in form view directly
        # if self.shipment_count == 1:
        #     action['view_mode'] = 'form'
        #     action['res_id'] = self.shipment_ids[0].id
        #     action['views'] = [(False, 'form')]

        return action

    @api.depends('lc_lines.price_subtotal')
    def _compute_amount_total(self):
        for lc in self:
            lc.amount_total = sum(line.price_subtotal for line in lc.lc_lines)

    amount_total = fields.Float(string="Total Amount",
                                compute="_compute_amount_total",
                                store=True,
                                )

    notes = fields.Text(string='Terms and Conditions')

    total_landed_cost = fields.Monetary(
        string="Total Landed Cost",
        compute="_compute_total_landed_cost",
        store=True,
        currency_field='company_currency_id'
    )
    lc_margin = fields.Float(
        string="LC Margin (%)",
        help="Percentage margin on total amount",
        default=0.0,
        tracking=True,
    )
    lc_margin_currency_rate = fields.Float(string="Margin Conversion Rate", default=0.0, tracking=True)

    lc_margin_value = fields.Monetary(
        string="LC Margin Amount",
        compute="_compute_lc_margin_value",
        store=True,
        currency_field="currency_id",
        help="Calculated margin value based on total amount and LC margin %",
    )
    margin_value_bdt = fields.Monetary(
        string="Margin Value in BDT",
        compute="_compute_margin_value_bdt",
        store=False,
        currency_field="company_currency_id",
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string="Company Currency",
        readonly=True,
        compute="_compute_company_currency",
        store=True
    )
    lc_cost_line_ids = fields.One2many(
        "letter.credit.cost.line",
        "lc_id",
        string="LC Landed Cost Lines"
    )

    voucher_number = fields.Many2one('account.move', string="Custom Duty Payment", readonly=True)
    lc_margin_voucher_number = fields.Many2one('account.move', string="Margin Payment", readonly=False)
    lc_vendor_voucher = fields.Many2one('account.move', string="Vendor Payment", readonly=False)

    lc_total_amount_bdt = fields.Float(
        string="Total Amount (BDT)",
        compute="_compute_lc_total_amount_bdt",
        readonly=False,
        store=True,
        tracking=True,
    )
    payment_id = fields.Many2one('account.payment', string="Vendor Payment Info")
    add_partner_id = fields.Many2one('res.partner', string='Vendor for Additional Charge')

    # loan_id = fields.Many2one('loan.management', string="Related Loan", readonly=True, copy=False)

    payment_ids = fields.Many2many('account.payment', string="Vendor Payments", readonly=True)

    payment_count = fields.Integer(compute='_compute_payment_count', string="Payment Count")
    add_charge_vendor_bill = fields.Many2many(
        'account.move',
        'lc_vendor_bill_rel',
        'lc_id',
        'bill_id',
        string="Vendor Bills",
        domain=[('move_type', '=', 'in_invoice')],
        copy=False,
    )
    add_charge_vendor_bill_count = fields.Integer(
        string="Vendor Bill Count",
        compute="_compute_add_charge_vendor_bill_count"
    )

    custom_duty_journals = fields.Many2many(
        'account.move',
        'lc_custom_duty_move_rel',
        'lc_id',
        'move_id',
        string="Custom Duty Payment Entries",
        copy=False,
        readonly=True,
    )

    custom_duty_journal_count = fields.Integer(
        string="Custom Duty Journal Count",
        compute="_compute_custom_duty_journal_count",
    )

    insurance_no = fields.Char(string="Insurance NO:")
    insurance_amount = fields.Float(string="Insurance Amount")
    insurance_company = fields.Many2one("res.partner", string="Insurance Company", tracking=True)
    ins_cover_date = fields.Date(string="Insurance Cover Date")
    ins_cover_note = fields.Text(string="Insurance Cover Note")
    ins_acc_no = fields.Many2one('account.account',
        string="LC Insurance Acc",
        domain="[('account_type', '=', 'asset_current')]"
    )
    lc_ins_journal = fields.Many2one('account.journal',
                                     string="Insurance Payment Journal",
                                     domain="[('type', 'in', ['bank','cash'])]")
    insurance_payment_entry = fields.Many2one('account.move', string="Insurance Payment", readonly=False)
    bank_charge_amount = fields.Float(string="Bank Charge Amount")
    bank_acc_no = fields.Many2one('account.account',
                                 string="LC Bank Charge Acc",
                                 )

    bank_charge_journal = fields.Many2one(
        'account.journal',
        string="Bank Charge Journal",
        domain = "[('type', 'in', ['bank', 'cash'])]"
    )
    bank_charge_payment_entry = fields.Many2one('account.move', string="Bank Payment Entry", readonly=False)


    @api.depends('lc_cost_line_ids.amount')
    def _compute_total_landed_cost(self):
        for record in self:
            record.total_landed_cost = sum(record.lc_cost_line_ids.mapped('amount'))

    @api.depends('custom_duty_journals')
    def _compute_custom_duty_journal_count(self):
        for rec in self:
            rec.custom_duty_journal_count = len(rec.custom_duty_journals)

    def action_view_custom_duty_journals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Custom Duty Journal Entries',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.custom_duty_journals.ids)],
        }

    def open_custom_duty_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Custom Duty Journal Entry',
            'res_model': 'lc.custom.duty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lc_id': self.id,
                'default_journal_id': self.lc_journal_id.id if self.lc_journal_id else False,
            }
        }

    def _compute_add_charge_vendor_bill_count(self):
        for record in self:
            record.add_charge_vendor_bill_count = len(record.add_charge_vendor_bill)

    def action_view_add_charge_vendor_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Additional Vendor Bills',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.add_charge_vendor_bill.ids)],
            'context': {'create': False},
            'target': 'current',
        }

    def action_open_vendor_bill_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Vendor Bill',
            'res_model': 'lc.vendor.bill.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('import_lc_management.view_lc_vendor_bill_wizard_form').id,
            'target': 'new',
            'context': {
                'default_lc_id': self.id,
            },
        }

    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    def action_open_payment_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'lc.vendor.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lc_id': self.id,
            }
        }

    def action_view_vendor_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Payments',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payment_ids.ids)],
        }

    @api.depends('amount_total', 'local_currency')
    def _compute_lc_total_amount_bdt(self):
        for lc in self:
            lc.lc_total_amount_bdt = lc.amount_total * lc.local_currency if lc.local_currency else 0.0

    @api.depends('lc_margin_value', 'local_currency')
    def _compute_margin_value_bdt(self):
        for rec in self:
            rec.margin_value_bdt = rec.lc_margin_amount * rec.lc_margin_currency_rate if rec.lc_margin_amount and rec.lc_margin_currency_rate else 0.0

    @api.depends('company_id')
    def _compute_company_currency(self):
        for rec in self:
            rec.company_currency_id = rec.company_id.currency_id

    @api.depends('lc_margin', 'amount_total')
    def _compute_lc_margin_value(self):
        for rec in self:
            rec.lc_margin_value = (
                                          rec.amount_total * rec.lc_margin) / 100.0 if rec.amount_total and rec.lc_margin else 0.0

    _sql_constraints = [
        ("name", "unique (name)", "The name of the Consumption Order must be unique!"),
        ("lc_number", "unique (lc_number)", "The LC Number must be unique!"),
    ]

    @api.depends("po_id.state")
    def _compute_purchase_related(self):
        for lc in self:
            purchases = lc.po_id.filtered(lambda po: po.state in ("purchase", "done"))
            offers = lc.po_id.filtered(lambda po: po.state not in ("purchase", "done"))

            state = lc.state
            if lc.state == "confirm" and purchases:
                state = "confirm"
            elif lc.state in ("approve", "done") and not purchases:
                state = "confirm"

            lc.update(
                {"po_count": len(purchases), "offer_count": len(offers), "state": state}
            )

    @api.depends("purchase_ids.picking_ids")
    def _compute_incoming_picking_count(self):
        for lc in self:
            pickings = lc.purchase_ids.filtered(lambda po: po.state in ("purchase", "done")).mapped(
                "picking_ids").filtered(lambda pi: pi.state != "cancel")
            landed_costs = self.env["stock.landed.cost"].search([("picking_ids", "in", pickings.ids)])

            lc.picking_ready_count = len(pickings.filtered(lambda pi: pi.state != "done"))
            lc.picking_done_count = len(pickings.filtered(lambda pi: pi.state == "done"))
            lc.landed_cost_count = len(landed_costs.filtered(lambda lc: lc.state != "cancel"))
            lc.landed_cost_posted_count = len(landed_costs.filtered(lambda lc: lc.state == "done"))
            lc.landed_cost_actual_count = len(landed_costs.filtered(lambda lc: lc.state == "actual"))

    def action_view_picking(self):
        self.ensure_one()
        purchases = self.po_id.filtered(lambda po: po.state in ("purchase", "done"))
        pickings = purchases.picking_ids.filtered(lambda pi: pi.state != "cancel")

        if not purchases or not pickings or self.state != "lc_open":
            return

        return purchases[0]._get_action_view_picking(pickings)

    def action_view_landed_cost(self):
        self.ensure_one()

        landed_costs = self.env["stock.landed.cost"].search([("lc_id", "=", self.id)])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Landed Costs',
            'res_model': 'stock.landed.cost',
            'view_mode': 'list,form',
            'domain': [('lc_id', '=', self.id)],
            'context': {
                'default_lc_id': self.id,
                'default_company_id': self.company_id.id,
            },
            'res_id': landed_costs.id if len(landed_costs) == 1 else False,
        }

    def action_confirm(self):
        without_lc_lines = self.filtered(lambda rec: not rec.lc_lines)

        if without_lc_lines:
            raise UserError(
                _(
                    "You cannot confirm without product lines. %s"
                    % without_lc_lines.mapped("name")
                )
            )
        invalid_lc_value = self.filtered(lambda rec: rec.lc_value <= 0)
        if invalid_lc_value:
            raise UserError(
                _(
                    "You cannot confirm with LC Value less than or equal to zero. %s"
                    % ", ".join(invalid_lc_value.mapped("name"))
                )
            )

        self.write({"state": "confirm"})

    def action_cancel(self):
        """Prevent cancel if LC is in restricted states."""
        restricted_states = ['done', 'lc_open', 'lc_document', 'confirm']  # Add more as needed

        restricted_lcs = self.filtered(lambda lc: lc.state in restricted_states)

        if restricted_lcs:
            raise UserError(_(
                "You cannot cancel a Letter of Credit in state(s): %s.\n%s" % (
                    ', '.join(set(restricted_lcs.mapped('state'))),
                    ', '.join(restricted_lcs.mapped('name'))
                )
            ))

        self.write({'state': 'cancel'})

    def action_payment_lc_bank_charge(self):
        for record in self:
            # Validate required fields
            if not record.bank_charge_journal:
                raise UserError("Please define a Journal for Bank Charge Payment")
            if not record.bank_acc_no:
                raise UserError("Please Define an Account for Bank Charge Payment")
            if not record.bank_charge_amount:
                raise UserError("Please Enter an Amount for Bank Charge Payment")

            credit_account = record.bank_charge_journal.default_account_id
            if not credit_account:
                raise UserError("The selected Bank Charge Journal does not have a default Account")

            # Prepare move values
            mov_vals = {
                'journal_id': record.bank_charge_journal.id,
                'ref': f'LC Bank Charge: {record.name}',
                'date': fields.Date.context_today(self),
                'line_ids': [
                    (0, 0, {
                        'name': f"LC Bank Charge for {record.name}",
                        'account_id': record.bank_acc_no.id,
                        'debit': record.bank_charge_amount,
                        'credit': 0.0,
                        'currency_id': record.currency_id.id if record.currency_id else False,
                    }),
                    (0, 0, {
                        'name': f"LC Bank Charge for {record.name}",
                        'account_id': credit_account.id,
                        'debit': 0.0,
                        'credit': record.bank_charge_amount,
                        'currency_id': record.currency_id.id if record.currency_id else False,
                    }),
                ]
            }

            try:
                # Create and post journal entry
                move = self.env['account.move'].create(mov_vals)
                move.action_post()

                # Save reference to the record
                record.bank_charge_payment_entry = move.id

                # Post message
                record.message_post(
                    body=f"LC Bank Charge Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created."
                )

                # Return form view of created move
                return {
                    'name': 'LC Bank Charge Journal Entry',
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': move.id,
                    'view_mode': 'form',
                }

            except Exception as e:
                raise UserError(f"Failed to create or post bank charge journal entry: {str(e)}")

    def action_create_vendor_payment(self):
        for record in self:
            if not record.lc_journal_id:
                raise UserError("Please define a Journal in the LC record.")

            # Filter CNF charge lines
            cnf_lines = record.lc_cost_line_ids.filtered(
                lambda l: l.amount > 0 and l.landed_cost_type == 'cnf_charge'
            )

            if not cnf_lines:
                raise UserError("No 'CNF Charge' lines with amount found.")

            # Sum all cnf_charge line amounts
            total_amount = sum(cnf_lines.mapped('amount'))

            # Determine partner: (Assuming you have a field or logic)
            # For now, raise error if not explicitly given
            partner = record.partner_id if hasattr(record, 'partner_id') and record.partner_id else None
            if not partner:
                raise UserError("Please assign a Vendor to the LC record.")

            payment_vals = {
                'partner_id': partner.id,
                'partner_type': 'supplier',
                'payment_type': 'outbound',
                'journal_id': record.lc_journal_id.id,
                'amount': total_amount,
                'currency_id': record.company_id.currency_id.id,
                'date': fields.Date.context_today(self),
                'memo': f'Additional Charges Payment for LC: {record.name}',
            }

            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()  # comment out this line if you want to keep it in draft

            record.payment_id = payment.id

            record.message_post(
                body=f"Vendor Payment <a href='/web#id={payment.id}&model=account.payment'>{payment.name}</a> created.")

            return {
                'name': 'Vendor Payment',
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'res_id': payment.id,
                'view_mode': 'form',
            }

    def action_create_vendor_bill(self):
        for record in self:
            if not record.add_partner_id:
                raise UserError("Please assign an Additional Charge Vendor (add_partner_id).")

            # Filter only CNF charge lines
            cnf_lines = record.lc_cost_line_ids.filtered(
                lambda l: l.amount > 0 and l.landed_cost_type == 'cnf_charge'
            )

            if not cnf_lines:
                raise UserError("No 'CNF Charge' lines with amount found.")

            invoice_lines = []
            for line in cnf_lines:
                if not line.account_id:
                    raise UserError(f"No account set for CNF line '{line.product_id.name or line.id}'.")
                if not line.product_id:
                    raise UserError(f"No product selected for CNF line with amount {line.amount}.")

                invoice_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.name,
                    'quantity': 1,
                    'price_unit': line.amount,
                    'account_id': line.account_id.id,
                    'currency_id': record.currency_id.id,
                }))

            move_vals = {
                'move_type': 'in_invoice',
                'partner_id': record.add_partner_id.id,
                'invoice_date': fields.Date.context_today(self),
                'invoice_origin': record.name,
                'company_id': record.company_id.id,
                'currency_id': record.company_id.currency_id.id,
                'invoice_line_ids': invoice_lines,
            }

            bill = self.env['account.move'].with_company(record.company_id).create(move_vals)
            record.add_charge_vendor_bill = bill.id

            record.message_post(
                body=f"Vendor Bill <a href='/web#id={bill.id}&model=account.move'>{bill.name}</a> created from CNF Charges."
            )

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': bill.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'force_company': record.company_id.id},
            }

    def action_draft(self):
        self.ensure_one()
        if self.state == 'cancel':
            raise UserError("You cannot reset to Draft from Cancelled state.")
        self.write({'state': 'draft'})

    def action_done(self):
        if self.filtered(lambda lc: lc.state != "lc_document"):
            raise ValidationError(
                _("You can only complete the L/C once it has been LC Document.")
            )

        invalid_records = self.filtered(
            lambda lc: not all(
                [
                    lc.expire_date,
                    lc.opening_date,
                    lc.lc_lines,
                    lc.advise_bank,
                    lc.issue_bank,
                    lc.port_land,
                    lc.port_destination,
                    lc.proforma_invoice,
                ]
            )
        )

        if invalid_records:
            if len(invalid_records) > 1:
                raise ValidationError(
                    _(
                        "Missing required fields. Please provide all required information.\n%s"
                        % invalid_records.mapped("name")
                    )
                )
            else:
                raise ValidationError(
                    _("Missing required fields. Please provide all required information.")
                )

        for rec in self:
            rec._action_done()

    def action_new_landed_cost(self):
        self.ensure_one()

        # Prepare landed cost lines from your LC cost lines with product filter
        lc_lines = []
        for line in self.lc_cost_line_ids.filtered(lambda l: l.product_id.landed_cost_ok):
            lc_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'price_unit': line.amount,
                'account_id': line.product_id.property_account_expense_id.id or line.account_id.id,
                'split_method': 'equal',  # You can change this to dynamic if needed
                'name': line.product_id.name or line.landed_cost_type,
            }))

        return {
            "name": _("New Landed Cost"),
            "type": "ir.actions.act_window",
            "target": "current",
            "view_mode": "form",
            "res_model": "stock.landed.cost",
            "context": {
                "default_picking_ids": self.po_id.filtered(
                    lambda po: po.state in ("purchase", "done")
                )
                .mapped("picking_ids")
                .filtered(lambda pi: pi.state == "done")
                .ids,
                "default_lc_id": self.id,
                "default_company_id": self.company_id.id,
                "default_cost_lines": lc_lines,
            },
        }

    def action_view_po(self):
        self.ensure_one()

        po_id = self.po_id.ids if self.po_id else False

        result = self.env["ir.actions.actions"]._for_xml_id(
            "purchase.purchase_form_action"
        )
        # Override the context to remove default filtering
        result["context"] = {
            "default_lc_id": self.id,
            "default_origin": self.name,
            "id": po_id,
        }
        # Choose view mode accordingly
        if (self.po_count + self.offer_count) > 1:
            result["domain"] = [("lc_id", "=", self.id)]
        elif (self.po_count + self.offer_count) == 1:
            res = self.env.ref("purchase.purchase_order_form", False)
            form_view = [(res and res.id or False, "form")]
            result["views"] = form_view + [
                (state, view)
                for state, view in result.get("views", [])
                if view != "form"
            ]
            result["res_id"] = self.po_id.filtered(
                lambda po: po.state != "cancel"
            ).ids[0]

        return result

    def _action_done(self):
        self.ensure_one()

        if not self.lc_number:
            raise ValidationError(
                _("Please provide L/C Number for setting status of L/C to done.")
            )

        done_po = self.po_id.filtered(
            lambda po: po.state in ("purchase", "done")
        )

        if not done_po:
            raise ValidationError(_("You must have at least one purchase order."))

        for po in done_po:
            po_partner = po.partner_id

            if po_partner:
                vals = {
                    # Remove or handle the stock location fields
                    "property_product_pricelist": po_partner.property_product_pricelist.id if po_partner.property_product_pricelist else False,
                    "credit_limit": po_partner.credit_limit,
                    "total_due": po_partner.total_due,
                    "total_overdue": po_partner.total_overdue,
                    "user_id": po_partner.user_id.id if po_partner.user_id else False,
                    "trust": po_partner.trust,
                    "company_type": po_partner.company_type,
                }
                # Create the new partner first
                new_partner = po_partner
                # Then set the stock locations separately
                if po_partner.property_stock_customer:
                    new_partner.property_stock_customer = po_partner.property_stock_customer.id
                if po_partner.property_stock_supplier:
                    new_partner.property_stock_supplier = po_partner.property_stock_supplier.id

                # po.partner_id = new_partner
                po.picking_ids.write({"partner_id": new_partner.id})

        keep_lc_offer = (
            self.env["ir.config_parameter"].sudo().get_param("brac_lc_process.keep_lc_offer")
        )

        lc_offers = self.purchase_ids.filtered(
            lambda po: po.state not in ("purchase", "done")
        )

        if lc_offers and not keep_lc_offer:
            lc_offers.button_cancel()

            for offer in lc_offers:
                offer.message_post(
                    body=_(
                        "Cancelled by the L/C associated with this quotation. Reason: L/C Done"
                    )
                )

        self.write({"state": "done"})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        for order in self:
            if order.state == "done":
                raise UserError(_("You cannot delete a completed L/C."))

            if order.state not in ("draft", "cancel"):
                raise UserError(
                    _(
                        "You cannot delete an L/C once it has been confirmed. You must first cancel it."
                    )
                )

    def copy(self, default=None):
        default = dict(default or {})
        # Generate a new name for the L/C
        copied_lc = super().copy(default)
        copied_lc._message_log(
            body=_("This entry has been duplicated from %s", self._get_html_link())
        )

        return copied_lc


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["name"] = self.env["ir.sequence"].next_by_code("lc_name") or _("New")

        return super().create(vals_list)

    def action_create_lc_journal_entry(self):
        for record in self:
            if not record.lc_journal_id:
                raise UserError("Please define a Journal in the LC record.")

            # Include only lines with landed_cost_type == 'custom_duty'
            lc_lines = record.lc_cost_line_ids.filtered(
                lambda l: l.amount > 0 and l.landed_cost_type == 'custom_duty'
            )

            if not lc_lines:
                raise UserError("No 'Custom Duty' cost lines with amount found.")

            move_vals = {
                'journal_id': record.lc_journal_id.id,
                'ref': f'LC: {record.name}',
                'date': fields.Date.context_today(self),
                'line_ids': [],
            }

            total_debit = 0.0

            # Debit lines
            for line in lc_lines:
                if not line.account_id:
                    raise UserError(f"Missing account on cost line: {line.product_id.display_name}")
                move_vals['line_ids'].append((0, 0, {
                    'name': line.product_id.display_name or line.landed_cost_type,
                    'account_id': line.account_id.id,
                    'debit': line.amount,
                    'credit': 0.0,
                    'currency_id': line.currency_id.id if line.currency_id else False,
                }))
                total_debit += line.amount

            # Credit line
            credit_account = record.lc_journal_id.default_account_id
            if not credit_account:
                raise UserError("The selected journal does not have a default account.")

            move_vals['line_ids'].append((0, 0, {
                'name': 'Landed Cost Credit',
                'account_id': credit_account.id,
                'debit': 0.0,
                'credit': total_debit,
                'currency_id': lc_lines[0].currency_id.id if lc_lines and lc_lines[0].currency_id else False,
            }))

            # Create and post journal entry
            move = self.env['account.move'].create(move_vals)
            move.action_post()
            record.voucher_number = move.id

            record.message_post(
                body=f"Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created.")

            return {
                'name': 'Landed Cost Journal Entry',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': move.id,
                'view_mode': 'form',
            }

    def action_create_lc_margin_entry(self):
        for record in self:
            if not record.lc_margin_journal:
                raise UserError("Please define a Margin Journal on the LC record.")
            if not record.lc_margin_acc:
                raise UserError("Please define the LC Margin Account.")
            if not record.margin_value_bdt or record.margin_value_bdt <= 0:
                raise UserError("Margin Value must be greater than 0 to create a journal entry.")

            credit_account = record.lc_margin_journal.default_account_id
            if not credit_account:
                raise UserError("The selected margin journal does not have a default account.")

            move_vals = {
                'journal_id': record.lc_margin_journal.id,
                'ref': f'LC Margin: {record.name}',
                'date': fields.Date.context_today(self),
                'line_ids': [
                    # Debit: LC Margin Account
                    (0, 0, {
                        'name': f"LC Margin for {record.name}",
                        'account_id': record.lc_margin_acc.id,
                        'debit': record.margin_value_bdt,
                        'credit': 0.0,
                        'currency_id': record.currency_id.id if record.currency_id else False,
                    }),
                    # Credit: Journal's default account
                    (0, 0, {
                        'name': f"LC Margin for {record.name}",
                        'account_id': credit_account.id,
                        'debit': 0.0,
                        'credit': record.margin_value_bdt,
                        'currency_id': record.currency_id.id if record.currency_id else False,
                    }),
                ],
            }

            try:
                move = self.env['account.move'].create(move_vals)
                move.action_post()

                # Only update state after successful post
                record.lc_margin_voucher_number = move.id
                record.state = 'lc_open'

                record.message_post(
                    body=f"LC Margin Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created.")

                return {
                    'name': 'LC Margin Journal Entry',
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': move.id,
                    'view_mode': 'form',
                }

            except Exception as e:
                raise UserError(f"Failed to create or post journal entry: {str(e)}")

    def action_payment_lc_insurance(self):
        for record in self:
            if not record.lc_ins_journal:
                raise UserError("Please define a Journal for Insurance Payment")
            if not record.ins_acc_no:
                raise UserError("Please Define a Account for Insurance Payment")
            if not record.insurance_amount:
                raise UserError("Please Enter a Amount for Insurance Payment")

            credit_account = record.lc_ins_journal.default_account_id
            if not credit_account:
                raise UserError("The selected Journal not have default ACC")
            mov_vals ={
                'journal_id': record.lc_ins_journal.id,
                'ref':f'LC Insurance:{record.name}',
                'date': fields.Date.context_today(self),
                'line_ids':[
                    (0,0,{
                        'name':f"LC Insurance for {record.name}",
                        'account_id': record.ins_acc_no.id,
                        'debit': record.insurance_amount,
                        'credit':0.0,
                        'currency_id': record.currency_id.id if record.currency_id else False,
                    }),
                    (0,0, {
                        'name':f"LC Insurance for {record.name}",
                        'account_id': credit_account.id,
                        'debit':0.0,
                        'credit': record.insurance_amount,
                        'currency_id': record.currency_id.id if record.currency_id else False
                    })

                ]

            }
            try:
                move = self.env['account.move'].create(mov_vals)
                move.action_post()

                record.insurance_payment_entry = move.id

                record.message_post(
                    body=f"LC Insurance Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created.")

                return {
                    'name': 'LC Insurance Journal Entry',
                    'type': 'ir.actions.act_window',
                    'res_model': 'account.move',
                    'res_id': move.id,
                    'view_mode': 'form',
                }

            except Exception as e:
                raise UserError(f"Failed to create or post journal entry: {str(e)}")



    # def action_create_lc_payment_entry(self):
    #     for record in self:
    #         if not record.partner_id:
    #             raise UserError("Vendor must be defined.")
    #
    #         if not record.lc_vendor_payment_journal:
    #             raise UserError("Vendor Payment Journal must be set.")
    #
    #         if not record.lc_vendor_payment_journal.default_account_id:
    #             raise UserError("The selected Vendor Journal does not have a default account.")
    #
    #         if record.lc_total_amount_bdt <= 0:
    #             raise UserError("LC Total Amount must be greater than 0.")
    #
    #         margin_amount = record.margin_value_bdt or 0.0
    #         total_amount = record.lc_total_amount_bdt
    #         bank_amount = total_amount - margin_amount
    #
    #         if bank_amount < 0:
    #             raise UserError("Bank amount cannot be negative. Check margin or total amounts.")
    #
    #         if margin_amount > 0 and not record.lc_margin_acc:
    #             raise UserError("LC Margin Account must be defined when margin amount is greater than 0.")
    #
    #         bank_account = record.lc_vendor_payment_journal.default_account_id
    #
    #         move_vals = {
    #             'journal_id': record.lc_vendor_payment_journal.id,
    #             'ref': f'LC Payment: {record.name}',
    #             'date': fields.Date.context_today(self),
    #             'line_ids': [],
    #         }
    #
    #         # CREDIT: Vendor Payable
    #         move_vals['line_ids'].append((0, 0, {
    #             'name': f"LC Payable to {record.partner_id.name}",
    #             'account_id': record.partner_id.property_account_payable_id.id,
    #             'partner_id': record.partner_id.id,
    #             'debit': total_amount,
    #             'credit': 0.0,
    #             'currency_id': record.currency_id.id if record.currency_id else False,
    #         }))
    #
    #         # DEBIT: LC Margin (if applicable)
    #         if margin_amount > 0:
    #             move_vals['line_ids'].append((0, 0, {
    #                 'name': f"LC Margin for {record.name}",
    #                 'account_id': record.lc_margin_acc.id,
    #                 'partner_id': record.partner_id.id,
    #                 'debit': 0.0,
    #                 'credit': margin_amount,
    #                 'currency_id': record.currency_id.id if record.currency_id else False,
    #             }))
    #
    #         # DEBIT: Bank/Cash (actual payment)
    #         if bank_amount > 0:
    #             move_vals['line_ids'].append((0, 0, {
    #                 'name': f"Bank Payment for LC {record.name}",
    #                 'account_id': bank_account.id,
    #                 'partner_id': record.partner_id.id,
    #                 'debit': 0.0,
    #                 'credit': bank_amount,
    #                 'currency_id': record.currency_id.id if record.currency_id else False,
    #             }))
    #
    #         # Create and post the journal entry
    #         move = self.env['account.move'].create(move_vals)
    #         move.action_post()
    #
    #         # Reconcile with earliest open vendor bill
    #         bill = self.env['account.move'].search([
    #             ('partner_id', '=', record.partner_id.id),
    #             ('move_type', '=', 'in_invoice'),
    #             ('state', '=', 'posted'),
    #             ('amount_residual', '>', 0),
    #         ], order='date asc', limit=1)
    #
    #         if bill:
    #             bill_lines = bill.line_ids.filtered(
    #                 lambda l: l.account_id == record.partner_id.property_account_payable_id and l.amount_residual > 0)
    #             payment_lines = move.line_ids.filtered(
    #                 lambda l: l.account_id == record.partner_id.property_account_payable_id and l.amount_residual > 0)
    #
    #             if bill_lines and payment_lines:
    #                 (bill_lines + payment_lines).reconcile()
    #
    #         # Save journal entry and update state
    #         record.lc_vendor_voucher = move.id
    #         record.state = 'lc_document'
    #
    #         # Log to chatter
    #         record.message_post(
    #             body=f"LC Payment Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created."
    #         )
    #
    #         return {
    #             'name': 'LC Payment Journal Entry',
    #             'type': 'ir.actions.act_window',
    #             'res_model': 'account.move',
    #             'res_id': move.id,
    #             'view_mode': 'form',
    #         }

    def action_create_lc_payment_entry(self):
        for record in self:
            if not record.partner_id:
                raise UserError("Vendor must be defined.")

            if not record.lc_vendor_payment_journal:
                raise UserError("Vendor Payment Journal must be set.")

            if not record.lc_vendor_payment_journal.default_account_id:
                raise UserError("The selected Vendor Journal does not have a default account.")

            if record.lc_total_amount_bdt <= 0:
                raise UserError("LC Total Amount must be greater than 0.")

            if not record.local_currency or record.local_currency <= 0:
                raise UserError("Conversion rate (Local Currency) must be set and greater than 0.")

            margin_amount_bdt = record.margin_value_bdt or 0.0
            total_amount_bdt = record.lc_total_amount_bdt
            bank_amount_bdt = total_amount_bdt - margin_amount_bdt

            if bank_amount_bdt < 0:
                raise UserError("Bank amount cannot be negative. Check margin or total amounts.")

            # Compute foreign amounts
            total_amount_foreign = total_amount_bdt / record.local_currency
            margin_amount_foreign = margin_amount_bdt / record.local_currency if margin_amount_bdt else 0.0
            bank_amount_foreign = bank_amount_bdt / record.local_currency

            bank_account = record.lc_vendor_payment_journal.default_account_id

            move_vals = {
                'journal_id': record.lc_vendor_payment_journal.id,
                'ref': f'LC Payment: {record.name}',
                'date': fields.Date.context_today(self),
                'currency_id': record.currency_id.id,
                'line_ids': [],
            }

            # DEBIT: Vendor Payable
            move_vals['line_ids'].append((0, 0, {
                'name': f"LC Payable to {record.partner_id.name}",
                'account_id': record.partner_id.property_account_payable_id.id,
                'partner_id': record.partner_id.id,
                'debit': total_amount_bdt,
                'credit': 0.0,
                'amount_currency': total_amount_foreign,  # Positive for debit
                'currency_id': record.currency_id.id,
            }))

            # CREDIT: LC Margin (if applicable)
            if margin_amount_bdt > 0:
                if not record.lc_margin_acc:
                    raise UserError("LC Margin Account must be defined when margin amount is greater than 0.")

                move_vals['line_ids'].append((0, 0, {
                    'name': f"LC Margin for {record.name}",
                    'account_id': record.lc_margin_acc.id,
                    'partner_id': record.partner_id.id,
                    'debit': 0.0,
                    'credit': margin_amount_bdt,
                    'amount_currency': -margin_amount_foreign,  # Negative for credit
                    'currency_id': record.currency_id.id,
                }))

            # CREDIT: Bank Payment
            if bank_amount_bdt > 0:
                move_vals['line_ids'].append((0, 0, {
                    'name': f"Bank Payment for LC {record.name}",
                    'account_id': bank_account.id,
                    'partner_id': record.partner_id.id,
                    'debit': 0.0,
                    'credit': bank_amount_bdt,
                    'amount_currency': -bank_amount_foreign,  # Negative for credit
                    'currency_id': record.currency_id.id,
                }))

            # Create and post journal entry
            move = self.env['account.move'].create(move_vals)
            move.action_post()

            # Reconcile with earliest open vendor bill
            bill = self.env['account.move'].search([
                ('partner_id', '=', record.partner_id.id),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('amount_residual', '>', 0),
            ], order='date asc', limit=1)

            if bill:
                bill_lines = bill.line_ids.filtered(
                    lambda l: l.account_id == record.partner_id.property_account_payable_id and l.amount_residual > 0)
                payment_lines = move.line_ids.filtered(
                    lambda l: l.account_id == record.partner_id.property_account_payable_id and l.amount_residual > 0)

                if bill_lines and payment_lines:
                    (bill_lines + payment_lines).reconcile()

            # Save journal entry reference
            record.lc_vendor_voucher = move.id
            record.state = 'lc_document'

            # Log to chatter
            record.message_post(
                body=f"LC Payment Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created."
            )

            return {
                'name': 'LC Payment Journal Entry',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': move.id,
                'view_mode': 'form',
            }


class LetterCreditLine(models.Model):
    _name = "letter.credit.line"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "L/C Line"
    _rec_name = "product_id"
    _order = "id desc"

    po_id = fields.Many2one("purchase.order", string="Purchase Order")
    purchase_line_id = fields.Many2one("purchase.order.line", string="Purchase Order Line",readonly=False, copy=True)

    lc_id = fields.Many2one(
        "letter.credit",
        string="L/C",
        required=True,
        index=True,
        ondelete="cascade",
        check_company=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        check_company=True,
    )
    default_code = fields.Char(
        string="Internal Reference", readonly=True, related="product_id.default_code"
    )
    product_uom = fields.Many2one(
        "uom.uom",
        string="Product Unit of Measure",
        compute="_compute_product_uom",
        store=True,
        readonly=False,
        precompute=True,
        required=True,
    )
    product_uom_category_id = fields.Many2one(
        related="product_id.uom_id",
        string="UoM Category",
        store=True,
        readonly=False
    )
    product_qty = fields.Float(
        string="Quantity", default=1.0, digits="Product Unit of Measure", required=True
    )
    ordered_qty = fields.Float(
        compute="_compute_ordered_qty", string="Ordered Quantities", store=True
    )
    # requisition_id = fields.Many2one('requisition.master', string='Requisition', tracking=True)
    # requisition_line_id = fields.Many2one(
    #     "requisition.product.service", string="Requisition Line", readonly=False, copy=True
    # )
    move_id = fields.Many2one(
        "stock.move", string="Downstream Move", copy=False, readonly=True
    )
    company_id = fields.Many2one(
        related="lc_id.company_id", store=True, index=True, readonly=True
    )
    price_unit = fields.Float(
        string='Unit Price', required=True, digits='Product Price', readonly=False, default=0.0)
    foreign_currency = fields.Float(string='Unit Rate(Local)', default=0.0)
    foreign_price_subtotal = fields.Float(string='Subtotal(Local)', default=0.0, compute='compute_foreign_currency',
                                          compute_sudo=True)
    company_currency_id = fields.Many2one(
        'res.currency',
        # compute='_compute_company_currency',
        string='Currency',
        store=True
    )

    price_subtotal = fields.Monetary(
        compute='_compute_amount',
        string='Subtotal',
        store=True,
        currency_field='company_currency_id'
    )

    remaining_qty = fields.Float(
        string="Remaining Quantity",
        compute='_compute_remaining_qty',
        store=True,
        digits='Product Unit of Measure'
    )

    # Also add shipped_qty field to track shipped quantities
    shipped_qty = fields.Float(
        string="Shipped Quantity",
        default=0.0,
        digits='Product Unit of Measure'
    )

    @api.depends('product_qty', 'shipped_qty')
    def _compute_remaining_qty(self):
        for line in self:
            line.remaining_qty = line.product_qty - line.shipped_qty

    @api.depends('product_qty', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit

    @api.depends('company_id')
    def _compute_company_currency(self):
        for line in self:
            line.company_currency_id = line.company_id.currency_id

    @api.depends('price_unit', 'lc_id.currency_id', 'lc_id.local_currency',
                 'product_qty')
    def compute_foreign_currency(self):
        for line in self:
            if line.lc_id.purchase_process == 'foreign_purchase':
                line.foreign_currency = line.price_unit * line.lc_id.local_currency
                line.foreign_price_subtotal = line.foreign_currency * line.product_qty
            else:
                line.foreign_currency = line.price_unit * line.lc_id.local_currency
                line.foreign_price_subtotal = 0

    @api.depends('product_qty', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit

    @api.depends("product_id")
    def _compute_product_uom(self):
        for line in self:
            line.product_uom = line.product_id.uom_id.id

    @api.depends("lc_id.po_id.state")
    def _compute_ordered_qty(self):
        for line in self:
            total = 0.0
            lc = line.lc_id

            # Use the single PO reference from po_id instead of looping over multiple purchase orders
            po = lc.po_id
            if po and po.state in ["purchase", "done"]:
                # Filter PO lines to match the product in the current LC line
                for po_line in po.order_line.filtered(lambda order_line: order_line.product_id == line.product_id):
                    # Convert the quantity to the LC line's UoM if needed
                    if po_line.product_uom_id != line.product_uom:
                        total += po_line.product_uom._compute_quantity(po_line.product_qty, line.product_uom)
                    else:
                        total += po_line.product_qty

            # Set the total ordered quantity
            line.ordered_qty = total

            # Update the state of the LC based on ordered quantity
            if total > 0 and lc.state == "confirm":
                lc.write({"state": "approve"})
            elif total == 0.0 and lc.state in ("approve", "done"):
                lc.write({"state": "confirm"})

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom = self.product_id.uom_id.id
            self.product_qty = 1.0


class LetterCreditCostLine(models.Model):
    _name = "letter.credit.cost.line"
    _description = "LC Landed Cost Line"

    SPLIT_METHOD = [
        ("equal", "Equal"),
        ("by_quantity", "By Quantity"),
        ("by_current_cost_price", "By Current Cost"),
        ("by_weight", "By Weight"),
        ("by_volume", "By Volume"),
    ]

    lc_id = fields.Many2one("letter.credit", string="LC Reference", ondelete="cascade", required=True, index=True)

    lc_product_id = fields.Many2one(
        "product.product",
        string="LC Product",
        domain=[("type", "=", "consu")],
    )

    product_id = fields.Many2one(
        "product.product",
        string="Cost Product",
        domain=[("type", "=", "service")],
    )

    landed_cost_type = fields.Selection([
        ('custom_duty', 'Custom Duty'),
        ('cnf_charge', 'Additional Charge')
    ], string="Cost Type", default='custom_duty', required=True)
    split_method = fields.Selection(SPLIT_METHOD, string="Split Method")
    account_id = fields.Many2one(
        "account.account",
        "Account",
        required=True,
    )

    amount = fields.Monetary(string="Amount", required=True)

    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='lc_id.company_id.currency_id',
        readonly=True,
        store=True
    )

    lc_journal_id = fields.Many2one('account.journal', string="Duty Journal")
    payment_amount = fields.Float(string="Payed Amount")
    remaining_amount = fields.Float(string="Remaining Amount")
    is_payed = fields.Boolean(string="Is Paid", default=False)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            # Get default expense account (if you still want to do something with it)
            expense_account = self.product_id.property_account_expense_id

            # Set amount from product standard cost
            self.amount = self.product_id.standard_price

            # Optionally set the expense account as default
            if expense_account:
                self.account_id = expense_account
