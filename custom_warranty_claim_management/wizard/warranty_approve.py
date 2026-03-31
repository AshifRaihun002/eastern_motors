from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ApproveWarrantyWarranty(models.TransientModel):
    _name= "approve.warranty.wizard"
    _description = "Warranty Approve Wizard"

    note = fields.Text(string="Note")

    def approve_warranty(self):
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

        # Log to generic approval history
        warranty._log_history(
            action_type='authorized',
            stage_id=warranty.stage_id.id,
            to_stage_id=next_stage.id if next_stage else False,
            note=self.note
        )

        if next_stage:
            warranty.write({'stage_id': next_stage.id, 'state': 'in_approval'})  # Keep state draft until final stage
        else:
            warranty.write({'stage_id': warranty.stage_id.id, 'state': 'approved'})  # Final approval


