from odoo import models, fields, api, _
from odoo.addons.helper import validator

class SMSMailSender(models.Model):
    _name = "sms.mail.sender"
    _description = "SMS Mail Sender Information"
    _order = "name"

    name = fields.Char(string="Name", required=True, copy=False, default="/")
    active = fields.Boolean(string="Active", default=True, copy=False)

    @api.constrains("name")
    def _check_unique_constraint_name(self):
        for rec in self:
            msg = 'Name "%s"' % rec.name
            envobj = self.env['sms.mail.sender']
            conditionlist = [('name', '=ilike', rec.name)]
            validator.check_duplicate_value(rec, envobj, conditionlist, msg)