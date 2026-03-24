from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class PurchaseRequisition(models.Model):
    _inherit = "custom.purchase.requisition"

    lc_ready_count = fields.Integer(compute="_compute_lc_count")
    lc_done_count = fields.Integer(compute="_compute_lc_count")

    # warehouse_id = fields.Many2one(
    #     'stock.warehouse',
    #     string='Bull Station',
    #     default=lambda self: self.env.user.property_warehouse_id.id,
    #     readonly=False
    # )
    date_required = fields.Datetime(string='Required Date LC')

    def _compute_lc_count(self):
        for rec in self:
            rec.lc_ready_count = self.env["letter.credit"].search_count(
                [
                    ("requisition_id", "=", rec.id),
                    ("state", "not in", ("done", "cancel")),
                ]
            )
            rec.lc_done_count = self.env["letter.credit"].search_count(
                [("requisition_id", "=", rec.id), ("state", "=", "done")]
            )

    def action_new_lc(self):
        self.ensure_one()

        return {
            "name": _("New L/C"),
            "type": "ir.actions.act_window",
            "target": "current",
            "view_mode": "form",
            "res_model": "letter.credit",
            "context": {
                "default_requisition_id": self.id,
                "default_origin": self.name,
                "default_description": self.remarks,
            },
        }

    def action_view_lc(self):
        self.ensure_one()

        action = {
            "name": _("Letter of Credit"),
            "type": "ir.actions.act_window",
            "res_model": "letter.credit",
            "context": {"create": False},
        }

        lc_ids = self.env["letter.credit"].search([("requisition_id", "=", self.id)])

        if len(lc_ids) == 1:
            action.update({"view_mode": "form", "res_id": lc_ids.id})
        else:
            action.update(
                {"view_mode": "list,form", "domain": [("id", "in", lc_ids.ids)]}
            )

        return action
