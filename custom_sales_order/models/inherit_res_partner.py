from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_type = fields.Selection([
        ('retail', 'Retail'),
        ('dealer', 'Dealer'),
        ('corporate', 'Corporate'),
        ('tender', 'Tender'),
        ('fleet_owner', 'Fleet Owner')
    ], string="Customer Type")

    is_security_money_apply = fields.Boolean(string="Security Applicable", default=False)
    security_money = fields.Integer(string="Security Amount")

    credit_used_amount = fields.Float(
        string="Credit Used",
        compute='_compute_remaining_credit',
        help="Total confirmed sales amount that uses credit payment type."
    )

    remaining_credit_limit = fields.Float(
        string="Remaining Credit Limit",
        compute='_compute_remaining_credit',
        help="Available credit = Credit Limit - Used Credit"
    )

    def _get_confirmed_credit_orders(self):
        self.ensure_one()
        commercial_partner = self.commercial_partner_id
        return self.env['sale.order'].search([
            ('partner_id', 'child_of', commercial_partner.id),
            ('payment_type', '=', 'credit'),
            ('state', 'in', ['sale', 'done']),
        ])

    @api.depends('credit_limit')
    def _compute_remaining_credit(self):
        for partner in self:
            commercial_partner = partner.commercial_partner_id
            credit_orders = commercial_partner._get_confirmed_credit_orders()
            used_credit = sum(credit_orders.mapped('amount_total'))
            remaining = commercial_partner.credit_limit - used_credit if commercial_partner.credit_limit > 0 else 0.0
            partner.credit_used_amount = used_credit
            partner.remaining_credit_limit = remaining if remaining > 0 else 0.0
