from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    is_indent_transit_active = fields.Boolean(
        string="Activate Indent Transit Location",
        default=False,
        help="Enable indent transit location usage for indent issues."
    )
    indent_transit_location_id = fields.Many2one(
        'stock.location',
        string="Indent Transit Location",
        domain=[('usage', '=', 'transit')],
        help="Select the location used as the transit point for indent issues."
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_indent_transit_active = fields.Boolean(
        related='company_id.is_indent_transit_active',
        string="Activate Indent Transit Location",
        readonly=False
    )
    indent_transit_location_id = fields.Many2one(
        related='company_id.indent_transit_location_id',
        comodel_name='stock.location',
        string="Indent Transit Location",
        readonly=False
    )