from odoo import fields, models
from odoo.exceptions import ValidationError


class SetTarget(models.TransientModel):
    _name = "set.target.wizard"
    _description = "Set Target"

    target_type = fields.Selection([
        ('dealer', 'Dealer'),
        ('branch', 'Branch'),
    ])
    branch_partner_id = fields.Many2one("res.partner",
                                        default=lambda self: self.env.context.get("default_branch_partner_id"))
    dealer_ids = fields.Many2many("res.partner", default=lambda self: self.env.context.get("default_dealer_ids"))
    dealer_id = fields.Many2one("res.partner", domain="[('id', 'in', dealer_ids)]")

    line_ids = fields.One2many("set.target.group.line", "head_id")

    def set_target(self):
        self.ensure_one()
        target_id = self.env.context.get("active_id")
        target = self.env["custom.sale.target.head"].browse(target_id)

        if not target:
            raise ValidationError("No Target Record Found")

        target.action_generate_dealer_lines()
        target.action_generate_branch_lines()

        if self.target_type == "dealer":
            if not self.dealer_id:
                for line in self.line_ids:
                    dealer_lines = (target.line_ids.search([("product_group_id", "=", line.product_group_id.id),
                                                            ("dealer_branch_id", "!=", self.branch_partner_id),
                                                            ("head_id", "=", target_id)]))

                    dealer_lines.write({
                        "target_qty": line.target_qty,
                        "target_value": line.target_value,
                    })

                    for dealer_line in dealer_lines:
                        dealer_line.action_distribute_quantity()
            else:
                for line in self.line_ids:
                    dealer_lines = (target.line_ids.search([("product_group_id", "=", line.product_group_id.id),
                                                            ("dealer_branch_id", "=", self.dealer_id),
                                                            ("head_id", "=", target_id)]))
                    dealer_lines.write({
                        "target_qty": line.target_qty,
                        "target_value": line.target_value,
                    })

                    for dealer_line in dealer_lines:
                        dealer_line.action_distribute_quantity()

        elif self.target_type == "branch":
            for line in self.line_ids:
                dealer_lines = target.line_ids.search(
                    [("product_group_id", "=", line.product_group_id.id),
                     ("dealer_branch_id", "=", self.branch_partner_id), ("head_id", "=", target_id)])
                dealer_lines.write({
                    "target_qty": line.target_qty,
                    "target_value": line.target_value,
                })

                for dealer_line in dealer_lines:
                    dealer_line.action_distribute_quantity()

        return {"type": "ir.actions.act_window_close"}


class SetTargetGroupLine(models.TransientModel):
    _name = "set.target.group.line"
    _description = "Set Target Group Line"

    product_group_id = fields.Many2one("product.custom.group")

    target_qty = fields.Integer()
    target_value = fields.Float()

    head_id = fields.Many2one("set.target.wizard", ondelete="cascade")
