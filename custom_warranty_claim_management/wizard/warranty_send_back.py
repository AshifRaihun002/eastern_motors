from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class SendBackWizardWarranty(models.TransientModel):
    _name= "send.back.wizard.warranty"
    _description = "Warranty Send Back Wizard"

    note = fields.Text(string="Note")

    def send_back_warranty(self):
        warranty_id = self.env.context.get("active_id")
        warranty = self.env["warranty.claim"].browse(warranty_id)

        if not warranty_id:
            raise ValidationError("No warranty record found")

        current_stage_sequence = warranty.stage_id.sequence

        previous_stage = self.env["approval.line"].sudo().search(
            [
                ("config_id", "=", warranty.stage_id.config_id.id),
                ("sequence", "<", current_stage_sequence),
            ], order="sequence desc", limit=1
        )

        if previous_stage:
            self.env["approval.history"].create({
                "action_type": "sent_back",
                "res_id": warranty_id,
                "res_model": "warranty.claim",
                "stage_id": warranty.stage_id.id,
                "user_id": self.env.user.id,
                "date": fields.Datetime.now(),
                "note": self.note,
            })
            warranty.write({"stage_id": previous_stage.id})

        elif previous_stage and self.env.user not in previous_stage.user_ids:
            raise UserError("You are not allowed to send back from this stage")
        else:
            raise ValidationError(_("No previous stage found to send back"))


