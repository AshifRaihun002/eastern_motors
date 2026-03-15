from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date

class WarrantyClaim(models.Model):
    _name = "warranty.claim"
    _description = "Warranty Claim"
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
    inspector = fields.Many2one("res.users", string="Inspector")
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

    inspection_date = fields.Datetime(string="Inspection Date")
    inspector_observations = fields.Text(string="Inspector Observations")
    other_observations = fields.Text(string="Other Observations")

    picture_type_one_ids = fields.One2many("inspection.picture.one", "warranty_claim_id", string="Picture 1")
    picture_type_two_ids = fields.One2many("inspection.picture.two", "warranty_claim_id", string="Picture 2")
    picture_type_three_ids = fields.One2many("inspection.picture.three", "warranty_claim_id", string="Picture 3")
    picture_type_four_ids = fields.One2many("inspection.picture.four", "warranty_claim_id", string="Picture 4")
    picture_type_five_ids = fields.One2many("inspection.picture.five", "warranty_claim_id", string="Picture 5")

    # Todo: Add fields related to "Dealer Info"

    # Todo: Add Approval

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
                    record.state = "inspected"
                else:
                    raise UserError(_("Inspection Date and Observation required"))
            else:
                raise UserError(_("Not in correct state"))

    @api.onchange("sales_order_id")
    def onchange_sales_order(self):
        if self.sales_order_id:
            self.line_ids = [(5, 0, 0)]
            lines = []
            for line in self.sales_order_id.order_line:
                lines.append((0, 0, {
                    "product_id": line.product_id.id,
                    "product_qty": line.product_uom_qty,
                    "price_unit": line.price_unit,
                    "name": line.name,
                }))
            self.line_ids = lines

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
