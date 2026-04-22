from odoo import api, fields, models, _

import requests
import random
import json


class SMSMailServer(models.Model):
    _name = "sms.mail.server"
    _description = "SMS Mail Server"
    _rec_name = "description"

    @api.model
    def get_reference_type(self):
        return ['SSL Wireless', 'Route Mobile']

    @api.model
    def _get_mob_no(self):
        user_obj = self.env['res.users'].browse([self._uid])
        return user_obj.mob_number

    @api.model
    def _set_mob_no(self):
        user_obj = self.env['res.users'].browse([self._uid])
        user_obj.write({'mob_number': self.user_mobile_no})

    gateway = fields.Selection([
        ("ssl_wireless", "SSL Wireless"),
        ("routemobile", "Route Mobile"),
        ("boomcast", "Boom Cast")
    ],
        string="Gateway", required=True, help="""SSL Wireless Parameters:ssl_url, api_token,SID_NAME,SMS Text,Mobile Number,cust_id ;Route Mobile Parameters: ssl_url,username,password,message-type,dlr,source. [destination,message];
                           Boom Cast Parameters: ssl_url, user_name, password [destination,message]""")

    description = fields.Char(string="Description", required=True)
    sequence = fields.Integer(string='Priority',
                              help="Default Priority will be 0. Auto SMS will be sent from  priority=0.")
    sms_debug = fields.Boolean(string="Debugging",
                               help="If enabled, the error message of sms gateway will be written to the log file")
    user_mobile_no = fields.Char(string="Mobile No.", help="Eleven digit mobile number with country code(e.g +88)")
    # gateway = fields.Selection('get_reference_type')
    # gateway = fields.Char(string="Gateway", required=True)
    ssl_url = fields.Char(string="URL", widget="url", required=True)
    ssl_user_name = fields.Char(string="User Name", required=True, help="The username of the HTTP account.")
    ssl_password = fields.Char(string="Password", required=True, help="The password of the HTTP account.")

    # -----extra for routemobile
    msg_type = fields.Selection([
        ("0", "Plain text (GSM 3.38 Character encoding)"),
        ("1", "Flash (GSM 3.38 Character encoding)"),
        ("2", "Unicode"),
        ("3", "Reserved"),
        ("4", "WAP Push"),
        ("5", "Plain text (ISO-8859-1 Character encoding)"),
        ("6", "Unicode Flash"),
        ("7", "Flash (ISO-8859-1 Character encoding)")
    ],
        string="Message Type", help="It indicates the type of message. Values for type include")
    dlr = fields.Selection([
        ("0", "No delivery report required"),
        ("1", "Delivery report required")
    ],
        string="DLR",
        help="Indicates whether the client wants delivery report for this message. The values for dlr include:")
    msg_source = fields.Char(string="Source", help="""The source address that should appear in the message.
                                                             Max Length of 18 if numeric.
                                                             Max Length of 11 if alphanumeric.
                                                            To prefix the plus sign (+) to the sender’s address when the message
                                                            is displayed on their cell phone, please prefix the plus sign to your
                                                            sender’s address while submitting the message (note the plus sign
                                                            should be URL encoded). Additional restrictions on this field may be
                                                            enforced by the SMSC.""")
    api_token = fields.Char(string="API TOKEN", help="""API Token Proved by SMS Provider.""")
    # ----------
    ssl_sid_new = fields.Many2one('sms.mail.sender', string="Sender ID (SID)", required=True)

    ssl_sid = fields.Selection([("green_dot", "Green Dot"), ("ogroni", "Ogroni"), ("top_ten", "Top Ten")],
                               string="Sender Id", default='ogroni')  # not used
    active = fields.Boolean(default=True)

    test_response_msg = fields.Char(string="Test Result:", help="""Test result response message.""")

    def test_conn_ssl(self):
        self.ensure_one()
        self.test_response_msg = ""
        gateway = self.gateway
        mobile_number = self.user_mobile_no

        mob_numbers_list = mobile_number.split(",")
        sms_text = "This is e test SMS, sent from ERP. Test by Ogroni Informatix Limited"

        # data = {
        #     "user": self.ssl_user_name,
        #     "pass": self.ssl_password,
        #     "sid": self.ssl_sid_new,
        # }

        try:
            ssl_url = self.ssl_url
            user_name = self.ssl_user_name
            password = self.ssl_password
            msg_type = self.msg_type
            dlr = self.dlr
            source = self.msg_source
            api_token = str(self.api_token)
            ssl_sid_new = str(self.ssl_sid_new.name) or ''

            mob_no = ''
            # ------------
            # year = str(datetime.now().year)
            # month = str(datetime.now().month).zfill(2)
            # day = str(datetime.now().day).zfill(2)
            # hour = str((datetime.now() + timedelta(hours=6)).hour).zfill(2)
            # minute = str(datetime.now().minute).zfill(2)
            # second = str(datetime.now().second).zfill(2)
            sms_id = 'TST' + str(random.randint(1000000000, 9999999999));
            sms_text_quote = ''
            for mob_no in mob_numbers_list:

                if gateway == 'ssl_wireless':
                    # sms_text_quote = urllib.parse.quote(sms_text, safe='')

                    if len(mob_no) != 13:
                        if len(mob_no) == 11:
                            mob_no = '88' + mob_no
                        elif len(mob_no) == 10:
                            mob_no = '880' + mob_no

                    try:
                        mob_no = int(mob_no)
                    except:
                        return 'Failed! Invalid Mobile. Sample: 8801700000001 or 01700000001'

                else:
                    if len(mob_no) >= 13:
                        mob_no = mob_no
                    else:
                        tmp_mob = mob_no[-11:]
                        mob_no = str('+88') + str(tmp_mob)
                        # mob_no = str(tmp_mob)
                # ----------------------
                request_url = ''
                if gateway == 'routemobile':
                    request_url = '{0}?username={1}&password={2}&type={3}&dlr={4}&destination={5}&source={6}&message={7}'.format(
                        ssl_url, user_name, password, msg_type, dlr, mob_no, source, sms_text)
                elif gateway == 'boomcast':
                    msg_type = 'TEXT'
                    request_url = "{0}&userName={1}&password={2}&MsgType={3}&receiver={4}&message={5}".format(ssl_url,
                                                                                                              user_name,
                                                                                                              password,
                                                                                                              msg_type,
                                                                                                              mob_no,
                                                                                                              sms_text)
                elif gateway == 'ssl_wireless':
                    request_url = "{0}?api_token={1}&sid={2}&msisdn={3}&sms={4}&csms_id={5}".format(ssl_url, api_token,
                                                                                                    ssl_sid_new,
                                                                                                    str(mob_no),
                                                                                                    sms_text, sms_id)
                else:
                    pass
                # print('request_url--------',request_url)
                # numbers = self.format_mobile_numbers(numbers)
                if request_url:
                    if gateway == 'ssl_wireless':
                        response = requests.get(url=request_url)
                        result = json.loads(response.text)

                        # print('result-----------',result)
                        # my_dict = xmltodict.parse(result)
                        if response.status_code == 200:
                            status = result['status']
                            status_code = result['status_code']
                            error_message = result['error_message']
                            if str(status_code) == '200':
                                result = 'Status: ' + str(status) + ', Status Code: ' + str(
                                    status_code) + ', Status Meaning: ' + str(error_message)
                            else:
                                result = 'Status: ' + str(status) + ', Status Code: ' + str(
                                    status_code) + ', Status Meaning: ' + str(error_message)
                        else:
                            result = 'failed: server_error!'

                        self.test_response_msg = result

                    else:
                        resp = requests.post(request_url)
                        response_content = resp._content.decode('utf-8')
                        self.test_response_msg = response_content

        except Exception as e:
            print(e)

        return True

    # running func
    def custom_send_sms_api(self, sms_id, numbers, message):
        # sms_server = self.env['sms.mail.server'].browse(1)
        sms_server_obj = self.env['sms.mail.server'].search([('sequence', '=', 1)], limit=1)
        if sms_server_obj:
            gateway = sms_server_obj.gateway
            ssl_url = sms_server_obj.ssl_url
            user_name = sms_server_obj.ssl_user_name
            password = sms_server_obj.ssl_password
            msg_type = sms_server_obj.msg_type
            dlr = sms_server_obj.dlr
            source = sms_server_obj.msg_source
            api_token = str(sms_server_obj.api_token)
            ssl_sid_new = str(sms_server_obj.ssl_sid_new.name) or ''

            # dlr = 1
            # smstype = 'TEXT'
            # source = 'Ogroni'

            # numbers = '01673561755|01717782151'
            # numbers = self.format_mobile_numbers(numbers)
            numbers = str('+88') + str(numbers)[-11:]

            request_url = ''
            if gateway == 'ssl_wireless':
                request_url = "{0}?api_token={1}&sid={2}&msisdn={3}&sms={4}&csms_id={5}".format(ssl_url, api_token,
                                                                                                ssl_sid_new,
                                                                                                str(numbers),
                                                                                                message, sms_id)

                response = requests.get(url=request_url)
                result = json.loads(response.text)

                # print('result-----------',result)
                # my_dict = xmltodict.parse(result)
                if response.status_code == 200:
                    status = result['status']
                    status_code = result['status_code']
                    error_message = result['error_message']
                    if str(status_code) == '200':
                        result = 'success::' + 'Status: ' + str(status) + ', Status Code: ' + str(
                            status_code) + ', Status Meaning: ' + str(error_message)
                    else:
                        result = 'success::' + 'Status: ' + str(status) + ', Status Code: ' + str(
                            status_code) + ', Status Meaning: ' + str(error_message)
                else:
                    result = 'failed:: server_error!'

                return result

            elif gateway == 'routemobile':
                request_url = '{0}?username={1}&password={2}&type={3}&dlr={4}&destination={5}&source={6}&message={7}'.format(
                    ssl_url, user_name, password, msg_type, dlr, numbers, source, message)
                response = requests.post(request_url)
                result = ''
                if response.status_code == 200:
                    response_content = response._content.decode('utf-8')
                    respList = response_content.split('|')
                    if str(respList[0]) == '1701':
                        result = 'success::' + str(respList[2])
                    else:
                        result = 'failed::ErrorCode ' + str(respList[0])
                else:
                    result = 'failed::server_error'

                return result

            elif gateway == 'boomcast':
                msg_type = 'TEXT'
                request_url = "{0}&userName={1}&password={2}&MsgType={3}&receiver={4}&message={5}".format(ssl_url,
                                                                                                          user_name,
                                                                                                          password,
                                                                                                          msg_type,
                                                                                                          numbers,
                                                                                                          message)
                response = requests.post(request_url)
                result = ''
                if response.status_code == 200:
                    result = 'success::NA'
                else:
                    result = 'failed::server_error'

                return result
            else:
                pass

            # if request_url:
            #     resp = requests.post(request_url)
            #     response_content = resp._content.decode('utf-8')
            #     return resp

        # request_url = "{0}&userName={1}&password={2}&MsgType={3}&receiver={4}&message={5}".format(ssl_url, user_name, password, smstype, numbers, message)
        # resp = requests.post(request_url)
        # response_content = resp._content.decode('utf-8')

    def format_mobile_numbers(self, numbers):
        numbers_str = ''
        for number in numbers:
            numbers_str += str(number)[-11:] + "|"

        if numbers_str.endswith("|"):
            numbers_str = numbers_str[:-1]

        return numbers_str
