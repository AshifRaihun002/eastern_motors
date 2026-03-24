from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class IndentAnalysisWizard(models.TransientModel):
    _name = 'indent.analysis.wizard'
    _description = 'Indent Analysis Report Wizard'

    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    unit_id = fields.Many2one('hr.department', string='Unit/Store', domain=[('is_store', '=', True)])
    report_type = fields.Selection([
        ('abc', 'ABC Analysis (By Amount)'),
        ('xyz', 'XYZ Analysis (By Consumption Qty)'),
        ('efg', 'EFG Analysis (By Stock Qty)')
    ], string='Analysis Type', default='abc', required=True)

    @api.constrains('from_date', 'to_date')
    def _check_dates(self):
        for rec in self:
            if rec.from_date and rec.to_date and rec.from_date > rec.to_date:
                raise ValidationError(_("From Date must be earlier than To Date."))

    def action_print_pdf(self):
        data = {
            'form': self.read()[0]
        }
        return self.env.ref('indent_process.action_report_indent_analysis').report_action(self, data=data)

    def action_print_excel(self):
        data = {
            'form': self.read()[0]
        }
        return self.env.ref('indent_process.action_report_indent_analysis_xlsx').report_action(self, data=data)
