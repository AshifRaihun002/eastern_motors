from odoo import models
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.report_xlsx.report.report_abstract_xlsx import ReportAbsatractXlsx
except ImportError:
    _logger.debug('Can not import report_xlsx')


class IndentReportXlsx(models.AbstractModel):
    _name = 'report.indent_process.indent_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Indent Report XLSX'

    def generate_xlsx_report(self, workbook, data, wizard):
        report_obj = self.env['report.indent_process.indent_report_template']
        report_data = report_obj._get_report_values(None, data=data)
        lines = report_data.get('lines', [])
        
        sheet = workbook.add_worksheet('Indent Report')
        
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
        cell_format = workbook.add_format({'border': 1, 'font_size': 9})
        num_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'font_size': 9})
        total_format = workbook.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00', 'font_size': 10, 'bg_color': '#f2f2f2'})
        date_format = workbook.add_format({'border': 1, 'num_format': 'dd/mm/yyyy', 'font_size': 9})

        # Set Column Widths
        sheet.set_column('A:A', 5)   # S.no
        sheet.set_column('B:C', 15)  # Indent No, Date
        sheet.set_column('D:D', 30)  # Item Name
        sheet.set_column('E:G', 15)  # Internal Name, Uom, Status
        sheet.set_column('H:H', 12)  # Indent Qty
        sheet.set_column('I:I', 15)  # Issue Date
        sheet.set_column('J:J', 15)  # To Dept
        sheet.set_column('K:L', 12)  # Issue Qty, Return Qty
        sheet.set_column('M:M', 15)  # Lot ID
        sheet.set_column('N:P', 15)  # Net Issue Qty, Unit Rate, Issue Amt
        sheet.set_column('Q:W', 20)  # User, Shipment, Supplier, etc.

        # Header
        sheet.merge_range('A1:X1', 'STORE INDENT AND ISSUE BETWEEN', head_format)
        sheet.merge_range('A2:X2', f"From {report_data['from_date'].strftime('%d/%m/%Y')} To {report_data['to_date'].strftime('%d/%m/%Y')}", sub_head_format)

        # Table Headers
        headers = [
            'S.no', 'Indent No', 'Indent Date', 'Item Name[Code]', 'Internal Name', 'Uom', 'Item status',
            'Indent qty', 'Issue Date', 'To Department', 'Issue Qty', 'Return Qty', 'Lot ID',
            'Net Issue Qty', 'Unit Rate', 'Issue Amt', 'User Name', 'ShipmentNo', 'ShipmentDate',
            'SupplierName', 'MFGDate', 'ExpireDate', 'Comment', 'Remarks'
        ]
        for col, header in enumerate(headers):
            sheet.write(3, col, header, table_head_format)

        row = 4
        serial = 1
        total_issue_amt = 0.0
        
        for line in lines:
            sheet.write(row, 0, serial, cell_format)
            sheet.write(row, 1, line['indent_no'], cell_format)
            sheet.write(row, 2, line['indent_date'], date_format)
            sheet.write(row, 3, line['product_name'], cell_format)
            sheet.write(row, 4, line['internal_name'], cell_format)
            sheet.write(row, 5, line['uom'], cell_format)
            sheet.write(row, 6, line['status'], cell_format)
            sheet.write(row, 7, line['indent_qty'], num_format)
            sheet.write(row, 8, line['issue_date'], date_format)
            sheet.write(row, 9, line['to_dept'], cell_format)
            sheet.write(row, 10, line['issue_qty'], num_format)
            sheet.write(row, 11, line['return_qty'], num_format)
            sheet.write(row, 12, line['lot_id'], cell_format)
            sheet.write(row, 13, line['net_issue_qty'], num_format)
            sheet.write(row, 14, line['unit_rate'], num_format)
            sheet.write(row, 15, line['issue_amt'], num_format)
            sheet.write(row, 16, line['user_name'], cell_format)
            sheet.write(row, 17, line['shipment_no'], cell_format)
            sheet.write(row, 18, line['shipment_date'], date_format)
            sheet.write(row, 19, line['supplier_name'], cell_format)
            sheet.write(row, 20, line['mfg_date'], date_format)
            sheet.write(row, 21, line['exp_date'], date_format)
            sheet.write(row, 22, line['comment'], cell_format)
            sheet.write(row, 23, line['remarks'], cell_format)
            
            total_issue_amt += line['issue_amt']
            row += 1
            serial += 1

        # Total Row
        sheet.merge_range(row, 0, row, 14, 'TOTAL', table_head_format)
        sheet.write(row, 15, total_issue_amt, total_format)
        for col in range(16, 24):
            sheet.write(row, col, '', total_format)
