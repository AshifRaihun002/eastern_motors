from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime


class LCShipment(models.Model):
    _name = "lc.shipment"
    _description = "LC Shipment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Shipment Reference",
        default=lambda s: _("New"),
        readonly=True,
        required=True,
    )

    lc_id = fields.Many2one(
        "letter.credit",
        string="Letter of Credit",
        required=True,
        readonly=True,
        ondelete="cascade"
    )
    vendor_bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        copy=False,
        readonly=False,
    )

    po_id = fields.Many2one(
        related='lc_id.po_id',
        string='Purchase Order',
        readonly=False,
        store=True
    )

    shipment_date = fields.Datetime(
        string="Shipment Date",
        default=fields.Datetime.now,
        required=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    shipment_line_ids = fields.One2many(
        "lc.shipment.line",
        "shipment_id",
        string="Shipment Lines"
    )

    notes = fields.Text(string="Notes")

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string="Company Currency",
        readonly=True,
        compute="_compute_company_currency",
        store=True
    )

    local_currency = fields.Float(
        related="lc_id.local_currency",
        string="Conversion Rate",
        readonly=False
    )
    partner_id = fields.Many2one(
        related="lc_id.partner_id",
        string="Vendor", tracking=True)

    currency_id = fields.Many2one(
        'res.currency',
        related="lc_id.currency_id",
        string='Account Currency',
        readonly=False
    )

    ship_margin_amount = fields.Float(
        string="Shipment Margin Amount",
        readonly=False
    )
    ship_margin_journal = fields.Many2one(
        'account.journal',
        string="Payment Journal",
        domain="[('type', 'in', ['bank', 'cash'])]"
    )
    ship_margin_acc = fields.Many2one(
        'account.account',
        string="Shipment Margin Acc",
        domain="[('account_type', '=', 'asset_current')]"
    )
    payment_date = fields.Date(string="Payment Date")

    payment_type = fields.Selection([
        ('upass', 'U-Pass'),
        ('sight', 'Sight'),
    ], string='Payment Type', default='sight', tracking=True)

    ship_payment_amount = fields.Float(
        string="Shipment Payment Amount",
        compute="_compute_ship_payment_amount",
        store=True,
    )
    ship_margin_payment = fields.Many2one('account.move', string="Shipment Payment", readonly=False)

    # Add purchase_process field for the computation
    purchase_process = fields.Selection(
        related="lc_id.purchase_process",
        string="Currency Type",
        readonly=True
    )

    cost_line_ids = fields.One2many(
        "shipment.cost.line",
        "shipment_id",
        string="Landed Cost Lines"
    )
    picking_count = fields.Integer(
        string='Transfer Count',
        compute='_compute_picking_count',
        store=True
    )

    picking_ids = fields.One2many(
        'stock.picking',
        'lc_shipment_id',
        string='Related Transfers'
    )
    amount_total = fields.Float(string="Total Amount",
                                compute="_compute_amount_total",
                                store=True,
                                )
    amount_total_bdt = fields.Float(string="Total Amount BDT",
                                    compute="_compute_total_amount_in_bdt",
                                    store=True,
                                    )
    custom_duty_journals = fields.Many2many(
        'account.move',
        'lc_shipment_account_move_rel',  # Let Odoo auto-create the table
        'shipment_id',
        'move_id',
        string="Custom Duty Payment Entries",
        copy=False,
        readonly=True,
    )
    vendor_bill_ids = fields.Many2many(
        'account.move',
        'lc_shipment_vendor_bill_rel',
        'shipment_id',
        'move_id',
        string="Vendor Bills",
        copy=False,
        readonly=True,
    )

    add_charge_vendor_bill = fields.Many2many(
        'account.move',
        'lc_shipment_vendor_bill_rel',  # Changed relation table name
        'shipment_id',  # Changed from 'lc_id' to 'shipment_id'
        'move_id',
        string="Vendor Bills",
        domain=[('move_type', '=', 'in_invoice')],
        copy=False,
    )

    custom_duty_journal_count = fields.Integer(
        string="Custom Duty Journal Count",
        compute="_compute_custom_duty_journal_count",
    )
    add_charge_vendor_bill_count = fields.Integer(
        string="Vendor Bill Count",
        compute="_compute_add_charge_vendor_bill_count"
    )
    landed_cost_count = fields.Integer(
        string="Landed Costs",
        compute="_compute_landed_cost_count",
    )
    vendor_bill_count = fields.Integer(
        string='Vendor Bill Count',
        compute='_compute_vendor_bill_count'
    )

    lc_advance_amount = fields.Float(
        string="LC Advance Amount",
        readonly=False
    )
    ship_advance_acc = fields.Many2one(
        'account.account',
        string="LC Advance Acc",
    )

    def _compute_vendor_bill_count(self):
        for shipment in self:
            shipment.vendor_bill_count = 1 if shipment.vendor_bill_id else 0

    def _compute_landed_cost_count(self):
        for shipment in self:
            shipment.landed_cost_count = self.env["stock.landed.cost"].search_count(
                [("shipment_id", "=", shipment.id)]
            )

    @api.depends('amount_total_bdt', 'ship_margin_amount')
    def _compute_ship_payment_amount(self):
        for rec in self:
            rec.ship_payment_amount = rec.amount_total_bdt - rec.ship_margin_amount

    def action_view_landed_costs(self):
        """Smart button to view related landed costs"""
        self.ensure_one()
        action = self.env.ref("stock_landed_costs.action_stock_landed_cost").read()[0]
        action["domain"] = [("shipment_id", "=", self.id)]
        action["context"] = {"default_shipment_id": self.id}
        return action

    def action_new_landed_cost(self):
        self.ensure_one()

        # Prepare landed cost lines from your LC cost lines with product filter
        shipment_lines = []
        for line in self.cost_line_ids.filtered(lambda l: l.product_id.landed_cost_ok):
            shipment_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'price_unit': line.amount,
                'account_id': line.product_id.property_account_expense_id.id or line.account_id.id,
                'split_method': line.split_method or 'equal',  # Use the line's split method if available
                'name': line.product_id.name or line.landed_cost_type,
            }))

        # Get done pickings from this shipment
        done_pickings = self.picking_ids.filtered(lambda pi: pi.state == "done")

        return {
            "name": _("New Landed Cost"),
            "type": "ir.actions.act_window",
            "target": "current",
            "view_mode": "form",
            "res_model": "stock.landed.cost",
            "context": {
                "default_picking_ids": done_pickings.ids,
                "default_shipment_id": self.id,
                "default_company_id": self.company_id.id,
                "default_cost_lines": shipment_lines,
            },
        }

    def action_create_vendor_bill(self):
        """Create vendor bill for the shipment linked to PO"""
        self.ensure_one()

        if not self.po_id:
            raise UserError(_("No Purchase Order linked to this shipment!"))

        if self.vendor_bill_id and self.vendor_bill_id.state != 'cancel':
            raise UserError(_("Vendor bill already exists for this shipment!"))

        # Prepare invoice lines from shipment lines
        invoice_line_vals = []
        for line in self.shipment_line_ids:
            # Find corresponding PO line
            po_line = self.env['purchase.order.line'].search([
                ('order_id', '=', self.po_id.id),
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if not po_line:
                raise UserError(_("Product %s not found in Purchase Order!") % line.product_id.name)

            invoice_line_vals.append((0, 0, {
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'price_unit': po_line.price_unit,  # Use PO price
                'purchase_line_id': po_line.id,  # Link to PO line
                'name': line.product_id.name,
                'account_id': line.product_id.property_account_expense_id.id or
                              line.product_id.categ_id.property_account_expense_categ_id.id,
                'lc_shipment_line_id': line.id,

            }))

        # Create vendor bill
        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'custom_conversion_rate': self.local_currency,
            'manual_currency_rate': True,
            'invoice_date': fields.Date.today(),
            'currency_id': self.currency_id.id,
            'purchase_id': self.po_id.id,  # Link to PO
            'invoice_line_ids': invoice_line_vals,
            'lc_shipment_id': self.id,  # Link to shipment
        }

        vendor_bill = self.env['account.move'].create(invoice_vals)
        self.vendor_bill_id = vendor_bill.id

        # Open the created bill
        return {
            'name': _('Vendor Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': vendor_bill.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_vendor_bill(self):
        """View the linked vendor bill"""
        self.ensure_one()
        if not self.vendor_bill_id:
            raise UserError(_("No vendor bill exists for this shipment!"))

        return {
            'name': _('Vendor Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.vendor_bill_id.id,
            'view_mode': 'form,list',
            'target': 'current',
        }

    @api.depends('custom_duty_journals')
    def _compute_custom_duty_journal_count(self):
        for rec in self:
            rec.custom_duty_journal_count = len(rec.custom_duty_journals)

    def _compute_add_charge_vendor_bill_count(self):
        for record in self:
            record.add_charge_vendor_bill_count = len(record.add_charge_vendor_bill)

    @api.depends('amount_total', 'local_currency')
    def _compute_total_amount_in_bdt(self):
        for rec in self:
            if rec.amount_total and rec.local_currency:
                rec.amount_total_bdt = rec.amount_total * rec.local_currency
            else:
                rec.amount_total_bdt = 0.0

    @api.depends('shipment_line_ids.price_subtotal')
    def _compute_amount_total(self):
        for ship in self:
            ship.amount_total = sum(line.price_subtotal for line in ship.shipment_line_ids)

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for shipment in self:
            shipment.picking_count = len(shipment.picking_ids)

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

    def get_shipment_cost_line_values(self):
        """Auto-fill those fields that are related to the LC product"""
        self.ensure_one()
        lc_product_ids = self.shipment_line_ids.mapped('product_id')
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
                        'shipment_id': self.id,
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
            self.cost_line_ids = None
            self.write({'cost_line_ids': lc_cost_line_vals})

        # Return action to reload current record
        return {
            'name': _('Letter of Credit'),
            'view_mode': 'form',
            'res_model': 'lc.shipment',
            'res_id': self.id,
            'type': 'ir.actions.act_window'
        }

    @api.depends('company_id')
    def _compute_company_currency(self):
        for rec in self:
            rec.company_currency_id = rec.company_id.currency_id

    def action_view_custom_duty_journals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Custom Duty Journal Entries',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.custom_duty_journals.ids)],
        }

    def action_open_vendor_bill_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Vendor Bill',
            'res_model': 'lc.shipment.vendor.bill.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('import_lc_management.view_lc_shipment_vendor_bill_wizard_form').id,
            'target': 'new',
            'context': {
                'default_shipment_id': self.id,
            },
        }



    def action_confirm(self):
        """Confirm shipment and split picking from purchase order"""
        for shipment in self:
            if shipment.state != 'draft':
                raise UserError(_("Only draft shipments can be confirmed."))

            # Validate shipment lines
            if not shipment.shipment_line_ids:
                raise UserError(_("Cannot confirm shipment without any products."))

            # Split picking from purchase order
            picking = shipment._split_picking_from_po()

            if not picking:
                raise UserError(_("Failed to create picking for shipment."))

            shipment.state = 'confirmed'

            # Post message in chatter
            shipment.message_post(
                body=_("Shipment confirmed. Picking %s created.") % picking.name
            )

        return True

    def _split_picking_from_po(self):
        """
        Split picking from purchase order based on shipment line quantities
        """
        self.ensure_one()

        if not self.po_id:
            raise UserError(_("No purchase order linked to this shipment."))

        # Get the main picking from purchase order
        main_pickings = self.po_id.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        )

        if not main_pickings:
            raise UserError(_("No available pickings found for purchase order %s.") % self.po_id.name)

        # Use the first available picking (usually there's only one)
        main_picking = main_pickings[0]

        # Ensure main picking is confirmed
        if main_picking.state == 'draft':
            main_picking.action_confirm()

        # Create a new picking for this shipment
        new_picking = self._create_shipment_picking(main_picking)

        # Process each shipment line to allocate quantities
        for line in self.shipment_line_ids:
            self._allocate_quantity_to_picking(line, main_picking, new_picking)

        # Confirm the new picking
        new_picking.action_confirm()

        # Link shipment to new picking
        new_picking.write({'lc_shipment_id': self.id})

        # Update the main picking quantities
        self._update_main_picking_quantities(main_picking)

        return new_picking

    def _create_shipment_picking(self, main_picking):
        """Create a new picking for the shipment"""
        picking_vals = {
            'picking_type_id': main_picking.picking_type_id.id,
            'location_id': main_picking.location_id.id,
            'location_dest_id': main_picking.location_dest_id.id,
            'origin': f"{main_picking.origin} - LC Shipment: {self.name}",
            'scheduled_date': fields.Datetime.now(),
            'company_id': self.company_id.id,
            'move_ids': [],
            'partner_id': main_picking.partner_id.id,
        }

        return self.env['stock.picking'].create(picking_vals)

    def _allocate_quantity_to_picking(self, shipment_line, main_picking, new_picking):
        """
        Allocate quantity from main picking to shipment picking
        """
        # Find the corresponding move in main picking
        main_move = main_picking.move_ids.filtered(
            lambda m: m.product_id == shipment_line.product_id and
                      m.product_uom_qty >= shipment_line.quantity and
                      m.state not in ('done', 'cancel')
        )

        if not main_move:
            raise UserError(_(
                "Product %(product)s not available in picking %(picking)s. "
                "Requested: %(qty)s %(uom)s"
            ) % {
                                'product': shipment_line.product_id.name,
                                'picking': main_picking.name,
                                'qty': shipment_line.quantity,
                                'uom': shipment_line.product_uom.name
                            })

        main_move = main_move[0]

        # Create move in shipment picking
        move_vals = {
            # 'name': f"{shipment_line.product_id.name} - LC Shipment",
            'product_id': shipment_line.product_id.id,
            'product_uom_qty': shipment_line.quantity,
            'product_uom': shipment_line.product_uom.id,
            'location_id': main_picking.location_id.id,
            'location_dest_id': main_picking.location_dest_id.id,
            'picking_id': new_picking.id,
            'shipment_line_id': shipment_line.id,
            'shipment_id': self.id,
            'purchase_line_id':shipment_line.lc_line_id.purchase_line_id.id,
            'price_unit': shipment_line.price_unit,
            'procure_method': main_move.procure_method,
            # Copy additional fields if needed
            'date': fields.Datetime.now(),
            'company_id': self.company_id.id,
        }

        # Create the move
        new_move = self.env['stock.move'].create(move_vals)

        # Update the main move quantity
        remaining_qty = main_move.product_uom_qty - shipment_line.quantity
        if remaining_qty > 0:
            main_move.write({'product_uom_qty': remaining_qty})
        else:
            # If no quantity left, cancel the main move
            main_move._action_cancel()

        return new_move

    def _update_main_picking_quantities(self, main_picking):
        """
        Update main picking after allocation
        Remove moves with zero quantity
        """
        # Remove moves with zero or negative quantity
        zero_moves = main_picking.move_ids.filtered(
            lambda m: m.product_uom_qty <= 0
        )
        if zero_moves:
            zero_moves.unlink()

        # If no moves left, cancel the picking
        if not main_picking.move_ids:
            main_picking.action_cancel()
        else:
            # Update the picking state
            main_picking._compute_state()

    def action_create_shipment_payment_entry(self):
        for shipment in self:
            # Check if we have the required fields
            if not shipment.lc_id.partner_id:
                raise UserError("Vendor must be defined in the Letter of Credit.")

            if not shipment.ship_margin_journal:
                raise UserError("Margin Journal must be set.")

            if not shipment.ship_margin_journal.default_account_id:
                raise UserError("The selected Margin Journal does not have a default account.")

            if shipment.amount_total_bdt <= 0:
                raise UserError("Total Amount in BDT must be greater than 0.")

            if not shipment.local_currency or shipment.local_currency <= 0:
                raise UserError("Conversion rate (Local Currency) must be set and greater than 0.")

            # Get amounts
            margin_amount_bdt = shipment.ship_margin_amount or 0.0
            lc_advance_amount_bdt = shipment.lc_advance_amount or 0.0
            total_amount_bdt = shipment.amount_total_bdt
            bank_amount_bdt = total_amount_bdt - margin_amount_bdt - lc_advance_amount_bdt

            if bank_amount_bdt < 0:
                raise UserError("Bank amount cannot be negative. Check margin, advance, or total amounts.")

            # Compute foreign amounts
            total_amount_foreign = total_amount_bdt / shipment.local_currency
            margin_amount_foreign = margin_amount_bdt / shipment.local_currency if margin_amount_bdt else 0.0
            lc_advance_amount_foreign = lc_advance_amount_bdt / shipment.local_currency if lc_advance_amount_bdt else 0.0
            bank_amount_foreign = bank_amount_bdt / shipment.local_currency

            bank_account = shipment.ship_margin_journal.default_account_id
            partner = shipment.lc_id.partner_id

            move_vals = {
                'journal_id': shipment.ship_margin_journal.id,
                'ref': f'Shipment Margin Payment: {shipment.name}',
                'date': fields.Date.context_today(self),
                'currency_id': shipment.currency_id.id if shipment.currency_id else self.env.company.currency_id.id,
                'line_ids': [],
            }

            # DEBIT: Vendor Payable (from LC partner)
            move_vals['line_ids'].append((0, 0, {
                'name': f"Shipment Payable to {partner.name}",
                'account_id': partner.property_account_payable_id.id,
                'partner_id': partner.id,
                'debit': total_amount_bdt,
                'credit': 0.0,
                'amount_currency': total_amount_foreign,
                'currency_id': shipment.currency_id.id if shipment.currency_id else self.env.company.currency_id.id,
            }))

            # CREDIT: Shipment Margin (if applicable)
            if margin_amount_bdt > 0:
                if not shipment.ship_margin_acc:
                    raise UserError("Shipment Margin Account must be defined when margin amount is greater than 0.")

                move_vals['line_ids'].append((0, 0, {
                    'name': f"Shipment Margin for {shipment.name}",
                    'account_id': shipment.ship_margin_acc.id,
                    'partner_id': partner.id,
                    'debit': 0.0,
                    'credit': margin_amount_bdt,
                    'amount_currency': -margin_amount_foreign,
                    'currency_id': shipment.currency_id.id if shipment.currency_id else self.env.company.currency_id.id,
                }))

            # CREDIT: LC Advance (if applicable)
            if lc_advance_amount_bdt > 0:
                if not shipment.ship_advance_acc:
                    raise UserError(
                        "Shipment Advance Account must be defined when LC Advance amount is greater than 0.")

                move_vals['line_ids'].append((0, 0, {
                    'name': f"Shipment Advance for {shipment.name}",
                    'account_id': shipment.ship_advance_acc.id,
                    'partner_id': partner.id,
                    'debit': 0.0,
                    'credit': lc_advance_amount_bdt,
                    'amount_currency': -lc_advance_amount_foreign,
                    'currency_id': shipment.currency_id.id if shipment.currency_id else self.env.company.currency_id.id,
                }))

            # CREDIT: Bank Payment
            if bank_amount_bdt > 0:
                move_vals['line_ids'].append((0, 0, {
                    'name': f"Bank Payment for Shipment {shipment.name}",
                    'account_id': bank_account.id,
                    'partner_id': partner.id,
                    'debit': 0.0,
                    'credit': bank_amount_bdt,
                    'amount_currency': -bank_amount_foreign,
                    'currency_id': shipment.currency_id.id if shipment.currency_id else self.env.company.currency_id.id,
                }))

            # Create and post journal entry
            move = self.env['account.move'].create(move_vals)
            move.action_post()

            # Reconcile with earliest open vendor bill
            bill = self.env['account.move'].search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('amount_residual', '>', 0),
            ], order='date asc', limit=1)

            if bill:
                bill_lines = bill.line_ids.filtered(
                    lambda l: l.account_id == partner.property_account_payable_id and l.amount_residual > 0)
                payment_lines = move.line_ids.filtered(
                    lambda l: l.account_id == partner.property_account_payable_id and l.amount_residual > 0)

                if bill_lines and payment_lines:
                    (bill_lines + payment_lines).reconcile()

            # Save journal entry reference
            shipment.ship_margin_payment = move.id

            # Log to chatter
            shipment.message_post(
                body=f"Shipment Margin Payment Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created."
            )

            return {
                'name': 'Shipment Payment Journal Entry',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': move.id,
                'view_mode': 'form',
            }

    def open_shipment_custom_duty_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Custom Duty Journal Entry',
            'res_model': 'shipment.custom.duty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shipment_id': self.id,
                'default_journal_id': False,  # You can set a default journal if needed
            }
        }

    def action_view_picking(self):
        """Action to view related pickings with shipment_id filter"""
        self.ensure_one()
        # Search for pickings that have this shipment_id or origin matching name
        pickings = self.env['stock.picking'].search([
            '|',
            ('lc_shipment_id', '=', self.id),
            ('origin', '=', self.name)
        ])

        action = {
            'name': _('Shipment Transfers'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pickings.ids)],
            'context': {
                'create': False,
                'default_shipment_id': self.id,  # Set default shipment_id when creating new picking
            },
        }

        if len(pickings) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = pickings.id

        return action

    def action_receive(self):
        for shipment in self:
            if shipment.state != 'confirmed':
                raise UserError(_("Only confirmed shipments can be marked as received."))
            shipment.state = 'received'

    def action_cancel(self):
        for shipment in self:
            if shipment.state == 'received':
                raise UserError(_("Received shipments cannot be cancelled."))
            shipment.state = 'cancelled'

    def action_draft(self):
        for shipment in self:
            if shipment.state != 'cancelled':
                raise UserError(_("Only cancelled shipments can be reset to draft."))
            shipment.state = 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["name"] = self.env["ir.sequence"].next_by_code('lc.shipment') or _("New")
        return super(LCShipment, self).create(vals_list)


