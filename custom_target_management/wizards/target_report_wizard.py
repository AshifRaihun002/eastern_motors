from odoo import models, fields, api
import xlsxwriter
import base64
import io
from io import BytesIO
from collections import defaultdict


class TargetFormReportWizard(models.TransientModel):
    _name = "target.form.report.wizard"
    _description = "Target Report Wizard"

    report_type = fields.Selection([
        ('period', 'Period'),
        ('month', 'Month'),
    ])

    period_id = fields.Many2one(
        comodel_name='fiscal.year.config',
        string="Period",
        required=True
    )
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string="Month")

    def action_generate_fiscal_report(self):
        self.ensure_one()

        # --- 1. Fetch all product groups ---
        product_groups = self.env['product.custom.group'].search([], order='name asc')

        # --- 2. Fetch all target heads for this period ---
        heads = self.env['custom.sale.target.head'].search([
            ('period', '=', self.period_id.id),
            ('status', '=', 'approved'),
        ])

        # --- 3. Build a dict: {branch: {dealer: {group_id: {qty, value}}}} ---
        # Using defaultdict for easy accumulation
        branch_map = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'qty': 0, 'value': 0.0})))

        for head in heads:
            branch = head.branch_id
            for line in head.line_ids:
                dealer = line.dealer_branch_id
                group = line.product_group_id

                if not dealer or not group:
                    continue

                if self.month:
                    # --- Month filter: sum from detail lines matching the month ---
                    month_int = int(self.month)
                    for detail in line.detail_line_ids:
                        if not detail.date_from or not detail.date_to:
                            continue
                        # Check if this detail's range falls in the selected month
                        if (detail.date_from.month <= month_int <= detail.date_to.month or
                                detail.date_from.month == month_int or
                                detail.date_to.month == month_int):
                            branch_map[branch][dealer][group.id]['qty'] += detail.target_qty
                            branch_map[branch][dealer][group.id]['value'] += detail.target_value
                else:
                    # --- Full period: use line totals ---
                    branch_map[branch][dealer][group.id]['qty'] += line.target_qty
                    branch_map[branch][dealer][group.id]['value'] += line.target_value

        # --- 4. Build final structured result ---
        grand_total = {
            'groups': {g.id: {'qty': 0, 'value': 0.0} for g in product_groups},
            'total_qty': 0,
            'total_value': 0.0,
        }

        branches_result = []

        for branch, dealers in branch_map.items():
            branch_subtotal = {
                'groups': {g.id: {'qty': 0, 'value': 0.0} for g in product_groups},
                'total_qty': 0,
                'total_value': 0.0,
            }

            dealers_result = []

            for dealer, groups in dealers.items():
                dealer_groups = {g.id: {'qty': 0, 'value': 0.0} for g in product_groups}
                dealer_total_qty = 0
                dealer_total_value = 0.0

                for group in product_groups:
                    g_data = groups.get(group.id, {'qty': 0, 'value': 0.0})
                    dealer_groups[group.id] = g_data
                    dealer_total_qty += g_data['qty']
                    dealer_total_value += g_data['value']

                    # Accumulate into branch subtotal
                    branch_subtotal['groups'][group.id]['qty'] += g_data['qty']
                    branch_subtotal['groups'][group.id]['value'] += g_data['value']

                    # Accumulate into grand total
                    grand_total['groups'][group.id]['qty'] += g_data['qty']
                    grand_total['groups'][group.id]['value'] += g_data['value']

                branch_subtotal['total_qty'] += dealer_total_qty
                branch_subtotal['total_value'] += dealer_total_value
                grand_total['total_qty'] += dealer_total_qty
                grand_total['total_value'] += dealer_total_value

                dealers_result.append({
                    'dealer': dealer,
                    'groups': dealer_groups,
                    'total_qty': dealer_total_qty,
                    'total_value': dealer_total_value,
                })

            branches_result.append({
                'branch': branch,
                'dealers': dealers_result,
                'subtotal': branch_subtotal,
            })

        data = {
            'product_groups': product_groups,
            'branches': branches_result,
            'grand_total': grand_total,
        }

        stream = io.BytesIO()
        wb = xlsxwriter.Workbook(stream, {'in_memory': True})
        ws = wb.add_worksheet('Sales Target Report')

        product_groups = data['product_groups']
        n_groups = len(product_groups)

        # ---- Column index layout (0-based) ----------------------------- #
        COL_DEALER = 0
        COL_GRP_START = 1  # first group qty col
        COL_TOTAL_QTY = COL_GRP_START + n_groups * 2
        COL_TOTAL_VALUE = COL_TOTAL_QTY + 1
        TOTAL_COLS = COL_TOTAL_VALUE + 1  # total column count

        # ---- Number formats -------------------------------------------- #
        FMT_QTY = '#,##0'
        FMT_VALUE = '#,##0.00'

        # ---- Shared format properties ---------------------------------- #
        base = {'font_name': 'Arial', 'font_size': 10, 'border': 1}

        def fmt(extra):
            return wb.add_format({**base, **extra})

        # Title
        f_title = fmt({'bold': True, 'font_size': 12,
                       'bg_color': '#1F4E79', 'font_color': '#FFFFFF',
                       'align': 'center', 'valign': 'vcenter'})

        # Column headers
        f_hdr = fmt({'bold': True,
                     'bg_color': '#2E75B6', 'font_color': '#FFFFFF',
                     'align': 'center', 'valign': 'vcenter', 'text_wrap': True})

        # Branch header
        f_branch = fmt({'bold': True,
                        'bg_color': '#1F4E79', 'font_color': '#FFFFFF',
                        'align': 'left', 'valign': 'vcenter'})

        # Dealer rows (alternating)
        f_dealer_even = fmt({'bg_color': '#EBF3FB', 'align': 'left', 'valign': 'vcenter'})
        f_dealer_odd = fmt({'bg_color': '#FFFFFF', 'align': 'left', 'valign': 'vcenter'})
        f_num_even = fmt({'bg_color': '#EBF3FB', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_QTY})
        f_num_odd = fmt({'bg_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_QTY})
        f_val_even = fmt({'bg_color': '#EBF3FB', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_VALUE})
        f_val_odd = fmt({'bg_color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_VALUE})

        # Subtotal
        f_sub = fmt({'bold': True, 'bg_color': '#BDD7EE', 'align': 'left', 'valign': 'vcenter'})
        f_sub_num = fmt(
            {'bold': True, 'bg_color': '#BDD7EE', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_QTY})
        f_sub_val = fmt(
            {'bold': True, 'bg_color': '#BDD7EE', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_VALUE})

        # Grand total
        f_grand = fmt({'bold': True, 'bg_color': '#F4B942', 'align': 'left', 'valign': 'vcenter'})
        f_grand_num = fmt(
            {'bold': True, 'bg_color': '#F4B942', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_QTY})
        f_grand_val = fmt(
            {'bold': True, 'bg_color': '#F4B942', 'align': 'center', 'valign': 'vcenter', 'num_format': FMT_VALUE})

        # Header number formats (no num_format needed — headers are text)
        f_hdr_num = f_hdr
        f_hdr_val = f_hdr

        # ---- Column widths -------------------------------------------- #
        ws.set_column(COL_DEALER, COL_DEALER, 28)
        for g_idx in range(n_groups):
            qty_col = COL_GRP_START + g_idx * 2
            ws.set_column(qty_col, qty_col, 12)
            ws.set_column(qty_col + 1, qty_col + 1, 16)
        ws.set_column(COL_TOTAL_QTY, COL_TOTAL_QTY, 12)
        ws.set_column(COL_TOTAL_VALUE, COL_TOTAL_VALUE, 16)

        # ---- Freeze panes --------------------------------------------- #
        # Freeze below row 3 (title + 2 header rows) and right of col 0
        ws.freeze_panes(3, 1)

        row = 0

        # ---- Title row ------------------------------------------------ #
        period_name = self.period_id.name or ''
        month_label = dict(self._fields['month'].selection).get(self.month, 'Full Period') \
            if self.month else 'Full Period'
        title = f"Sales Target Report  |  Period: {period_name}  |  {month_label}"

        ws.merge_range(row, 0, row, TOTAL_COLS - 1, title, f_title)
        ws.set_row(row, 24)
        row += 1

        # ---- Header row 1: group names spanning Qty+Value ------------- #
        ws.merge_range(row, COL_DEALER, row + 1, COL_DEALER, 'Dealer', f_hdr)

        for g_idx, group in enumerate(product_groups):
            qty_col = COL_GRP_START + g_idx * 2
            ws.merge_range(row, qty_col, row, qty_col + 1, group.name, f_hdr)

        ws.merge_range(row, COL_TOTAL_QTY, row, COL_TOTAL_VALUE, 'Total', f_hdr)
        ws.set_row(row, 20)
        row += 1

        # ---- Header row 2: Qty / Value labels ------------------------- #
        # COL_DEALER already merged — write empty string to satisfy XlsxWriter
        ws.write(row, COL_DEALER, '', f_hdr)

        for g_idx in range(n_groups):
            qty_col = COL_GRP_START + g_idx * 2
            ws.write(row, qty_col, 'Qty', f_hdr)
            ws.write(row, qty_col + 1, 'Value', f_hdr)

        ws.write(row, COL_TOTAL_QTY, 'Qty', f_hdr)
        ws.write(row, COL_TOTAL_VALUE, 'Value', f_hdr)
        ws.set_row(row, 18)
        row += 1

        # ---- Data rows ------------------------------------------------ #
        def write_group_data(r, groups, f_num, f_val):
            for g_idx, group in enumerate(product_groups):
                qty_col = COL_GRP_START + g_idx * 2
                g_data = groups.get(group.id, {'qty': 0, 'value': 0.0})
                ws.write_number(r, qty_col, g_data['qty'], f_num)
                ws.write_number(r, qty_col + 1, g_data['value'], f_val)

        for branch_data in data['branches']:
            branch_name = branch_data['branch'].name if branch_data['branch'] else 'Unknown'

            # Branch header
            ws.merge_range(row, 0, row, TOTAL_COLS - 1, branch_name, f_branch)
            ws.set_row(row, 18)
            row += 1

            # Dealer rows
            for d_idx, dealer_data in enumerate(branch_data['dealers']):
                is_even = d_idx % 2 == 0
                f_text = f_dealer_even if is_even else f_dealer_odd
                f_num = f_num_even if is_even else f_num_odd
                f_val = f_val_even if is_even else f_val_odd

                dealer_name = dealer_data['dealer'].name if dealer_data['dealer'] else ''
                ws.write(row, COL_DEALER, dealer_name, f_text)
                write_group_data(row, dealer_data['groups'], f_num, f_val)
                ws.write_number(row, COL_TOTAL_QTY, dealer_data['total_qty'], f_num)
                ws.write_number(row, COL_TOTAL_VALUE, dealer_data['total_value'], f_val)
                row += 1

            # Subtotal
            subtotal = branch_data['subtotal']
            ws.write(row, COL_DEALER, 'Subtotal', f_sub)
            write_group_data(row, subtotal['groups'], f_sub_num, f_sub_val)
            ws.write_number(row, COL_TOTAL_QTY, subtotal['total_qty'], f_sub_num)
            ws.write_number(row, COL_TOTAL_VALUE, subtotal['total_value'], f_sub_val)
            row += 1

        # Grand total
        grand = data['grand_total']
        ws.write(row, COL_DEALER, 'Grand Total', f_grand)
        write_group_data(row, grand['groups'], f_grand_num, f_grand_val)
        ws.write_number(row, COL_TOTAL_QTY, grand['total_qty'], f_grand_num)
        ws.write_number(row, COL_TOTAL_VALUE, grand['total_value'], f_grand_val)

        wb.close()
        file_data = stream.getvalue()

        attachment = self.env['ir.attachment'].create({
            'name': f'sales_target_report_{self.period_id.name}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(file_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_generate_excel(self):
        line_model = self.env.context.get("line_model")
        record_id = self.env.context.get("active_id")
        record = self.env["custom.sale.target.head"].browse(record_id)

        period = record.period
        branch = record.branch_id.partner_id

        dealer_lines = self.env[line_model].search(
            [('head_id', '=', record.id), ('dealer_branch_id', '!=', record.branch_id.partner_id)])
        branch_lines = self.env[line_model].search(
            [('head_id', '=', record.id), ('dealer_branch_id', '=', record.branch_id.partner_id)])
        product_groups = self.env['product.custom.group'].sudo().search([])

        target_info = {}
        for line in dealer_lines:
            if line.dealer_branch_id in target_info:
                # target_info[line.dealer_branch_id].append((line.product_group_id, line.target_qty, line.target_value))
                target_info[line.dealer_branch_id][line.product_group_id] = (line.target_qty, line.target_value)
            else:
                target_info[line.dealer_branch_id] = {}
                target_info[line.dealer_branch_id][line.product_group_id] = (line.target_qty, line.target_value)

        branch_info = {}
        for line in branch_lines:
            if line.dealer_branch_id in branch_info:
                # branch_info[line.dealer_branch_id].append((line.product_group_id, line.target_qty, line.target_value))
                branch_info[line.dealer_branch_id][line.product_group_id] = (line.target_qty, line.target_value)
            else:
                branch_info[line.dealer_branch_id] = {}
                branch_info[line.dealer_branch_id][line.product_group_id] = (line.target_qty, line.target_value)

        # Excel Code
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Target Report')

        # Formats
        header_fmt = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
        })

        heading_fmt = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
        })

        cell_fmt = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        money_fmt = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'center',
            'valign': 'vcenter',
        })

        merge_fmt = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        row = 0
        col = 0

        # Period& Branch
        worksheet.write(row, col, 'Period', header_fmt)
        worksheet.merge_range(row, col + 1, row, col + 3,
                              f"{period.from_date.strftime("%B %Y")} - {period.to_date.strftime("%B %Y")}", merge_fmt)
        row += 1
        worksheet.write(row, col, 'Branch', header_fmt)
        worksheet.merge_range(row, col + 1, row, col + 3, f"{branch.display_name}", merge_fmt)

        # Dealer
        row += 2
        worksheet.write(row, col, "Group ->", header_fmt)
        worksheet.write(row + 1, col, "Dealer", header_fmt)
        col = 1
        group_total = {}
        for group in product_groups:
            worksheet.merge_range(row, col, row, col + 1, f"{group.name}", heading_fmt)
            worksheet.write(row + 1, col, "Quantity", cell_fmt)
            worksheet.write(row + 1, col + 1, "Amount", cell_fmt)
            group_total[group] = [0, 0]
            col += 2
        worksheet.merge_range(row, col, row, col + 1, "Total", heading_fmt)
        worksheet.write(row + 1, col, "Quantity", cell_fmt)
        worksheet.write(row + 1, col + 1, "Amount", cell_fmt)
        row += 2

        for key in target_info:
            col = 0
            quantity_total = 0
            amount_total = 0
            worksheet.write(row, col, key.name, cell_fmt)
            for group_key in product_groups:
                if group_key in target_info[key]:
                    worksheet.write(row, col + 1, target_info[key][group_key][0], money_fmt)
                    worksheet.write(row, col + 2, target_info[key][group_key][1], money_fmt)
                    quantity_total += target_info[key][group_key][0]
                    amount_total += target_info[key][group_key][1]

                    group_total[group_key][0] += target_info[key][group_key][0]
                    group_total[group_key][1] += target_info[key][group_key][1]
                else:
                    worksheet.write(row, col + 1, 0, money_fmt)
                    worksheet.write(row, col + 2, 0, money_fmt)
                col += 2

            worksheet.write(row, col + 1, quantity_total, money_fmt)
            worksheet.write(row, col + 2, amount_total, money_fmt)
            row += 1

        col = 1
        worksheet.write(row, col - 1, "Total", heading_fmt)
        for key in group_total:
            worksheet.write(row, col, group_total[key][0], money_fmt)
            worksheet.write(row, col + 1, group_total[key][1], money_fmt)
            col += 2
        worksheet.write(row, col, record.dealer_target_qty, money_fmt)
        worksheet.write(row, col + 1, record.dealer_target_value, money_fmt)

        # Branch
        row += 2
        col = 0
        worksheet.write(row, col, "Group ->", header_fmt)
        worksheet.write(row + 1, col, "Branch", header_fmt)
        col = 1

        for group in product_groups:
            worksheet.merge_range(row, col, row, col + 1, f"{group.name}", heading_fmt)
            worksheet.write(row + 1, col, "Quantity", cell_fmt)
            worksheet.write(row + 1, col + 1, "Amount", cell_fmt)
            col += 2
        worksheet.merge_range(row, col, row, col + 1, "Total", heading_fmt)
        worksheet.write(row + 1, col, "Quantity", cell_fmt)
        worksheet.write(row + 1, col + 1, "Amount", cell_fmt)
        row += 2

        for key in branch_info:
            col = 0
            quantity_total = 0
            amount_total = 0
            worksheet.write(row, col, key.name, cell_fmt)
            for group_key in product_groups:
                if group_key in branch_info[key]:
                    worksheet.write(row, col + 1, branch_info[key][group_key][0], money_fmt)
                    worksheet.write(row, col + 2, branch_info[key][group_key][1], money_fmt)
                    quantity_total += branch_info[key][group_key][0]
                    amount_total += branch_info[key][group_key][1]

                    group_total[group_key][0] += branch_info[key][group_key][0]
                    group_total[group_key][1] += branch_info[key][group_key][1]
                else:
                    worksheet.write(row, col + 1, 0, money_fmt)
                    worksheet.write(row, col + 2, 0, money_fmt)
                col += 2

            worksheet.write(row, col + 1, quantity_total, money_fmt)
            worksheet.write(row, col + 2, amount_total, money_fmt)
            row += 1

        workbook.close()
        excel_data = base64.b64encode(output.getvalue()).decode('utf-8')

        attachment = self.env['ir.attachment'].create({
            "name": "Target Report",
            "type": "binary",
            "datas": excel_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'current',
        }
