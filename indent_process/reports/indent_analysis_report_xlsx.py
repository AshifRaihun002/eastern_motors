from odoo import models
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.report_xlsx.report.report_abstract_xlsx import ReportAbsatractXlsx
except ImportError:
    _logger.debug('Can not import report_xlsx')


class IndentAnalysisReportXlsx(models.AbstractModel):
    _name = 'report.indent_process.indent_analysis_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Indent Analysis Report XLSX'

    def generate_xlsx_report(self, workbook, data, wizard):
        report_obj = self.env['report.indent_process.indent_analysis_template']
        report_data = report_obj._get_report_values(None, data=data)
        lines = report_data.get('lines', [])
        
        sheet = workbook.add_worksheet('Indent Analysis')
        
        # Formats
        head_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 14, 'underline': 1
        })
        sub_head_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 12
        })
        table_head_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'bg_color': '#f2f2f2', 'font_size': 10
        })
        cell_format = workbook.add_format({'border': 1, 'font_size': 9, 'text_wrap': True})
        num_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'font_size': 9})
        center_format = workbook.add_format({'border': 1, 'align': 'center', 'font_size': 9})
        bold_center_format = workbook.add_format({'bold': True, 'border': 1, 'align': 'center', 'font_size': 9})

        # Set Column Widths
        sheet.set_column('A:B', 20)  # Store, Prod Category
        sheet.set_column('C:E', 15)  # Sub Cat, Code, Name
        sheet.set_column('F:F', 30)  # Specification
        sheet.set_column('G:H', 12)  # Part Number, UOM
        sheet.set_column('I:K', 15)  # Safety Stock, MOQ, Reorder Level
        sheet.set_column('L:N', 12)  # Lead Time, Total Qty, Total Amount
        sheet.set_column('N:N', 10)  # Analysis Col (ABC/XYZ/EFG)
        sheet.set_column('O:O', 15)  # LC / Local
        sheet.set_column('P:P', 35)  # Remarks

        # Header
        form = data.get('form', {})
        report_type = form.get('report_type', 'abc')
        title = 'ABC INDENT ANALYSIS REPORT (BY AMOUNT)'
        if report_type == 'xyz':
            title = 'XYZ INDENT ANALYSIS REPORT (BY CONSUMPTION QTY)'
        elif report_type == 'efg':
            title = 'EFG INDENT ANALYSIS REPORT (BY STOCK QTY)'

        sheet.merge_range('A1:Q1', title, head_format)
        sheet.merge_range('A2:Q2', f"From {report_data['from_date'].strftime('%d/%m/%Y')} To {report_data['to_date'].strftime('%d/%m/%Y')}", sub_head_format)

        # Table Headers
        analysis_header = 'ABC'
        if report_type == 'xyz':
            analysis_header = 'XYZ'
        elif report_type == 'efg':
            analysis_header = 'EFG'

        headers = [
            'Store', 'Product Category', 'Sub Category', 'Code', 'Name(Item)', 'Specification', 
            'Part Number', 'UOM', 'Safety Stock', 'Min. Order Qty (MOQ)', 'Reorder Level', 
            'Lead Time (Days)', 'Total Qty', 'Total Amount', analysis_header, 'LC / Local', 'Remarks'
        ]
        for col, header in enumerate(headers):
            sheet.write(3, col, header, table_head_format)

        row = 4
        
        for line in lines:
            sheet.write(row, 0, line['store'], cell_format)
            sheet.write(row, 1, line['category'], cell_format)
            sheet.write(row, 2, line['sub_category'], cell_format)
            sheet.write(row, 3, line['code'], cell_format)
            sheet.write(row, 4, line['name'], cell_format)
            sheet.write(row, 5, line['specification'], cell_format)
            sheet.write(row, 6, line['part_number'], cell_format)
            sheet.write(row, 7, line['uom'], cell_format)
            sheet.write(row, 8, line['safety_stock'], num_format)
            sheet.write(row, 9, line['moq'], num_format)
            sheet.write(row, 10, line['reorder_level'], num_format)
            sheet.write(row, 11, line['lead_time'], center_format)
            sheet.write(row, 12, line['total_qty'], num_format)
            sheet.write(row, 13, line['total_amount'], num_format)
            
            analysis_val = line['abc']
            if report_type == 'xyz':
                analysis_val = line['xyz']
            elif report_type == 'efg':
                analysis_val = line['efg']
                
            sheet.write(row, 14, analysis_val, bold_center_format)
            sheet.write(row, 15, line['lc_local'], center_format)
            sheet.write(row, 16, line['remarks'], cell_format)
            row += 1
