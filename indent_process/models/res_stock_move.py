from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class StockMove(models.Model):
    _inherit = 'stock.move'

    indent_line_id = fields.Many2one('indent.line', string='Indent Line')
    indent_id = fields.Many2one('indent.process', string='Indent Process', related='indent_line_id.indent_id')
    priority = fields.Selection(
        selection_add=[
            ('1', 'Low'), ('2', 'High'), ('3', 'Urgent'),
        ], ondelete={'1': 'set default', '2': 'set default', '3': 'set default'}
    )

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    indent_line_id = fields.Many2one('indent.line', string='Indent Line', related='move_id.indent_line_id', store=True)
    indent_id = fields.Many2one('indent.process', string='Indent Process', related='move_id.indent_id', store=True)
