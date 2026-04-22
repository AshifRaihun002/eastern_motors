from odoo import api, fields, models


class SmsOutboxDetails(models.Model):
    _name = 'sms.outbox.details'
    _description = 'Sms Outbox Details'
    _order = 'id desc'
    _rec_name = 'mobile_no'

    module_name = fields.Selection(
        [('1', 'General'),
         ('2', 'Purchase'),
         ('3', 'Inventory'),
         ('4', 'Sale'),
         ('5', 'POS'),
         ('6', 'HR'),
         ('7', 'Accounts'),
         ('8', 'E-Commerce'),
         ('9', 'Service'),
         ('10', 'Marketing'),
         ],
        'Module', default='1', required=True)

    source_ref = fields.Char('Source Ref', size=100, default='')
    mobile_no = fields.Char('Mobile No', size=20, required=True)
    msg_body = fields.Text('Message', required=True)
    msg_id = fields.Char(string='Message ID')
    error_msg = fields.Char('Error msg', size=200, default='')
    status = fields.Selection(
        [('1', 'Ready'), ('2', 'Sent'), ('3', 'Error')],
        'Status', default='1', required=True)

    is_header_sent = fields.Boolean('Header Sent?', default=False)
    is_footer_sent = fields.Boolean('Footer Sent?', default=False)
    header_text = fields.Char('Header Text', size=100, default='')
    footer_text = fields.Char('Footer Text', size=100, default='')

    @api.model
    def send_sms(self):
        sms_obj = self.env['sms.mail.server'].sudo()

        # -----------
        outbox_rows = self.env['sms.outbox.details'].search([('status', '=', '1')], order='id', limit=100)
        if outbox_rows:
            for rec in outbox_rows:
                mobile_no = str(rec.mobile_no).replace("+", "").replace(" ", "").replace("-", "").strip()
                msg_text = rec.msg_body

                if rec.is_header_sent == True:
                    msg_text = "%s\n%s" % (rec.header_text, msg_text)

                if rec.is_footer_sent == True:
                    msg_text = "%s\n%s" % (msg_text, rec.footer_text)

                if len(mobile_no) > 11:
                    mobile_no = str('+88') + str(mobile_no)[-11:]
                elif len(mobile_no) == 11:
                    mobile_no = '+88' + mobile_no
                elif len(mobile_no) == 10:
                    mobile_no = '+880' + mobile_no

                try:
                    if len(mobile_no) != 14:  # +8801719078552
                        rec.write({'status': '3', 'error_msg': 'Invalid Mobile No'})
                        continue

                except:
                    rec.write({'status': '3', 'error_msg': 'Invalid Mobile No'})
                    continue

                # -----------
                try:
                    # sent function call
                    sms_id = 'SOB' + str(rec.id)
                    response = sms_obj.custom_send_sms_api(sms_id, mobile_no, msg_text)
                    if response:
                        resList = response.split('::')
                        if resList[0] == 'success':
                            rec.write({'status': '2', 'msg_id': resList[1]})
                        else:
                            rec.write({'status': '3', 'error_msg': resList[1]})

                    # result = response.text
                    # my_dict = xmltodict.parse(result)
                    #
                    # res_message_id = my_dict['ArrayOfServiceClass']['ServiceClass']['MessageId']
                    # #res_status = my_dict['ArrayOfServiceClass']['ServiceClass']['Status']
                    # res_error_code = my_dict['ArrayOfServiceClass']['ServiceClass']['ErrorCode']
                    # res_error_msg = my_dict['ArrayOfServiceClass']['ServiceClass']['ErrorText']
                    #
                    # #'result----------',Error or NotError
                    # if str(res_error_code) == '0':
                    #     rec.write({'msg_id':res_message_id,'status': '2'})
                    # else:
                    #     rec.write({'msg_id':res_message_id,'status': '3','error_msg':res_error_msg})
                except:
                    rec.write({'status': '3', 'error_msg': 'Invalid Request'})

        else:
            return ""
