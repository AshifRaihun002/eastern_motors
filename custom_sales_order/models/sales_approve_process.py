from odoo import models, fields, api, _


class ApprovalConfig(models.Model):
    _inherit = 'approval.config'

    approval_type = fields.Selection(
        selection_add=[('sales', 'Sales Order')], ondelete={'sales': 'set default'}
    )