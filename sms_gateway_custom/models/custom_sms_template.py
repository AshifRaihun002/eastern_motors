from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.addons.helper import validator

class SMSTemplateCustom(models.Model):
    _name = "sms.template.custom"
    _description = "SMS Template Information"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"
    _rec_name = "type"

    sms_format = fields.Text(string='SMS Format', required=True, copy=True)
    type = fields.Selection([
        ('purchase', 'Purchase'),
        ('bill', 'Bill'),
        ('sale', 'Sale'),
        ('invoice', 'Invoice'),
        ('delivery', 'Delivery'),
        ('pos', 'POS'),
        ('pos_sp_disc', 'POS Special discount'),
        ('payment', 'Payment'),
        ('hr', 'HR'),
        ('account', 'Accounts'),
        ('service', 'Service'),
        ('marketing', 'Marketing'),
        ('gift_card_sale', 'Gift Card Sale'),
        ('warranty_service', 'Warranty Service'),
        ('hr_salary', 'HR Salary'),
        ('hr_pf', 'HR PF'),
    ], string='Type', copy=False, index=True, help="Sale:$customer_name,$sale_amount,$order_no; Delivery:$order_no,$delivery_no;")

    format_no = fields.Selection([
        ('1', '1st'),
        ('2', '2nd'),
        ('3', '3rd'),
    ], string='Format Number', copy=False, index=True, tracking=4)
    is_active = fields.Boolean(default=False, string='Active', copy=False)

    is_header_sent = fields.Boolean(string='Header Sent?', default=False)
    is_footer_sent = fields.Boolean(string='Footer Sent?', default=False)
    header_text = fields.Char('Header Text', size=100, default='')
    footer_text = fields.Char('Footer Text', size=100, default='')

    @api.constrains('type', 'format_no')
    def _check_unique_constraint_duplicate(self):
        for rec in self:
            msg = 'SMS Format "%s"' % rec.format_no
            envobj = self.env['sms.template.custom']
            conditionlist = [('type', '=', rec.type), ('format_no', '=', rec.format_no)]
            validator.check_duplicate_value(rec, envobj, conditionlist, msg)


