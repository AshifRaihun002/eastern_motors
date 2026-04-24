from odoo import models, fields, api, _

class IndentReturnReportWizard(models.TransientModel):
    _name = 'indent.return.report.wizard'
    _description = 'Indent Return Report Wizard'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)

    def action_print_excel(self):
        data = {
            'form': self.read()[0],
        }
        return self.env.ref('indent_process.action_report_indent_return_xlsx').report_action(self, data=data)
