from odoo import fields, models, api


class WarrantyClaimLine(models.Model):
    _name = "warranty.claim.line"
    _description = "Warranty Claim Line"

    claim_id = fields.Many2one("warranty.claim", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product", domain="[('type', '=', 'consu'), ('is_storable', '=', True)]")
    name = fields.Text(string="Description")
    product_qty = fields.Float(string="Quantity")
    price_unit =  fields.Float(string="Unit Price")
    serial_number = fields.Char(string="Serial No.", required=True)
    pattern = fields.Char(string="Pattern")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.price_unit = self.product_id.list_price
        self.name = self.product_id.name
        self.pattern = self.product_id.pattern