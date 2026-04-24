from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_type = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('credit', 'Credit'),
    ], string="Payment Type", default='cash', tracking=True, required=True)

    # Related fields from partner
    customer_type = fields.Selection([
        ('retail', 'Retail'),
        ('dealer', 'Dealer'),
        ('corporate', 'Corporate'),
        ('tender', 'Tender'),
        ('fleet_owner', 'Fleet Owner')
    ], string="Customer Type",
        related='partner_id.customer_type',
        store=True)

    is_security_money_apply = fields.Boolean(
        string="Security Applicable",
        related='partner_id.is_security_money_apply',
        store=True)

    user_id = fields.Many2one(
        comodel_name='res.users',
        string="User",
        compute='_compute_user_id',
        store=True,
        readonly=False,
        precompute=True,
        index=True,
        tracking=2,
        domain="[('company_ids', 'in', company_id)]",
    )

    security_money = fields.Integer(
        string="Security Amount",
        related='partner_id.security_money',
        store=True)

    # Credit limit as related field from partner
    credit_limit = fields.Float(
        string="Credit Limit",
        related='partner_id.credit_limit',
        help="Maximum credit allowed for this customer")

    # Remaining credit from partner
    remaining_credit = fields.Float(
        string="Remaining Credit",
        related='partner_id.remaining_credit_limit',
        help="Remaining credit available")

    credit_used_amount = fields.Float(
        string="Credit Used",
        related='partner_id.credit_used_amount',
        help="Total confirmed credit sales for this customer."
    )

    projected_remaining_credit = fields.Float(
        string="Remaining After This Order",
        compute='_compute_credit_limit_metrics',
        help="Remaining credit after including the current quotation amount."
    )

    credit_overdue_amount = fields.Float(
        string="Exceeded Amount",
        compute='_compute_credit_limit_metrics',
        help="How much this order exceeds the customer's credit limit."
    )

    is_credit_limit_exceeded = fields.Boolean(
        string="Credit Limit Exceeded",
        compute='_compute_credit_limit_metrics'
    )

    credit_used_sale_order_ids = fields.Many2many(
        'sale.order',
        string="Credit Used Sales",
        compute='_compute_credit_limit_metrics',
        help="Confirmed sales orders that already consumed the customer's credit limit."
    )

    credit_used_sale_order_count = fields.Integer(
        string="Credit Sales Count",
        compute='_compute_credit_limit_metrics'
    )
    approval_config_id = fields.Many2one(
        'approval.config', string='Approval', tracking=True, compute='_compute_sale_approval_config', store=False,
        domain="[('approval_type', '=', 'sales'), ('company_id', '=', company_id)]"
    )
    stage_id = fields.Many2one(
        "approval.line", string="Approval Stage", copy=True, tracking=True,
        domain="[('config_id', '=', approval_config_id), ('config_id', '!=', False)]"
    )
    is_user_approver = fields.Boolean(string='Is User Approver', compute='_compute_is_user_approver')
    state = fields.Selection(
        selection_add=[('approval_pending', 'Approval Pending')],
        ondelete={'approval_pending': 'set default'},
        tracking=True
    )

    approval_history_ids = fields.One2many(string="Sales Approval History", comodel_name='so.approval.history', inverse_name='sale_id', copy=False,)
    authorised_by_id = fields.Many2one(
        'hr.employee',
        string='Authorized By',
        copy=False,
        tracking=True
    )

    def _confirmation_error_message(self):
        """Return whether order can be confirmed or not, else return error message."""
        self.ensure_one()

        # Allow approval_pending also
        if self.state not in {'draft', 'sent', 'approval_pending'}:
            return _("Some orders are not in a state requiring confirmation.")

        if any(
                not line.display_type
                and not line.is_downpayment
                and not line.product_id
                for line in self.order_line
        ):
            return _("Some order lines are missing a product, you need to correct them before going further.")

        return False
    def approve_sale_order(self):
        for record in self:
            # Validation: Check if there are any product lines in the sales order
            if not record.order_line:
                raise ValidationError(_("No products added to the Sales Order. Please add products to proceed."))

            # Validation: Check if the approval config exists
            approval_config = record.approval_config_id
            if not approval_config:
                raise ValidationError(_("No Approval Data Added to Approval Config. Please Add Data to Proceed."))

            # Validation: Current stage must exist
            if not record.stage_id:
                raise ValidationError(_("No approval stage found for this Sales Order."))

            current_stage_sequence = record.stage_id.sequence

            # Find the next stage based on the current stage's sequence
            next_stage = self.env['approval.line'].sudo().search(
                [
                    ('config_id', '=', approval_config.id),
                    ('sequence', '>', current_stage_sequence),
                ],
                order='sequence asc',
                limit=1
            )

            # Prepare history data
            history_data = {
                'action_type': 'authorized',
                'sale_id': record.id,
                'stage_id': record.stage_id.id,
                'to_stage_id': next_stage.id if next_stage else False,
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'note': _("Approved by %s") % self.env.user.name,
            }

            if next_stage and self.env.user in record.stage_id.user_ids:
                # Move to the next stage and keep state as approval_pending
                record.write({
                    'stage_id': next_stage.id,
                    'state': 'approval_pending'
                })

                # Create the approval history record
                self.env['so.approval.history'].create(history_data)

            elif next_stage and self.env.user not in record.stage_id.user_ids:
                raise UserError(_("You are not allowed to approve this stage."))

            elif not next_stage and self.env.user in record.stage_id.user_ids:
                # Final stage approval
                self.env['so.approval.history'].create(history_data)

                # Store final approver
                record.write({
                    'authorised_by_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
                })

                # Call main sales confirmation process
                super(SaleOrder, record).action_confirm()

            else:
                raise ValidationError(_("No Approval Remaining"))

    # def action_confirm(self):
    #     for order in self:
    #         if order.approval_config_id and order.state in ('draft', 'sent'):
    #             raise UserError(_("This Sales Order must be submitted for approval first."))
    #
    #         if order.approval_config_id and order.state == 'approval_pending':
    #             raise UserError(_("This Sales Order is still waiting for approval."))
    #
    #     return super(SaleOrder, self).action_confirm()

    def send_back_note(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Back Note'),
            'res_model': 'sent.back.wizard.so',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context': {
                'active_id': self.id,
                'sale_id': self.id,
            },
        }
    @api.depends('stage_id.user_ids')
    def _compute_is_user_approver(self):
        for rec in self:
            is_erp_manager = False
            has_approval_access = self.env.user in rec.stage_id.user_ids

            # Check if the current user is in the 'erp_manager' group
            erp_manager_group = self.env.ref('base.group_erp_manager')
            if erp_manager_group and self.env.user in erp_manager_group.user_ids:
                is_erp_manager = True
            rec.is_user_approver = has_approval_access

    @api.onchange('approval_config_id')
    def onchange_approval_config_id(self):
        for rec in self:
            rec.stage_id = self.env["approval.line"].search([
                ('config_id', '=', rec.approval_config_id.id)
            ], limit=1).id
    def get_current_stage_sequence(self):
        """Return the sequence of the current stage."""
        self.ensure_one()
        return self.stage_id.sequence if self.stage_id else 0


    def action_submit_for_approval(self):
        """Send quotation for approval"""
        for rec in self:
            if not rec.order_line:
                raise ValidationError(_("Please add at least one product line."))

            if not rec.approval_config_id:
                raise ValidationError(_("No Approval Config found. Please configure approval stages first."))

            first_stage = self.env['approval.line'].search([
                ('config_id', '=', rec.approval_config_id.id)
            ], order='sequence asc', limit=1)

            if not first_stage:
                raise ValidationError(_("No approval stages found in the selected approval config."))

            rec.write({
                'stage_id': first_stage.id,
                'state': 'approval_pending',
            })

    @api.depends('company_id')
    def _compute_sale_approval_config(self):
        for record in self:
            approval_config = self.env["approval.config"].search([
                ('approval_type', '=', 'sales'),
                ('company_id', '=', record.company_id.id)
            ], limit=1)

            if approval_config:
                record.approval_config_id = approval_config
            else:
                raise UserError(_("No Approval Config found. Please configure indent approval stages first."))

    @api.depends('partner_id', 'partner_id.credit_limit', 'partner_id.remaining_credit_limit', 'amount_total', 'payment_type')
    def _compute_credit_limit_metrics(self):
        for order in self:
            partner = order.partner_id.commercial_partner_id
            if not partner:
                order.projected_remaining_credit = 0.0
                order.credit_overdue_amount = 0.0
                order.is_credit_limit_exceeded = False
                order.credit_used_sale_order_ids = False
                order.credit_used_sale_order_count = 0
                continue

            credit_used_orders = partner._get_confirmed_credit_orders()
            order.credit_used_sale_order_ids = credit_used_orders
            order.credit_used_sale_order_count = len(credit_used_orders)

            if partner.credit_limit <= 0:
                order.projected_remaining_credit = 0.0
                order.credit_overdue_amount = 0.0
                order.is_credit_limit_exceeded = False
                continue

            confirmed_credit_orders = credit_used_orders.filtered(lambda so: so.id != order.id)
            used_credit_before_order = sum(confirmed_credit_orders.mapped('amount_total'))
            current_remaining = partner.credit_limit - used_credit_before_order
            projected_remaining = current_remaining
            if order.payment_type == 'credit':
                projected_remaining -= order.amount_total

            order.projected_remaining_credit = max(projected_remaining, 0.0) if order.payment_type != 'credit' else projected_remaining
            order.credit_overdue_amount = abs(projected_remaining) if projected_remaining < 0 else 0.0
            order.is_credit_limit_exceeded = order.payment_type == 'credit' and projected_remaining < 0

    @api.constrains('partner_id', 'amount_total', 'payment_type')
    def _check_credit_limit(self):
        for order in self:
            partner = order.partner_id.commercial_partner_id
            if order.state in ['draft', 'sent']:  # Only check in draft/sent state
                if order.payment_type == 'credit' and order.credit_limit > 0 and order.is_credit_limit_exceeded:
                    raise ValidationError(_(
                        f"Credit limit exceeded for customer {partner.name}!\n"
                        f"Credit Limit: {order.credit_limit}\n"
                        f"Payment Type: {order.payment_type}\n"
                        f"Remaining Before Order: {order.remaining_credit}\n"
                        f"Current Order: {order.amount_total}\n"
                        f"Remaining After Order: {order.projected_remaining_credit}\n"
                        f"This order exceeds the credit limit by {order.credit_overdue_amount}"
                    ))

            # Security money validation
            if order.is_security_money_apply and order.security_money > 0:
                if order.amount_total > order.security_money:
                    raise ValidationError(_(
                        f"Order amount ({order.amount_total}) exceeds security money amount ({order.security_money})!\n"
                        f"Maximum order amount allowed: {order.security_money}"
                    ))


class PurchaseOrderApproval(models.Model):
    _name = 'so.approval.history'
    _rec_name = 'sale_id'
    _description = 'Approval History'

    date = fields.Datetime('Date', default=fields.Datetime.now)
    stage_id = fields.Many2one('approval.line', string='Approval Stage')
    to_stage_id = fields.Many2one('approval.line', string='Approval State')
    user_id = fields.Many2one('res.users', 'Action Taken By', default=lambda self: self.env.user)
    action_type = fields.Selection(
        [
            ('authorized', 'Authorized'),
            ('sent_back', 'Sent Back'),
            ('review', 'Review')
        ],
        required=True
    )
    sale_id = fields.Many2one(
        comodel_name='sale.order',
        string="Sales Order",
        required=True,
        ondelete='cascade',
        index=True,
        copy=False)
    note = fields.Text('Note', translate=True)