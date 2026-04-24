from odoo import models

class InheritedResPartnerInheritSMSGatewayCustom(models.Model):
    _inherit = "res.partner"
    _description = "Inherited Res Partner Inherit SMS Gateway Custom"

    def send_sms_partner(self):
        form_view_id = self.env.ref('sms_gateway_custom.view_send_sms_to_partner_wizard_form').id

        return {
            'name': 'Send SMS Text Message',
            'type': 'ir.actions.act_window',
            'res_model': 'send.sms.to.partner.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(form_view_id, 'form')],
            'view_id': form_view_id,
            'res_id': False,
            'target': 'new',
        }