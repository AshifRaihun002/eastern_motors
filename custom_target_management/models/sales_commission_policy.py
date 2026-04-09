from odoo import models, fields, api

class SalesCommissionPolicy(models.Model):
    _name = "sales.commission.policy"
    _description = "Sales Commission Policy"

    name = fields.Char(string="Name", required=True)
    created_by = fields.Char(string="Created By", default=lambda self: self.env.user)
    is_active = fields.Boolean(string="Is Active", default=True)

    policy_line_ids = fields.One2many("sales.commission.policy.line", "policy_id", string="Policies")


class SalesCommissionLine(models.Model):
    _name = "sales.commission.policy.line"
    _description = "Sales Commission Line"

    policy_id = fields.Many2one("sales.commission.policy")

    sequence = fields.Integer(string="Sequence", default=1)
    from_amount = fields.Float(string="From Amount")
    to_amount = fields.Float(string="To Amount")
    commission = fields.Float(string="Commission")




