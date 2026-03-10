from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SendBackWizard(models.TransientModel):
    _name = 'send.back.wizard'
    _description = 'Send Back Wizard'
    _inherit = ['log.history.mixin']

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    note = fields.Text(string='Note')

    def action_send_back(self):
        self.ensure_one()
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        action_type = self.env.context.get('action_type', 'sent_back')

        if not active_model or not active_id:
            raise ValidationError(_("No record selected."))

        record = self.env[active_model].browse(active_id)

        # Determine previous stage
        if not record.stage_id:
            raise ValidationError(_("No current stage found."))

        first_stage = record.stage_id.first_stage(record.approval_config_id.id)
        if not first_stage:
            raise ValidationError(_("No first stage found to send back."))

        # Log in generic approval history
        record._log_history(
            action_type=action_type,
            note=self.note,
            stage_id=record.stage_id.id,
            to_stage_id=first_stage.id,
        )
        # Move back stage
        record.write({'stage_id': first_stage.id, 'state': 'draft'})
