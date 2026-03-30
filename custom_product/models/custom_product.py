from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    size = fields.Char(string="Size")
    pr = fields.Char(string="PR")
    pattern = fields.Char(string="Pattern")
    rim = fields.Char(string="Rim")
    set = fields.Char(string="Set")
    vendor_product_code = fields.Char(string="Vendor Product Code")
    hs_code = fields.Char(string="HS Code")

    type_id = fields.Many2one("product.custom.type", string="Type")
    group_id = fields.Many2one("product.custom.group", string="Group")

    def _build_auto_name(self,vals=None):
        vals = vals or {}
        for rec in self:
            size = vals.get("size", rec.size or "")
            pr = vals.get("pr", rec.pr or "")
            pattern = vals.get("pattern", rec.pattern or "")

            parts = [p.strip() for p in [size,pr,pattern] if p and str(p).strip()]
            return " ".join(parts)

    @api.onchange("size","pr","pattern")
    def _onchange_auto_name(self):
        for rec in self:
            rec.name = rec._build_auto_name()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            auto_name = " ".join(
                [str(vals.get(k, "")).strip() for k in ["size", "pr", "pattern"] if vals.get(k)]
            )
            if auto_name:
                vals["name"] = auto_name
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in ["size", "pr", "pattern"]):
            for rec in self:
                auto_name = rec._build_auto_name()
                if auto_name and rec.name != auto_name:
                    super(ProductTemplate, rec).write({"name": auto_name})
        return res

class ProductCustomType(models.Model):
    _name = "product.custom.type"
    _description = "Product Type"

    name = fields.Char(string='Type')

class ProductCustomGroup(models.Model):
    _name = "product.custom.group"
    _description = "Product Group"

    name = fields.Char(string='Group Name')