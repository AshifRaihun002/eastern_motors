from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date

class WarrantyApproval(models.Model):
    _inherit = 'approval.config'
    approval_type = fields.Selection(selection_add=[('warranty', 'Warranty Claim')], ondelete={'warranty': 'set default'})

class WarrantyDecision(models.Model):
    _inherit = "approval.history"

    approval_decision = fields.Selection([
        ('no_action', 'No Action'),
        ('refund', 'Refund'),
        ('replacement', 'Replacement'),
    ])
    refund_amount = fields.Float(string="Refund Amount")

class WarrantyClaim(models.Model):
    _name = "warranty.claim"
    _description = "Warranty Claim"
    _inherit = ["log.history.mixin"]
    _order = "name desc, create_date desc"

    name = fields.Char(string="Warranty Ref", readonly=True, copy=False, help="Warranty Reference",
                       default=lambda self: _("New"))
    sales_order_id = fields.Many2one("sale.order", string="Sales Order")
    customer_id = fields.Many2one("res.partner", string="Customer")
    salesperson_id = fields.Many2one("res.users", string="Sales Person")
    mobile = fields.Char(string="Mobile")
    email = fields.Char(string="Email")
    Address = fields.Char(string="Address")
    sales_order_date = fields.Datetime(string="Sales Order Date")
    inspector = fields.Many2one("res.users", string="Inspector", domain=lambda self: self._get_inspector_domain())
    warranty_claim_date = fields.Datetime(string="Warranty Claim Date", default=lambda self: fields.Datetime.now())
    line_ids = fields.One2many("warranty.claim.line", "claim_id", string="Order Lines")
    state = fields.Selection([
        ("draft", "Draft"),
        ("assigned", "Assigned"),
        ("inspected", "Inspected"),
        ("in_approval", "In Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("closed", "Closed"),
    ], default="draft", string="Status")

    # Inspector fields
    inspection_date = fields.Datetime(string="Inspection Date")
    inspector_observations = fields.Text(string="Inspector Observations")
    other_observations = fields.Text(string="Other Observations")

    picture_type_one_ids = fields.One2many("inspection.picture.one", "warranty_claim_id", string="Picture 1")
    picture_type_two_ids = fields.One2many("inspection.picture.two", "warranty_claim_id", string="Picture 2")
    picture_type_three_ids = fields.One2many("inspection.picture.three", "warranty_claim_id", string="Picture 3")
    picture_type_four_ids = fields.One2many("inspection.picture.four", "warranty_claim_id", string="Picture 4")
    picture_type_five_ids = fields.One2many("inspection.picture.five", "warranty_claim_id", string="Picture 5")

    # Todo: Add fields related to "Dealer Info"

    # Approval Related fields
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company
    )

    requesting_department_id = fields.Many2one('hr.department', default=lambda self: self.env.user.employee_id.department_id)

    # approval_config_id = fields.Many2one("approval.config", domain="[('approval_type', '=', 'warranty'), ('company_id', '=', company_id)]", string="Approval Config")
    approval_config_id = fields.Many2one("approval.config", default= lambda self: self.env["approval.config"].sudo().search([("approval_type", "=", "warranty")], limit=1), string="Approval Config")

    stage_id = fields.Many2one(
        "approval.line",
        string="Approval Stage",
        copy=False,
        domain="[('config_id', '=', approval_config_id)]",
    )

    approval_history_ids = fields.One2many(
        'approval.history',
        'res_id',
        string="Approval History",
        domain=lambda self: [('res_model', '=', self._name), ('company_id', '=', self.company_id.id)],
    )

    is_user_approver = fields.Boolean(default=False, compute="_compute_is_user_approver")

    is_last_approval_stage = fields.Boolean(default=False, compute="_is_last_approval_stage")

    approval_decision = fields.Selection([
        ('no_action', 'No Action'),
        ('refund', 'Refund'),
        ('replacement', 'Replacement'),
    ], string="Approval Decision")
    refund_amount = fields.Float(string="Refund Amount")

    total_price = fields.Float(string="Total Price")

    @api.onchange("line_ids")
    def _calculate_total_price(self):
        total_price = 0.0
        for line in self.line_ids:
            total_price += line.price_unit*line.product_qty
        self.total_price = total_price

    def _get_inspector_domain(self):
        group = self.env.ref("custom_warranty_claim_management.warranty_claim_inspector")
        return [('group_ids', 'in', group.ids)]

    @api.onchange('approval_config_id')
    def _onchange_approval_config_id(self):
        self.stage_id = False
        if self.approval_config_id and self.approval_config_id.approval_line_ids:
            self.stage_id = self.approval_config_id.approval_line_ids[0]

    @api.depends("stage_id.user_ids")
    def _compute_is_user_approver(self):
        for rec in self:
            has_approval_access = self.env.user in rec.stage_id.user_ids

            rec.is_user_approver = has_approval_access

    @api.depends("stage_id")
    def _is_last_approval_stage(self):
        for rec in self:
            if rec.stage_id:
                rec.is_last_approval_stage = self.stage_id.is_final()

    def open_send_back_wizard(self):
        """Open wizard to capture send-back note"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Back Note'),
            'res_model': 'send.back.wizard',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context': {
                'default_note': '',
                'active_id': self.id,
                'active_model': self._name
            },
        }

    def open_approve_wizard(self):
        self.ensure_one()

        # Validation: Must have lines
        if not self.line_ids:
            raise ValidationError(_("No Products Added to the Indent. Please Add Products to Proceed."))

        # Validation: Must have approval config
        if not self.approval_config_id:
            raise ValidationError(_("No Approval Config found. Please configure approval stages first."))

        current_stage_sequence = self.stage_id.sequence

        return {
            'type': 'ir.actions.act_window',
            'name': _('Approve Note'),
            'res_model': 'approve.warranty.wizard',
            'target': 'new',
            'view_mode': 'form',
            'context': {
                'default_note': '',
                'active_id': self.id,
                'active_model': self._name,
                'default_is_last_approval_stage': self.is_last_approval_stage,
                'default_total_price': self.total_price,
            }
        }

    def assign_to_inspector(self):
        for record in self:
            if record.inspector:
                record.state = "assigned"
            else:
                raise UserError(_("Warranty Claim is not assigned to inspector"))

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def inspection_done(self):
        for record in self:
            if record.state == "assigned":
                if record.inspector_observations and record.inspection_date:
                    record.state = "in_approval"
                else:
                    raise UserError(_("Inspection Date and Observation required"))
            else:
                raise UserError(_("Not in correct state"))

    @api.onchange("sales_order_id")
    def _onchange_sales_order(self):
        if self.sales_order_id:
            self.line_ids = [(5, 0, 0)]
            lines = []
            total_price = 0.0
            for line in self.sales_order_id.order_line:
                lines.append((0, 0, {
                    "product_id": line.product_id.id,
                    "product_qty": line.product_uom_qty,
                    "price_unit": line.price_unit,
                    "name": line.name,
                    "pattern": line.product_id.pattern,
                }))
                total_price += line.price_unit*line.product_uom_qty
            self.line_ids = lines
            self.total_price = total_price

        for record in self:
            if record.sales_order_id:
                if record.sales_order_id.partner_id:
                    record.customer_id = record.sales_order_id.partner_id
                if record.sales_order_id.user_id:
                    record.salesperson_id = record.sales_order_id.user_id
                if record.sales_order_id.partner_id.email:
                    record.email = record.sales_order_id.partner_id.email
                if record.sales_order_id.date_order:
                    record.sales_order_date = record.sales_order_id.date_order

    @api.model_create_multi
    def create(self, vals_list):
        for val in vals_list:
            if val.get("name", _("New") == _("New")):
                val["name"] = self.env["ir.sequence"].next_by_code("warranty.sequence")

        return super(WarrantyClaim, self).create(vals_list)

    # Dashboard related function
    @api.model
    def get_overview_data(self):
        today = date.today()
        states = [
            ('draft', 'Draft'),
            ('assigned', 'Assigned'),
            ('inspected', 'Inspected'),
            ('in_approval', 'In Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('closed', 'Closed'),
        ]

        result = []
        for state, label in states:
            previous_count = self.search_count([
                ('state', '=', state),
                ('warranty_claim_date', '<', today),
            ])
            current_count = self.search_count([
                ('state', '=', state),
                ('warranty_claim_date', '>=', today),
            ])
            result.append({
                'state': state,
                'label': label,
                'previous': previous_count,
                'current': current_count,
            })

        return result
