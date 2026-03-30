from odoo import models, api, fields, _
from datetime import datetime

class IndentReport(models.AbstractModel):
    _name = 'report.indent_process.indent_report_template'
    _description = 'Indent Report Abstract Model'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form'):
            return {}

        form = data.get('form')
        from_date = fields.Date.to_date(form.get('from_date'))
        to_date = fields.Date.to_date(form.get('to_date'))
        company_id = form.get('company_id')
        product_ids = form.get('product_ids')
        status = form.get('status')

        # 1. Fetch move lines based on filters
        move_line_domain = [
            ('date', '>=', datetime.combine(from_date, datetime.min.time())),
            ('date', '<=', datetime.combine(to_date, datetime.max.time())),
            ('state', '=', 'done'),
            ('indent_id', '!=', False)
        ]
        if company_id:
            move_line_domain.append(('company_id', '=', company_id[0]))
        if product_ids:
            move_line_domain.append(('product_id', 'in', product_ids))
        
        # Note: 'status' filter on indent.line might need careful handling if we filter move lines.
        # If status is selected, we might want to filter move lines belonging to indents with that status.
        if status:
            move_line_domain.append(('indent_line_id.issue_status', '=', status))

        move_lines = self.env['stock.move.line'].search(move_line_domain)
        
        report_data = []
        processed_indent_line_ids = set()

        for ml in move_lines:
            # Skip if it's a return move line (handle returns inside prepare_line_data or skip here)
            if ml.move_id.origin_returned_move_id:
                continue
            
            report_data.append(self._prepare_line_data_from_move_line(ml))
            processed_indent_line_ids.add(ml.indent_line_id.id)

        # 2. Fetch Indents that match filters but have no moves (Pending)
        # OR if status is 'pending', we focus on these.
        if status in [False, 'pending']:
            indent_line_domain = [
                ('indent_date', '>=', from_date),
                ('indent_date', '<=', to_date),
                ('issue_status', '=', 'pending')
            ]
            if company_id:
                indent_line_domain.append(('company_id', '=', company_id[0]))
            if product_ids:
                indent_line_domain.append(('product_id', 'in', product_ids))
            
            indent_lines_no_moves = self.env['indent.line'].search(indent_line_domain)
            for il in indent_lines_no_moves:
                if il.id not in processed_indent_line_ids:
                    report_data.append(self._prepare_line_data_from_indent_line(il))

        return {
            'doc_ids': docids,
            'doc_model': 'indent.report.wizard',
            'docs': self.env['indent.report.wizard'].browse(docids or []),
            'from_date': from_date,
            'to_date': to_date,
            'lines': report_data,
        }

    def _prepare_line_data_from_move_line(self, ml):
        """Prepare report row from a stock.move.line record."""
        line = ml.indent_line_id
        move = ml.move_id
        picking = ml.picking_id
        
        issue_qty = ml.quantity
        
        # Calculate return qty for this specific move line?
        # A return usually references the original move, not specifically the move line.
        # But we can try to find return move lines for the same product in the same picking (backwards)
        return_qty = 0.0
        # This is a bit complex for move lines. Usually, returns are new moves referencing the original.
        # For now, let's stick to the move-level logic if specific line-level return tracking isn't clear.
        # Search for moves returned from this move
        return_moves = self.env['stock.move'].search([
            ('origin_returned_move_id', '=', move.id),
            ('state', '=', 'done')
        ])
        # proportional return qty for this move line if multiple move lines exist? 
        # Usually internal transfers for indents don't split that much.
        if len(move.move_line_ids) > 1:
            total_move_qty = sum(move.move_line_ids.mapped('quantity'))
            move_return_qty = sum(return_moves.mapped('quantity'))
            if total_move_qty > 0:
                return_qty = (issue_qty / total_move_qty) * move_return_qty
        else:
            return_qty = sum(return_moves.mapped('quantity'))

        net_issue_qty = issue_qty - return_qty
        unit_rate = move.unit_rate if hasattr(move, 'unit_rate') else line.product_id.standard_price
        
        shipment_no = picking.name
        shipment_date = picking.scheduled_date
        supplier_name = picking.partner_id.name if picking.partner_id else ''

        mfg_date = ml.manufacturing_data if hasattr(ml, 'manufacturing_data') else False
        exp_date = ml.expiry_data if hasattr(ml, 'expiry_data') else False
        
        lot_name = ml.lot_id.name if ml.lot_id else ''
        if not mfg_date or not exp_date:
            if ml.lot_id:
                mfg_date = ml.lot_id.manufacture_date if hasattr(ml.lot_id, 'manufacture_date') else mfg_date
                exp_date = ml.lot_id.expiration_date if hasattr(ml.lot_id, 'expiration_date') else exp_date

        return {
            'indent_no': line.indent_id.name,
            'indent_date': line.indent_date,
            'product_name': f"{line.product_id.name}[{line.product_id.default_code or ''}]",
            'internal_name': line.product_id.default_code or '',
            'uom': line.product_uom.name,
            'status': dict(line._fields['issue_status'].selection).get(line.issue_status, ''),
            'indent_qty': line.quantity,
            'issue_date': ml.date.date(),
            'to_dept': line.department_id.name,
            'issue_qty': issue_qty,
            'return_qty': return_qty,
            'lot_id': lot_name,
            'net_issue_qty': net_issue_qty,
            'unit_rate': unit_rate,
            'issue_amt': net_issue_qty * unit_rate,
            'user_name': picking.write_uid.employee_id.barcode if picking.write_uid.employee_id else picking.write_uid.name,
            'shipment_no': shipment_no,
            'shipment_date': shipment_date,
            'supplier_name': supplier_name,
            'mfg_date': mfg_date,
            'exp_date': exp_date,
            'comment': '', 
            'remarks': line.remarks or '',
        }

    def _prepare_line_data_from_indent_line(self, line):
        """Prepare report row for an indent line with no issues."""
        return {
            'indent_no': line.indent_id.name,
            'indent_date': line.indent_date,
            'product_name': f"{line.product_id.name}[{line.product_id.default_code or ''}]",
            'internal_name': line.product_id.default_code or '',
            'uom': line.product_uom.name,
            'status': dict(line._fields['issue_status'].selection).get(line.issue_status, ''),
            'indent_qty': line.quantity,
            'issue_date': False,
            'to_dept': line.department_id.name,
            'issue_qty': 0.0,
            'return_qty': 0.0,
            'lot_id': '',
            'net_issue_qty': 0.0,
            'unit_rate': line.product_id.standard_price,
            'issue_amt': 0.0,
            'user_name': '',
            'shipment_no': '',
            'shipment_date': False,
            'supplier_name': '',
            'mfg_date': False,
            'exp_date': False,
            'comment': '',
            'remarks': line.remarks or '',
        }
