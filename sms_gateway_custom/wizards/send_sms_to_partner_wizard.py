from odoo import models, fields, _
from odoo.exceptions import UserError

class SendSMSToPartnerWizard(models.TransientModel):
    _name = "send.sms.to.partner.wizard"
    _description = "Send SMS To Partner Wizard"

    body = fields.Text(string="Message")

    def action_send_sms(self):
        active_id = self.env.context.get("active_id")
        partner_id = self.env['res.partner'].browse(active_id)

        sms_obj = self.env['sms.outbox.details']

        mobile = ''
        if partner_id.phone:
            mobile = partner_id.phone
        else:
            raise UserError(_('Required Customer Mobile No.'))

        sms_data = {
            'module_name': '10',
            'mobile_no': mobile,
            'msg_body': self.body,
        }

        sms_obj.sudo().create(sms_data)

        return True