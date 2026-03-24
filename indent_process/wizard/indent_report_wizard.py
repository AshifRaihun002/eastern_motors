from odoo import models, fields, api, _
from odoo.exceptions import UserError

class IndentReportWizard(models.TransientModel):
    _name = 'indent.report.wizard'
    _description = 'Indent Report Wizard'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    product_ids = fields.Many2many('product.product', string='Products')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Received'),
        ('received', 'Fully Received'),
        ('cancel', 'Cancelled')
    ], string='Status')
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)

    def action_print_pdf(self):
        data = {
            'form': self.read()[0],
        }
        return self.env.ref('indent_process.action_report_indent').report_action(self, data=data)

    def action_print_excel(self):
        data = {
            'form': self.read()[0],
        }
        return self.env.ref('indent_process.action_report_indent_xlsx').report_action(self, data=data)
