from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ApproveWarrantyWarranty(models.TransientModel):
    _name= "approve.warranty.wizard"
    _description = "Warranty Approve Wizard"

    note = fields.Text(string="Note")

    is_last_approval_stage = fields.Boolean(string="Last Approval Stage", default=lambda self: self.env.context.get("default_is_last_approval_stage"))
    total_price = fields.Float(string="Total Price", default=lambda self: self.env.context.get("default_total_price"))
    approval_decision = fields.Selection([
        ('no_action', 'No Action'),
        ('refund', 'Refund'),
        ('replacement', 'Replacement'),
    ])
    refund_amount = fields.Float(string="Refund Amount")

    def approve_warranty(self):
        self.ensure_one()
        warranty_id = self.env.context.get("active_id")
        warranty = self.env["warranty.claim"].browse(warranty_id)

        if not warranty_id:
            raise ValidationError("No warranty record found")

        current_stage_sequence = warranty.stage_id.sequence

        # Find next stage
        next_stage = warranty.stage_id.get_next_stage(warranty.approval_config_id.id, current_stage_sequence, warranty.company_id.id)

        # Check user permission
        if next_stage and self.env.user not in warranty.stage_id.user_ids:
            raise UserError(_("You are not allowed to approve this stage."))
        elif self.env.user not in warranty.stage_id.user_ids:
            raise UserError(_("You are not allowed to approve this stage"))

        if self.approval_decision == 'refund':
            if self.refund_amount > self.total_price:
                raise ValidationError(_("Refund Amount cannot be greater than Total Price"))

        # Log to generic approval history
        # warranty._log_history(
        #     action_type='authorized',
        #     stage_id=warranty.stage_id.id,
        #     to_stage_id=next_stage.id if next_stage else False,
        #     note=self.note
        # )

        self.env["approval.history"].sudo().create([{
            'company_id': self.company_id.id if hasattr(self, "company_id") else self.env.company.id,
            'stage_id': warranty.stage_id.id,
            'to_stage_id': next_stage.id if next_stage else False,
            'user_id': self.env.user.id,
            'action_type': 'authorized',
            'res_model': "warranty.claim",
            'res_id': warranty_id,
            'note': self.note,
            'approval_decision': self.approval_decision if self.approval_decision else '',
            'refund_amount': self.refund_amount if self.refund_amount else '',
        }])

        if next_stage:
            warranty.write({'stage_id': next_stage.id, 'state': 'in_approval'})  # Keep state draft until final stage
        else:
            warranty.write({'stage_id': warranty.stage_id.id, 'state': 'approved', 'approval_decision': self.approval_decision if self.approval_decision else '', 'refund_amount': self.refund_amount if self.refund_amount else ''})  # Final approval


