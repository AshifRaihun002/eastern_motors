from odoo import fields, models

class InheritResCountry(models.Model):
    _inherit = "res.country"

    custom_country_code = fields.Char(string="Custom Code")