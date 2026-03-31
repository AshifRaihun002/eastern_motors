from odoo import fields, models, _
from odoo.exceptions import UserError


class PurchaseOrderStatusWizard(models.TransientModel):
    _name = 'purchase.order.status.wizard'
    _description = 'Purchase Order Status Update Wizard'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True
    )

    current_status = fields.Selection(
        [
            ('at_port', 'At Port'),
            ('nn_board', 'On Board'),
            ('under_ship', 'Under Shipment'),
            ('goods_in_order', 'Good In Order'),
            ('closed', 'Closed')
        ],
        string='Current Status',
        readonly=True
    )

    new_status = fields.Selection(
        [
            ('at_port', 'At Port'),
            ('nn_board', 'On Board'),
            ('under_ship', 'Under Shipment'),
            ('goods_in_order', 'Good In Order'),
            ('closed', 'Closed')
        ],
        string='New Status',
        required=True
    )

    remarks = fields.Text(string='Remarks')

    def action_update_status(self):
        self.ensure_one()

        po = self.purchase_order_id
        if not po:
            raise UserError(_("Purchase Order not found."))

        old_status = po.order_status
        new_status = self.new_status

        if old_status == new_status:
            raise UserError(_("The new status must be different from the current status."))

        po.write({
            'order_status': new_status,
        })

        self.env['purchase.order.status.history'].create({
            'purchase_order_id': po.id,
            'field_name': 'order_status',
            'from_state': old_status,
            'to_state': new_status,
            'action_date': fields.Datetime.now(),
            'action_by': self.env.user.id,
            'remarks': self.remarks,
        })

        return {'type': 'ir.actions.act_window_close'}