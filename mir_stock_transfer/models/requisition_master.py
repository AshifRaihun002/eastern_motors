from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class RequisitionMaster(models.Model):
    _inherit = 'custom.purchase.requisition'

    warehouse_src_id = fields.Many2one('stock.warehouse', string='Source Warehouse',
                                       )
    inter_company_transfer_ids = fields.One2many('inter.company.transfer', 'requisition_id', string='Internal Transfers')
    inter_company_transfer_count = fields.Integer(compute='_compute_inter_company_transfer_count',
                                                  string='Internal Transfers', store=True)

    @api.depends('inter_company_transfer_ids')
    def _compute_inter_company_transfer_count(self):
        for rec in self:
            rec.inter_company_transfer_count = len(rec.inter_company_transfer_ids) if rec.inter_company_transfer_ids else 0

    def action_view_internal_transfer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfers'),
            'res_model': 'inter.company.transfer',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.inter_company_transfer_ids.ids)],
            'context': {'create': False, 'delete': False},
        }

    def button_create_internal_transfer(self):
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("Please add at least one product line."))

        transfer_line_ids = []

        for line in self.line_ids:
            product = line.product_id
            from_uom = line.uom_id
            to_uom = product.uom_id
            qty = line.product_uom_qty

            if from_uom and to_uom and from_uom != to_uom:
                qty = from_uom._compute_quantity(qty, to_uom)

            transfer_line_ids.append((0, 0, {
                'product_id': product.id,
                'product_uom_id': to_uom.id,
                'quantity': qty,
                'requisition_line_id': line.id,
            }))

        transfer_vals = {
            'date': fields.Date.context_today(self),
            'source_company_id': self.warehouse_src_id.company_id.id,
            'source_warehouse_id': self.warehouse_src_id.id,
            'source_location_id': self.warehouse_src_id.lot_stock_id.id,
            'destination_company_id': self.warehouse_id.company_id.id,
            'destination_warehouse_id': self.warehouse_id.id,
            'destination_location_id': self.warehouse_id.lot_stock_id.id,
            'requisition_id': self.id,
            'transfer_line_ids': transfer_line_ids,
        }

        try:
            internal_transfer = self.env['inter.company.transfer'].sudo().create(transfer_vals)

            return {
                'type': 'ir.actions.act_window',
                'name': _('Internal Transfer'),
                'res_model': 'inter.company.transfer',
                'view_mode': 'form',
                'res_id': internal_transfer.id,
                'target': 'current',
            }

        except Exception as e:
            _logger.error(e)
            raise UserError(_("Unable to create Internal Transfer! Please check logs or contact admin!"))

class RequisitionLine(models.Model):
    _inherit = 'custom.purchase.requisition.line'

    received_qty = fields.Float('Received Qty', digits='Product Unit of Measure',
                                compute='_compute_qty_delivered')
    # requisition_line_ids = fields.One2many('custom.purchase.requisition.line', 'master_requisition_line_id',
    #                                        string='Requisition Line Ids',
    #                                        help='Requisition Line Ids that belongs to a master requisition line id')

    move_ids = fields.One2many('stock.move', 'requisition_line_id', string='Stock Moves')

    @api.depends('move_ids.state', 'move_ids.product_uom_qty', 'move_ids.product_uom',
                 'purchase_order_line_ids.qty_received', 'requisition_id.line_ids.received_qty',
                 'requisition_id.inter_company_transfer_ids', 'requisition_id.inter_company_transfer_ids.transfer_line_ids.received_quantity')
    def _compute_qty_delivered(self):
        print('Calculating Received Qty', )
        for line in self:
            # TODO: maybe one day, this should be done in SQL for performance sake
            # if line.requisition_type == 'budget':
            #     line.received_qty = sum(l.received_qty for l in line.budget_requisition_line_ids)
            if line.requisition_type == 'use':
                line.received_qty = sum(l.received_qty for l in line.requisition_line_ids if
                                        l.requisition_id.warehouse_id == line.requisition_id.warehouse_id)
            elif line.requisition_type == 'inventory':
                qty = 0.0
                outgoing_moves, incoming_moves = line._get_outgoing_incoming_moves()
                if outgoing_moves or incoming_moves:
                    for move in outgoing_moves:
                        if move.state != 'done':
                            continue
                        qty -= move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom_id,
                                                                  rounding_method='HALF-UP')
                    for move in incoming_moves:
                        if move.state != 'done':
                            continue
                        qty += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom_id,
                                                                  rounding_method='HALF-UP')
                elif line.requisition_id.inter_company_transfer_ids:
                    qty = sum(self.env['inter.company.transfer.line'].sudo().search(
                        [('requisition_line_id', '=', line.id)]).mapped('received_quantity'))
                line.received_qty = qty
            elif line.requisition_id.requisition_type == 'purchase':
                line.received_qty = sum(purchase_line.qty_received for purchase_line in line.purchase_order_line_ids)
            else:
                line.received_qty = 0.0
