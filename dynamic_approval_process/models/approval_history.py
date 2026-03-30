from odoo import models, fields, _


class ApprovalHistory(models.Model):
    _name = 'approval.history'
    _description = 'Generic Approval History'
    _order = 'id desc'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date = fields.Datetime('Date', default=fields.Datetime.now)
    stage_id = fields.Many2one('approval.line', string='From Stage')
    to_stage_id = fields.Many2one('approval.line', string='To Stage')
    user_id = fields.Many2one('res.users', string='Action Taken By', default=lambda self: self.env.user)
    action_type = fields.Selection(
        [
            ('create', 'Create'),
            ('authorized', 'Authorized'),
            ('sent_back', 'Sent Back'),
            ('review', 'Review'),
            ('cancel', 'Cancel'),
            ('draft', 'Reset to Draft',),
            ('confirmed', 'Confirm'),
            ('cancel', 'Cancel'),
            ('posted', 'Post'),
            ('paid', 'Paid'),
        ]
    )
    # Generic reference
    res_model = fields.Char(string="Related Model", required=True, index=True)
    res_id = fields.Integer(string="Related Record ID", required=True, index=True)

    note = fields.Text('Note', translate=True)
    res_name = fields.Char("Record Name", compute="_compute_res_name", store=True)

    def _compute_res_name(self):
        for rec in self:
            if rec.res_model and rec.res_id:
                try:
                    record = self.env[rec.res_model].browse(rec.res_id)
                    rec.res_name = record.display_name
                except Exception:
                    rec.res_name = False
