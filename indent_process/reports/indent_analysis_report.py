from odoo import models, api, fields, _
from datetime import datetime

class IndentAnalysisReport(models.AbstractModel):
    _name = 'report.indent_process.indent_analysis_template'
    _description = 'Indent Analysis Report Abstract Model'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form'):
            return {}

        form = data.get('form')
        from_date = fields.Date.to_date(form.get('from_date'))
        to_date = fields.Date.to_date(form.get('to_date'))
        company_id = form.get('company_id')
        unit_id = form.get('unit_id')
        report_type = form.get('report_type')

        # 1. Fetch move lines based on filters (excluding returns)
        move_line_domain = [
            ('date', '>=', datetime.combine(from_date, datetime.min.time())),
            ('date', '<=', datetime.combine(to_date, datetime.max.time())),
            ('state', '=', 'done'),
            '|',
                ('indent_id', '!=', False),
                ('move_id.origin_returned_move_id.indent_id', '!=', False)
        ]
        if company_id:
            move_line_domain.append(('company_id', '=', company_id[0]))
        if unit_id:
            move_line_domain.append('|')
            move_line_domain.append(('indent_id.requesting_department_id', '=', unit_id[0]))
            move_line_domain.append(('move_id.origin_returned_move_id.indent_id.requesting_department_id', '=', unit_id[0]))

        move_lines = self.env['stock.move.line'].search(move_line_domain)
        
        # 2. Group data by product
        product_data = {}
        for ml in move_lines:
            indent = ml.indent_id or ml.move_id.origin_returned_move_id.indent_id
            prod_id = ml.product_id.id
            if prod_id not in product_data:
                product_data[prod_id] = {
                    'product': ml.product_id,
                    'total_qty': 0.0,
                    'total_amount': 0.0,
                    'store_name': indent.from_unit.name if indent and indent.from_unit else ''
                }
            
            # unit_rate = ml.move_id.unit_rate if hasattr(ml.move_id, 'unit_rate') else ml.product_id.standard_price
            unit_rate = ml.move_id.unit_rate if hasattr(ml.move_id, 'unit_rate') else ml.product_id.list_price
            issue_qty = ml.quantity
            
            # If it's a return, subtract
            if ml.move_id.origin_returned_move_id:
                issue_qty = -issue_qty
                
            amount = issue_qty * unit_rate
            
            product_data[prod_id]['total_qty'] += issue_qty
            product_data[prod_id]['total_amount'] += amount

        # 3. Calculate metrics and prepare list
        days = max((to_date - from_date).days + 1, 1)
        
        report_data = []
        for p_data in product_data.values():
            product = p_data['product']
            total_qty = p_data['total_qty']
            total_amount = p_data['total_amount']
            
            avg_daily_issue = total_qty / days
            
            # Fetch fields from product or related models
            safety_stock = product.safety_stock if hasattr(product, 'safety_stock') else 0.0
            
            # MOQ is reordering_min_qty, which might be on product or a separate model in BRAC
            # Typically reordering_min_qty is on product
            moq = product.reordering_min_qty if hasattr(product, 'reordering_min_qty') else 0.0
            
            # Lead Time (sale_delay or purchase lead time depending on BRAC implementation)
            # BRAC often uses sale_delay for internal lead time or seller_ids for purchase
            lead_time = product.sale_delay if hasattr(product, 'sale_delay') else 0.0
            
            # Reorder Level formula: (Avg Daily issue * Lead Time) + Safety Stock
            reorder_level = (avg_daily_issue * lead_time) + safety_stock
            
            # LC/Local - check if there's a purchase_type field or default to LOCAL based on BRAC example
            # BRAC has `purchase_type` on POs/RFQs, but not necessarily on the product directly.
            # We'll default to 'LOCAL' unless a specific field exists.
            lc_local = 'LOCAL'
            
            report_data.append({
                'product_id': product.id,
                'store': p_data['store_name'],
                'category': product.categ_id.parent_id.name if product.categ_id.parent_id else '',
                'sub_category': product.categ_id.name,
                'code': product.default_code or '',
                'name': product.name,
                'specification': product.product_specification if hasattr(product, 'product_specification') else '',
                'part_number': product.barcode or product.default_code or '',
                'uom': product.uom_id.name,
                'safety_stock': safety_stock,
                'moq': moq,
                'reorder_level': reorder_level,
                'lead_time': lead_time,
                'lc_local': lc_local,
                'remarks': '',
                'total_qty': total_qty,
                'total_amount': total_amount,
                'current_stock_qty': product.qty_available or 0.0,
                'abc': '',
                'xyz': '',
                'efg': ''
            })

        # 4. ABC Classification (Based on Total Issue Amount)
        report_data.sort(key=lambda x: x['total_amount'], reverse=True)
        grand_total_amount = sum(row['total_amount'] for row in report_data)
        
        cumulative_amount = 0.0
        for i, row in enumerate(report_data):
            if i == 0:
                row['abc'] = 'A'
            elif cumulative_amount < (grand_total_amount * 0.1):
                row['abc'] = 'A'
            elif not any(r['abc'] == 'B' for r in report_data[:i]):
                row['abc'] = 'B'
            elif cumulative_amount < (grand_total_amount * 0.3):
                row['abc'] = 'B'
            else:
                row['abc'] = 'C'
            cumulative_amount += row['total_amount']

        # 5. XYZ Classification (Based on Total Issue Quantity)
        report_data.sort(key=lambda x: x['total_qty'], reverse=True)
        grand_total_qty = sum(row['total_qty'] for row in report_data)
        
        cumulative_qty = 0.0
        for i, row in enumerate(report_data):
            if i == 0:
                row['xyz'] = 'X'
            elif cumulative_qty < (grand_total_qty * 0.1):
                row['xyz'] = 'X'
            elif not any(r['xyz'] == 'Y' for r in report_data[:i]):
                row['xyz'] = 'Y'
            elif cumulative_qty < (grand_total_qty * 0.3):
                row['xyz'] = 'Y'
            else:
                row['xyz'] = 'Z'
            cumulative_qty += row['total_qty']

        # 6. EFG Classification (Based on Current Stock Quantity)
        report_data.sort(key=lambda x: x['current_stock_qty'], reverse=True)
        # For EFG, we only considered products with stock in earlier step (filter)? 
        # Actually the filter happens AFTER this? No, it should happen BEFORE classification or classification should only happen on filtered set.
        # User said: "EFG exactly same just the products that are in stock"
        
        # Let's re-filter before classification if report_type is efg
        if report_type == 'efg':
            report_data = [row for row in report_data if row['current_stock_qty'] > 0]
            
        grand_total_stock_qty = sum(row['current_stock_qty'] for row in report_data)
        
        cumulative_stock_qty = 0.0
        for i, row in enumerate(report_data):
            if i == 0:
                row['efg'] = 'E'
            elif cumulative_stock_qty < (grand_total_stock_qty * 0.1):
                row['efg'] = 'E'
            elif not any(r['efg'] == 'F' for r in report_data[:i]):
                row['efg'] = 'F'
            elif cumulative_stock_qty < (grand_total_stock_qty * 0.3):
                row['efg'] = 'F'
            else:
                row['efg'] = 'G'
            cumulative_stock_qty += row['current_stock_qty']
                
        # 7. Final Formatting and Sorting
        if report_type == 'abc':
            report_data.sort(key=lambda x: x['total_amount'], reverse=True)
        elif report_type == 'xyz':
            report_data.sort(key=lambda x: x['total_qty'], reverse=True)
        else:
            report_data.sort(key=lambda x: x['current_stock_qty'], reverse=True)

        return {
            'doc_ids': docids,
            'doc_model': 'indent.analysis.wizard',
            'docs': self.env['indent.analysis.wizard'].browse(docids or []),
            'from_date': from_date,
            'to_date': to_date,
            'report_type': report_type,
            'lines': report_data,
        }
