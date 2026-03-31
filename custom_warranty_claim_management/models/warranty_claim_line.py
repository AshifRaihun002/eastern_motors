from odoo import fields, models
from odoo.api import ondelete


class WarrantyClaimLine(models.Model):
    _name = "warranty.claim.line"
    _description = "Warranty Claim Line"

    claim_id = fields.Many2one("warranty.claim", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product")
    name = fields.Text(string="Description")
    product_qty = fields.Float(string="Quantity")
    price_unit =  fields.Float(string="Unit Price")
    serial_number = fields.Char(string="Serial No.", required=True)
    pattern = fields.Char(string="Pattern")