class LCShipmentLine(models.Model):
    _name = "lc.shipment.line"
    _description = "LC Shipment Line"

    shipment_id = fields.Many2one(
        "lc.shipment",
        string="Shipment",
        required=True,
        ondelete="cascade"
    )

    lc_line_id = fields.Many2one(
        "letter.credit.line",
        string="LC Product Line",
        required=True
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="lc_line_id.product_id",
        readonly=True,
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related="shipment_id.currency_id",
        string='Account Currency',
        readonly=False
    )

    quantity = fields.Float(
        string="Quantity",
        required=True,
        digits='Product Unit of Measure'
    )

    price_unit = fields.Float(
        string='Unit Price',
        related="lc_line_id.price_unit",
        readonly=True,
        digits='Product Price'
    )

    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        related="lc_line_id.product_uom",
        readonly=True
    )

    remaining_qty = fields.Float(
        string="Remaining After Shipment",
        compute='_compute_remaining_qty',
        digits='Product Unit of Measure'
    )
    lc_purchase_process = fields.Selection(
        related="lc_line_id.lc_id.purchase_process",
        string="Purchase Process",
        readonly=False
    )

    lc_local_currency = fields.Float(
        related="lc_line_id.lc_id.local_currency",
        string="Conversion Rate",
        readonly=False
    )

    foreign_currency = fields.Float(
        string='Unit Rate(Local)',
        compute='compute_foreign_currency',
        readonly=False,
        digits='Product Price'
    )

    foreign_price_subtotal = fields.Float(
        string='Subtotal(Local)',
        compute='compute_foreign_currency',
        readonly=False,
        digits='Product Price'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        readonly=True
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        readonly=False,
        compute="_compute_subtotal"
    )

    @api.depends('quantity', 'lc_line_id.remaining_qty')
    def _compute_remaining_qty(self):
        for line in self:
            line.remaining_qty = line.lc_line_id.remaining_qty - line.quantity

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            # Use wizard values if available, otherwise use related values
            actual_quantity = line.wizard_quantity or line.quantity
            actual_price_unit = line.wizard_price_unit or line.price_unit
            line.price_subtotal = actual_quantity * actual_price_unit

    # @api.depends('price_subtotal', 'lc_local_currency')
    # def _compute_foreign_currency(self):
    #     for line in self:
    #         if line.lc_local_currency:
    #             line.foreign_currency = line.price_unit * line.lc_local_currency
    #             line.foreign_price_subtotal = line.price_subtotal * line.lc_local_currency
    #         else:
    #             line.foreign_currency = 0.0
    #             line.foreign_price_subtotal = 0.0

    @api.depends('price_unit', 'shipment_id.currency_id', 'shipment_id.local_currency',
                 'quantity')
    def compute_foreign_currency(self):
        for line in self:
            if line.shipment_id.purchase_process == 'foreign_purchase':
                line.foreign_currency = line.price_unit * line.shipment_id.local_currency
                line.foreign_price_subtotal = line.foreign_currency * line.quantity
            else:
                line.foreign_currency = line.price_unit * line.shipment_id.local_currency
                line.foreign_price_subtotal = 0

    @api.depends('price_unit', 'quantity')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.price_unit * line.quantity

    @api.depends('quantity', 'lc_line_id.remaining_qty')
    def _compute_remaining_qty(self):
        for line in self:
            line.remaining_qty = line.lc_line_id.remaining_qty - line.quantity


class ShipmentCostLine(models.Model):
    _name = "shipment.cost.line"
    _description = "LC Landed Cost Line"

    SPLIT_METHOD = [
        ("equal", "Equal"),
        ("by_quantity", "By Quantity"),
        ("by_current_cost_price", "By Current Cost"),
        ("by_weight", "By Weight"),
        ("by_volume", "By Volume"),
    ]

    # Remove lc_id and replace with shipment_id
    shipment_id = fields.Many2one(
        "lc.shipment",
        string="Shipment Reference",
        ondelete="cascade",
        required=True,
        index=True
    )

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

    # Update currency relation to go through shipment -> company
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='shipment_id.company_id.currency_id',
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
            # Get default expense account
            expense_account = self.product_id.property_account_expense_id

            # Set amount from product standard cost
            self.amount = self.product_id.standard_price

            # Optionally set the expense account as default
            if expense_account:
                self.account_id = expense_account


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    lc_shipment_id = fields.Many2one(
        'lc.shipment',
        string='LC Shipment'
    )
