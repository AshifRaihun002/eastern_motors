from odoo import models, fields, api
from datetime import datetime
import pytz

class IndentReturnReportXlsx(models.AbstractModel):
    _name = 'report.indent_process.indent_return_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    
    def generate_xlsx_report(self, workbook, data, wizard):
        # Read wizard inputs
        date_from = fields.Date.from_string(data['form']['date_from'])
        date_to = fields.Date.from_string(data['form']['date_to'])
        store_id = data['form'].get('store_id') and data['form']['store_id'][0] or False
        to_unit_id = data['form'].get('to_unit_id') and data['form']['to_unit_id'][0] or False
        company_id = self.env.company.id

        sheet = workbook.add_worksheet('Return Report')

        # Formats
        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#D3D3D3', 'border': 1
        })
        cell_format = workbook.add_format({'border': 1, 'align': 'center'})
        left_cell_format = workbook.add_format({'border': 1, 'align': 'left'})
        date_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': 'dd-mmm-yyyy'})

        # Company Header
        sheet.merge_range('A1:O1', self.env.company.name, workbook.add_format({'bold': True, 'align': 'center', 'font_size': 14}))
        sheet.merge_range('A2:O2', 'RETURN REPORT', workbook.add_format({'bold': True, 'align': 'center', 'font_size': 12}))
        
        filter_str = f"Date: {date_from.strftime('%d-%b-%Y')} to {date_to.strftime('%d-%b-%Y')}"
        if store_id:
            store_name = self.env['factory.plant'].browse(store_id).name
            filter_str += f" | Store: {store_name}"
        if to_unit_id:
            unit_name = self.env['factory.plant'].browse(to_unit_id).name
            filter_str += f" | To Unit: {unit_name}"

        sheet.merge_range('A3:O3', filter_str, workbook.add_format({'align': 'center'}))

        # Columns configuration
        headers = [
            'Return ID', 'Return Date', 'Return From Department', 'Material Code',
            'Internal Code', 'Item Name', 'Status', 'Return Qty', 'Return Value',
            'Indent Date', 'Indent No', 'Indent Qty', 'Issue Date', 'Issue Qty', 'Issue Value'
        ]
        
        row = 4
        for col, head in enumerate(headers):
            sheet.write(row, col, head, header_format)
            
        # Set column widths
        sheet.set_column('A:B', 15)
        sheet.set_column('C:C', 25)
        sheet.set_column('D:E', 15)
        sheet.set_column('F:F', 30)
        sheet.set_column('G:I', 12)
        sheet.set_column('J:J', 15)
        sheet.set_column('K:K', 15)
        sheet.set_column('L:O', 12)

        row += 1

        # Search Stock Move Line Domain
        domain = [
            ('state', '=', 'done'),
            ('move_id.picking_type_id.code', '=', 'internal'),
            ('move_id.origin_returned_move_id', '!=', False),
            ('move_id.indent_line_id', '!=', False),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('company_id', '=', company_id)
        ]

        if store_id:
            domain.append(('move_id.indent_line_id.indent_id.from_unit', '=', store_id))
        
        if to_unit_id:
            domain.append(('move_id.indent_line_id.indent_id.factory_plant', '=', to_unit_id))

        move_lines = self.env['stock.move.line'].search(domain)

        total_return_value = 0.0
        total_issue_value = 0.0

        state_selection = dict(self.env['stock.move.line'].fields_get(['state'])['state']['selection'])

        for line in move_lines:
            move = line.move_id
            indent_line = move.indent_line_id
            indent = indent_line.indent_id
            
            # Format dates (move line date is datetime)
            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
            return_date = line.date.astimezone(user_tz).date() if line.date else ''
            
            # Values calculation
            std_price = line.product_id.standard_price or 0.0
            return_val = line.quantity * std_price
            issue_val = indent_line.transferred_qty * std_price

            total_return_value += return_val
            total_issue_value += issue_val

            sheet.write(row, 0, line.reference or line.picking_id.name or '', cell_format)
            sheet.write(row, 1, return_date, date_format)
            sheet.write(row, 2, indent.requesting_department_id.name or '', left_cell_format)
            sheet.write(row, 3, line.product_id.default_code or '', cell_format)
            sheet.write(row, 4, move.name or '', cell_format)
            sheet.write(row, 5, line.product_id.name or '', left_cell_format)
            sheet.write(row, 6, state_selection.get(line.state, line.state), cell_format)
            sheet.write(row, 7, line.quantity, cell_format)
            sheet.write(row, 8, return_val, cell_format)
            sheet.write(row, 9, indent.indent_date, date_format)
            sheet.write(row, 10, indent.name or '', cell_format)
            sheet.write(row, 11, indent_line.quantity, cell_format)
            sheet.write(row, 12, indent.issue_date, date_format)
            sheet.write(row, 13, indent_line.transferred_qty, cell_format)
            sheet.write(row, 14, issue_val, cell_format)
            
            row += 1

        # Print Totals
        sheet.merge_range(row, 0, row, 7, 'Grand Total:', workbook.add_format({'bold': True, 'align': 'right', 'border': 1}))
        sheet.write(row, 8, total_return_value, workbook.add_format({'bold': True, 'align': 'center', 'border': 1, 'num_format': '#,##0.00'}))
        sheet.merge_range(row, 9, row, 13, '', cell_format)
        sheet.write(row, 14, total_issue_value, workbook.add_format({'bold': True, 'align': 'center', 'border': 1, 'num_format': '#,##0.00'}))

