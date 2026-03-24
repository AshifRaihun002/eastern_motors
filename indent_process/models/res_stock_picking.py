from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime
from odoo import Command


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    priority = fields.Selection(
        selection_add=[
            ('1', 'Low'), ('2', 'High'), ('3', 'Urgent'),
        ], ondelete={'1': 'set default', '2': 'set default', '3': 'set default'}
    )
    indent_id = fields.Many2one(
        'indent.process',
        string='Indent',
        store=True
    )

    is_indent_issue = fields.Boolean(string="Indent Issue", default=False)
    is_indent_transfer = fields.Boolean(string='Is Indent Transfer', default=False)

    def button_validate(self):
        for picking in self:
            if picking.picking_type_id.code != 'internal':
                continue

            for move in picking.move_ids:
                demand = move.product_uom_qty
                done = sum(move.move_line_ids.mapped('quantity'))

                if float_compare(done, demand, precision_rounding=move.product_uom.rounding) > 0:
                    raise ValidationError(_(
                        "You can't receive more than demanded for %(product)s.\n"
                        "Demanded: %(demand)s %(uom)s\n"
                        "Received: %(done)s %(uom)s"
                    ) % {
                        'product': move.product_id.display_name,
                        'demand': demand,
                        'done': done,
                        'uom': move.product_uom.name,
                    })

        return super().button_validate()

        # @api.depends('move_ids.indent_line_id.indent_id')
        # def _compute_indent_id(self):
        #     for picking in self:
        #         # Get indent_id from moves
        #         moves_with_indent = picking.move_ids_without_package.filtered(
        #             lambda m: m.indent_line_id and m.indent_line_id.indent_id
        #         )
        #         if moves_with_indent:
        #             # Assuming all moves belong to same indent
        #             picking.indent_id = moves_with_indent[0].indent_line_id.indent_id
        #         else:
        #             picking.indent_id = False

    @api.onchange('indent_id')
    def _onchange_indent_id(self):
        for picking in self:

            if not picking.indent_id:
                picking.move_ids = [(5, 0, 0)]

            moves = [Command.clear()]

            for line in picking.indent_id.indent_line_ids:
                moves.append(Command.create({
                    # 'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_uom.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'indent_line_id': line.id,
                    'indent_id': picking.indent_id.id,
                }))

            picking.move_ids = moves


    def _is_backorder_picking(self, picking):
        """Check if this picking is a backorder"""
        # Method 1: Check if picking has backorder_id field set
        if hasattr(picking, 'backorder_id') and picking.backorder_id:
            return True

        # Method 2: Check origin for backorder keywords
        if picking.origin and any(keyword in picking.origin for keyword in ['Backorder of', 'Backorder', 'backorder']):
            return True

        # Method 3: Check if created from another picking's partial validation
        if picking.name and picking.name.startswith('BO/'):
            return True

        # Method 4: Check if there's a backorder_id field in the model
        if 'backorder_id' in self.env['stock.picking']._fields and picking.backorder_id:
            return True

        return False


