from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from markupsafe import Markup

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'


    requisition_id = fields.Many2one(
        comodel_name='custom.purchase.requisition',
        string='Purchase Requisition',
        compute='_compute_requisition_id',
    )
    requisition_line_id = fields.Many2one(comodel_name='custom.purchase.requisition.line', string='Requisition Lines')

    size = fields.Char(related="product_id.size", string="Size", store=True)
    pr = fields.Char(related="product_id.pr", string="PR", store=True)
    pattern = fields.Char(related="product_id.pattern", string="Pattern", store=True)
    hs_code = fields.Char(related="product_id.hs_code", string="HS Code", store=True)
    weight = fields.Float(related="product_id.weight", string="Weight", store=True)

    @api.depends('requisition_line_id', 'requisition_line_id.requisition_id')
    def _compute_requisition_id(self):
        """Compute requisition_id from requisition_line_id"""
        for line in self:
            line.requisition_id = line.requisition_line_id.requisition_id if line.requisition_line_id else False


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    indent_reference = fields.Text(string='Indent Reference')
    vendor_delivery_status = fields.Selection(
                                              [('eta', 'Estimated Time Of Arrival'),
                                              ('etd', 'Estimated Time of Departure')],
                                              string='Vendor Delivery Status',tracking=True,)
    ven_delivery_state_date = fields.Date(string='Vendor Delivery Status Date', tracking=True)
    last_po_notification_date = fields.Date(
        string="Last PO Notification Date",
    )
    order_status = fields.Selection([('at_port','At Port'),('nn_board', 'On Board'),
                                     ('under_ship','Under Shipment'),
                                     ('goods_in_order', 'Good In Order'),
                                     ('closed','Closed')], string='Order Status', tracking=True)

    order_status_record_ids = fields.One2many(
        'purchase.order.status.history',
        'purchase_order_id',
        string='Order Status History'
    )

    def action_open_order_status_wizard(self):
        self.ensure_one()
        return {
            'name': _('Update Order Status'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
                'default_current_status': self.order_status,
            }
        }

    def action_send_po_group_email(self):
        self.ensure_one()

        group = self.env.ref(
            'custom_purchase_requisition.group_po_delivery_notification',
            raise_if_not_found=False
        )
        if not group:
            raise ValidationError(_("Notification group not found."))

        users = group.user_ids.filtered(lambda u: u.active and u.email)
        if not users:
            raise ValidationError(_("No active users with email found in the notification group."))

        email_to = ",".join(users.mapped("email"))

        body_html = f"""
            <p>PO Information</p>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr>
                    <td><strong>PO Number</strong></td>
                    <td>{self.name or ''}</td>
                </tr>
                <tr>
                    <td><strong>Vendor</strong></td>
                    <td>{self.partner_id.name or ''}</td>
                </tr>
                <tr>
                    <td><strong>PO Value</strong></td>
                    <td>{self.amount_total or 0.0}</td>
                </tr>
                <tr>
                    <td><strong>Vendor Delivery Date</strong></td>
                    <td>{self.ven_delivery_state_date or ''}</td>
                </tr>
            </table>
        """

        mail_values = {
            'subject': _('PO Delivery Reminder - %s') % (self.name or ''),
            'email_to': email_to,
            'email_from': self.env.user.email or self.company_id.email or '',
            'body_html': body_html,
        }

        self.env['mail.mail'].sudo().create(mail_values).send()

        self.message_post(body=_("PO notification email sent to the configured group users."))

    @api.model
    def cron_send_po_group_email(self):
        interval_days = self.env.company.po_notification_send_interval or 0

        if interval_days <= 0:
            return

        today = fields.Date.today()
        target_date = today + timedelta(days=interval_days)

        po_records = self.search([
            ('ven_delivery_state_date', '=', target_date),
            ('state', 'in', ['purchase']),
        ])

        for po in po_records:
            po.action_send_po_group_email()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    po_notification_send_interval = fields.Integer(
        related='company_id.po_notification_send_interval',
        readonly=False,
        string='PO Notification Send Interval (Days)'
    )

class ResCompany(models.Model):
    _inherit = 'res.company'

    po_notification_send_interval = fields.Integer(
        string="PO Notification Send Interval (Days)",
        default=7
    )

class PurchaseOrderStatusHistory(models.Model):
    _name = 'purchase.order.status.history'
    _description = 'Purchase Order Status History'
    _order = 'action_date desc, id desc'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        required=True,
        ondelete='cascade'
    )

    field_name = fields.Char(
        string='Field Name',
        default='order_status',
        required=True
    )

    from_state = fields.Selection(
        [
            ('at_port', 'At Port'),
            ('nn_board', 'On Board'),
            ('under_ship', 'Under Shipment'),
            ('goods_in_order', 'Good In Order'),
            ('closed', 'Closed')
        ],
        string='From State'
    )

    to_state = fields.Selection(
        [
            ('at_port', 'At Port'),
            ('nn_board', 'On Board'),
            ('under_ship', 'Under Shipment'),
            ('goods_in_order', 'Good In Order'),
            ('closed', 'Closed')
        ],
        string='To State',
        required=True
    )

    action_date = fields.Datetime(
        string='Action Time',
        default=fields.Datetime.now,
        required=True
    )

    action_by = fields.Many2one(
        'res.users',
        string='Action Taken By',
        default=lambda self: self.env.user,
        required=True
    )

    remarks = fields.Text(string='Remarks')