from odoo import fields, models

class FiscalYearConfig(models.Model):
    _name= "fiscal.year.config"
    _description = "Fiscal Year Configuration"

    name = fields.Char(string="Name", required=True)
    from_date = fields.Date(string="From Date", required=True)
    to_date = fields.Date(string="To Date", required=True)
