from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    class StockPicking(models.Model):
        _inherit = 'stock.picking'

        def _check_purchase_over_receipt_limit(self):
            """Check if received quantity exceeds the allowed over-receipt percentage"""
            for picking in self:
                if picking.picking_type_code == 'incoming' and picking.purchase_id:
                    company = picking.company_id

                    # Skip validation if not active
                    if not company.is_purchase_over_receipt_active:
                        continue

                    # Check each move line against purchase order lines
                    for move in picking.move_ids_without_package:
                        if move.purchase_line_id:
                            po_line = move.purchase_line_id
                            po_qty = po_line.product_qty

                            # Get the quantity being received in THIS move
                            move_qty = move.quantity

                            # Calculate what the total received quantity WILL BE after this picking
                            current_received = po_line.qty_received
                            # Subtract any quantity from this move that might already be counted
                            current_received_from_this_move = sum(
                                move_line.quantity for move_line in move.move_line_ids
                                if move_line.state == 'done'
                            )
                            actual_current_received = current_received - current_received_from_this_move

                            total_will_be_received = actual_current_received + move_qty

                            # Calculate allowed quantity with over-receipt
                            allowed_percentage = 1 + (company.purchase_over_receipt_percentage / 100.0)
                            max_allowed_qty = po_qty * allowed_percentage

                            # Check if the new total will exceed the limit
                            if total_will_be_received > max_allowed_qty:
                                raise ValidationError(
                                    f"Over-receipt limit exceeded for product {move.product_id.display_name}!\n"
                                    f"Purchase Order Qty: {po_qty}\n"
                                    f"Maximum Allowed with {company.purchase_over_receipt_percentage}% over-receipt: {max_allowed_qty:.2f}\n"
                                    f"Currently Received: {actual_current_received:.2f}\n"
                                    f"Trying to Receive: {move_qty:.2f}\n"
                                    f"Total Will Be: {total_will_be_received:.2f}"
                                )

    def button_validate(self):
        """Override validate button to check over-receipt limits"""
        # Check over-receipt before validation
        if any(picking.purchase_id for picking in self):
            self._check_purchase_over_receipt_limit()

        return super(StockPicking, self).button_validate()

    def action_confirm(self):
        """Override confirm action to check over-receipt limits"""
        # Check over-receipt before confirmation
        if any(picking.purchase_id for picking in self):
            self._check_purchase_over_receipt_limit()

        return super(StockPicking, self).action_confirm()
