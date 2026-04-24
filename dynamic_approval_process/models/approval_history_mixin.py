from odoo import models, fields, _


class ApprovalHistoryMixin(models.AbstractModel):
    _name = "log.history.mixin"
    _description = "Mixin to Log Approval History"


    def _log_history(self, action_type, model_name='approval.history', note=None, stage_id=None, to_stage_id=None):
        """
        Create a generic approval history record for the current record.
        :param action_type: str ('create', 'authorized', 'sent_back', 'review')
        :param note: Optional text note
        :param stage_id: Optional stage (defaults to self.stage_id if available)
        """
        self.ensure_one()
        self.env[model_name].sudo().create([{
            'company_id': self.company_id.id if hasattr(self, "company_id") else self.env.company.id,
            'stage_id': stage_id,
            'to_stage_id': to_stage_id,
            'user_id': self.env.user.id,
            'action_type': action_type,
            'res_model': self._name,
            'res_id': self.id,
            'note': note or _("Action %s executed by %s") % (action_type, self.env.user.name),
        }])
