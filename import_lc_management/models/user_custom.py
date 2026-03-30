# from odoo import fields, models
#
# class ResUsers(models.Model):
#     _inherit = 'res.users'
#
#     warehouse_ids = fields.Many2many(
#         'stock.warehouse',
#         string='Allowed Warehouses',
#         help="Warehouses this user has access to."
#     )
#     property_warehouse_id = fields.Many2one(
#         'stock.warehouse',
#         string='Default Warehouse',
#         help="Default warehouse for this user.",
#         company_dependent=True  # Usually used for property fields
#     )