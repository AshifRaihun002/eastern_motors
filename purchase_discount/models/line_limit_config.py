from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_direct_purchase_line_limit_active = fields.Boolean(
        string="Activate Direct Purchase Line Limit",
        default=False,
        help="Enable validation based on each direct purchase line amount."
    )
    direct_purchase_line_limit = fields.Float(
        string="Direct Purchase Line Limit",
        help="Maximum allowed amount per direct purchase line without additional approval."
    )

    is_purchase_over_receipt_active = fields.Boolean(
        string="Activate Purchase Over-Receipt Limit",
        default=False,
        help="Enable validation for purchase order over-receipt percentage."
    )
    purchase_over_receipt_percentage = fields.Float(
        string="Purchase Over-Receipt Percentage",
        default=10.0,
        help="Maximum allowed over-receipt percentage for purchase orders (e.g., 10 for 10% extra)."
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_direct_purchase_line_limit_active = fields.Boolean(
        related='company_id.is_direct_purchase_line_limit_active',
        string="Activate Direct Purchase Line Limit",
        readonly=False
    )
    direct_purchase_line_limit = fields.Float(
        related='company_id.direct_purchase_line_limit',
        string="Direct Purchase Line Limit",
        readonly=False
    )
    is_purchase_over_receipt_active = fields.Boolean(
        related='company_id.is_purchase_over_receipt_active',
        string="Activate Purchase Over-Receipt Limit",
        readonly=False
    )
    purchase_over_receipt_percentage = fields.Float(
        related='company_id.purchase_over_receipt_percentage',
        string="Purchase Over-Receipt Percentage (%)",
        readonly=False
    )