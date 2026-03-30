from odoo import api, fields, models


class ApprovalConfig(models.Model):
    _name = 'approval.config'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _description = 'Approval Config'

    name = fields.Char(string='Approval Name', required=True, tracking=True, help="Name of the Approval")
    approval_type = fields.Selection([('none', 'None')], string="Approval Type", required=True, tracking=True,
                                     help="Type of the Approval", default='none')
    approval_line_ids = fields.One2many('approval.line', 'config_id', string="Approval Lines", copy=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )


class ApprovalLine(models.Model):
    _name = 'approval.line'
    _description = 'Approval Line'
    _order = 'sequence, id'

    sequence = fields.Integer("Sequence", default=1)
    name = fields.Char(string="Approval Stage Name", required=True, help="Name of the Approval Stage")
    user_ids = fields.Many2many('res.users', string="Users", help="Users to be assigned for the Approval Stage")
    config_id = fields.Many2one('approval.config', string="Approval Config")
    approval_type = fields.Selection(related='config_id.approval_type', string="Approval Type", store=True)
    type = fields.Selection([('recommender', 'Recommender'), ('approver', 'Approver')], string="Type",
                            help="Type of the Approval Stage")
    is_email_send = fields.Boolean(
        string="Email Send",
        default=False
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related="config_id.company_id",
        required=False,
    )
    approve_in_bulk = fields.Boolean(string="Approve In Bulk", default=False)

    def first_stage(self, config_id):
        """Return the first (lowest sequence) stage for a given approval config."""
        return self.sudo().search(
            [('config_id', '=', config_id)],
            order="sequence asc",
            limit=1
        )

    def get_next_stage(self, config_id, current_stage_sequence, company_id):
        """Get the next stage based on the current stage sequence."""
        self.ensure_one()
        next_stage = self.sudo().search(
            [
                ('config_id', '=', config_id),
                ('company_id', '=', company_id),
                ('sequence', '>', current_stage_sequence),
            ],
            order='sequence asc', limit=1
        )
        return next_stage

    def get_previous_stage(self, config_id, current_stage_sequence, company_id):
        """Get the previous stage based on the current stage sequence."""
        self.ensure_one()
        previous_stage = self.sudo().search([
            ('config_id', '=', config_id),
            ('company_id', '=', company_id),
            ('sequence', '<', current_stage_sequence),
        ], order="sequence desc", limit=1)
        return previous_stage

    def is_initial(self):
        """Check if this line is the initial approval stage."""
        # Find the line with the lowest sequence in the same approval config
        initial_line = self.search([('config_id', '=', self.config_id.id)], order='sequence', limit=1)
        return self == initial_line

    def is_final(self):
        """Check if this line is the final approval stage."""
        # Find the line with the highest sequence in the same approval config
        final_line = self.search([('config_id', '=', self.config_id.id)], order='sequence desc', limit=1)
        return self == final_line
