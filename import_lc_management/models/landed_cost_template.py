from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime

SPLIT_METHOD = [
    ("equal", "Equal"),
    ("by_quantity", "By Quantity"),
    ("by_current_cost_price", "By Current Cost"),
    ("by_weight", "By Weight"),
    ("by_volume", "By Volume"),
]


class LandedCostTemplate(models.Model):
    _name = "landed.cost.template"
    _description = "Estimated Landed Cost Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Landed Cost Template",
        index="trigram",
        copy=False,
        readonly=True,
        required=True,
        default=lambda s: _("New"),
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        copy=True,
        index=True,
        tracking=True,
        required=True,
        domain="[('landed_cost_ok', '=', False), '|', ('company_id', '=?', company_id), ('company_id', '=', False)]",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        check_company=True,
        copy=False,
        tracking=True,
        required=True,
    )
    template_date = fields.Date(
        string="Template Date",
        tracking=True,
        default=fields.Date.today,
        copy=False,
        required=True,
    )
    cost_lines = fields.One2many(
        "landed.cost.template.lines",
        "template_id",
        string="Cost Lines",
        copy=True,
        tracking=True,
        required=True,
    )
    internal_notes = fields.Html("Internal Notes")
    company_id = fields.Many2one(
        "res.company",
        "Company",
        index=True,
        default=lambda self: self.env.company,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    _sql_constraints = [
        (
            "name",
            "unique (name)",
            "The name of the Landed Cost Template must be unique!",
        ),
        (
            "product_company_uniq",
            "unique(product_id, company_id)",
            "The product must be unique per company!",
        ),
    ]

    @api.constrains("cost_lines", "product_id", "company_id")
    def _check_cost_lines(self):
        """Ensure Cost Lines are provided"""
        without_cost_lines = self.filtered(lambda lc: not lc.cost_lines)
        if without_cost_lines:
            raise ValidationError(
                _(f"No cost lines found!\n Invalid Landed Cost Templates: {without_cost_lines.mapped('name')}"))

    @api.onchange("company_id")
    def _onchange_company(self):
        """Reset lines and product when changing the company"""
        self.cost_lines = False
        self.product_id = False

    def copy(self, default=None):
        """Override the copy method to provide default naming and log messages."""
        default = dict(default or {})
        copied_lc = super().copy(default)
        copied_lc._message_log(
            body=_("This entry has been duplicated from %s", self._get_html_link())
        )
        return copied_lc

    @api.model_create_multi
    def create(self, vals_list):
        """Override the create method to handle unique naming."""
        for vals in vals_list:
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "landed_cost_template_name"
            ) or _("New")
        return super().create(vals_list)

    # def _compute_display_name(self):
    #     """Compute and assign custom display name for each record."""
    #     for rec in self:
    #         # Assign a custom display name based on the name and product information
    #         rec.display_name = f"[{rec.name}] Estimated {rec.product_id.name} Landed Cost"

    def _compute_display_name(self):
        """Return custom display name for records."""
        return [
            (rec.id, f"[{rec.name}] Estimated {rec.product_id.name} Landed Cost")
            for rec in self
        ]



class LandedCostTemplateLine(models.Model):
    _name = "landed.cost.template.lines"
    _description = "Landed Cost Template Line"
    _rec_name = "product_id"

    template_id = fields.Many2one(
        "landed.cost.template",
        string="Landed Cost Template",
        required=True,
        index=True,
        ondelete="cascade",
        check_company=True,
    )
    product_id = fields.Many2one(
        "product.product",
        "Product",
        required=True,
        check_company=True,
        domain="[('landed_cost_ok', '=', True), '|', ('company_id', '=?', company_id), ('company_id', '=', False)]",
    )
    account_id = fields.Many2one(
        "account.account",
        "Account",
        required=True,
    )
    landed_cost_type = fields.Selection([
        ('custom_duty', 'Custom Duty'),
        ('cnf_charge', ' Additional Charge')
    ], string="Cost Type", default='custom_duty', required=True)
    split_method = fields.Selection(
        SPLIT_METHOD,
        string="Split Method",
        required=True,
        help="Equal : Cost will be equally divided.\n"
             "By Quantity : Cost will be divided according to product's quantity.\n"
             "By Current cost : Cost will be divided according to product's current cost.\n"
             "By Weight : Cost will be divided depending on its weight.\n"
             "By Volume : Cost will be divided depending on its volume.",
    )
    price_unit = fields.Monetary(
        "Cost",
        required=True,
        currency_field="company_currency_id",
    )
    company_id = fields.Many2one(
        related="template_id.company_id", store=True, index=True
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", readonly=True, store=True
    )

    _sql_constraints = [
        (
            "product_template_uniq",
            "unique(product_id, template_id)",
            "The product must be unique per Landed Cost Template!",
        ),
    ]

    @api.constrains("price_unit")
    def _check_cost_price(self):
        """Ensure landed cost price is non-zero."""
        for line in self:
            if line.price_unit == 0:
                raise ValidationError(_("Landed Cost can't be 0!"))

    @api.onchange("product_id")
    def onchange_product_id(self):
        """Set account and split method based on the product."""
        product = self.product_id.product_tmpl_id
        self.account_id = product.get_product_accounts()["expense"]
        self.split_method = (
                product.split_method_landed_cost or self.split_method or "equal"
        )
        self.price_unit = self.product_id.standard_price or 0.0
