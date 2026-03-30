from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime


class StockPicking(models.Model):
    _inherit = "stock.picking"

    lc_id = fields.Many2one(
        related="purchase_id.lc_id", store=False, readonly=True
    )

    # def button_validate(self):
    #     # Filter records where the related L/C state is not done and raise an error
    #     if any(picking.lc_id and picking.lc_id.state != "done" for picking in self):
    #         raise ValidationError(_("L/C is not completed yet."))
    #
    #     # Proceed with the normal validation process
    #     return super(StockPicking, self).button_validate()

class StockMove(models.Model):
    _inherit = "stock.move"

    shipment_id = fields.Many2one("lc.shipment", string="Shipment")
    shipment_line_id = fields.Many2one("lc.shipment.line", string="Shipment Line")


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    shipment_id = fields.Many2one(
        'lc.shipment',
        string='LC Shipment',
        related='move_id.shipment_id',
        store=True
    )

    shipment_line_id = fields.Many2one(
        'lc.shipment.line',
        string='Shipment Line',
        related='move_id.shipment_line_id',
        store=True
    )


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    lc_shipment_id = fields.Many2one(
        'lc.shipment',
        string='LC Shipment',
        copy=False,
        ondelete='set null',
        index=True
    )


class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    lc_shipment_id = fields.Many2one(
        'lc.shipment',
        string='LC Shipment',
        related='move_id.lc_shipment_id',
        store=True,
        readonly=True,
        index=True
    )

    lc_shipment_line_id = fields.Many2one(
        'lc.shipment.line',
        string='Shipment Line',
        copy=False,
        ondelete='set null',
        index=True
    )