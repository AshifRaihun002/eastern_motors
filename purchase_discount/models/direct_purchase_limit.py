from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError

class DirectPurchaseConfig(models.Model):
    _name = 'direct.purchase.config'
    _description = 'Direct Purchase Configuration'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    direct_purchase_limit = fields.Float(
        string='Direct Purchase Limit',
        default=50000.0,
        help="Maximum allowed amount for direct purchases without additional approval"
    )
    direct_purchase_line_limit = fields.Float(
        string='Direct Purchase Line Limit',
        default=10000.00,
        help="Maximum allowed amount for direct purchases Line without additional approval"
    )
    is_active = fields.Boolean(string='Active', default=True)
    concern_dept = fields.Many2one('hr.department', string='Concern Department', readonly=False,
                                   domain="[('is_procurement', '=', True)]")

    _sql_constraints = [
        ('limit_positive', 'CHECK(direct_purchase_limit >= 0)',
         'Direct purchase limit must be positive!'),
    ]

    @api.model
    def get_direct_purchase_config(self, company_id=None, concern_dept_id=None):
        """Get the direct purchase configuration for current company and department"""
        company_id = company_id or self.env.company.id

        config = self.search([
            ('company_id', '=', company_id),
            ('is_active', '=', True),
            '|',
            ('concern_dept', '=', False),  # global config
            ('concern_dept', '=', concern_dept_id)  # department-specific config
        ], limit=1)

        return config

