from odoo import api, exceptions
import re
from odoo import _
# from odoo.exceptions import except_orm, Warning, RedirectWarning
#from unidecode import unidecode
from datetime import datetime
from odoo.exceptions import UserError

def _validate_email(self, vals, str):
    if vals:
        if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", vals) == None:
            raise exceptions.ValidationError(str + " Email '%s' is not valid." %(vals))


def _valid_phone_number(self, vals, str):
    if vals:
        s_phone = vals.encode('ascii', 'ignore').decode('ascii')
        if re.match(r"^\+?[\d-]*$", s_phone) == None:
            raise exceptions.ValidationError(str + " not valid.")


def _validate_url(self, vals, str):
    if vals:
        if re.match(r'https?://(?:www)?(?:[\w-]{2,255}(?:\.\w{2,6}){1,2})(?:/[\w&%?#-]{1,300})?', self.website) is None:
            raise exceptions.ValidationError("URL  is not valid.")


def _validate_special_char(name):
    if re.search("[^A-Za-z0-9 ]", name) == None:
        return True
    return False


# validate percentage value for float data type
def _validate_percentage(values):
    msg_store = {}
    for val in values:
        percent = float(values[val])
        if not (0 <= percent <= 100):
            msg_store[val] = val + ': ' + msg['percentage']

    return msg_store


def _validate_same(val1, val2, msg):
    if val1 == val2:
        msg_print = msg, "Can't be same"
        raise exceptions.ValidationError(msg_print)


def _validate_character(values, special=False):
    msg_store = {}

    for val in values:
        if values[val]:
            checkIllegal = values[val].strip()
            if special:
                if re.search("[^A-Za-z0-9 ]", checkIllegal) != None:
                    msg_store[val] = val + ': ' + msg['special_char']

            if not checkIllegal:
                msg_store[val] = val + ': ' + msg['space']

    return msg_store


def _validate_number(values):
    msg_store = {}
    for val in values:
        floatVal = float(values[val])
        if floatVal < 0.0:
            msg_store[val] = val + ': ' + msg['valid_number']
    return msg_store


def _check_illegal_char(self, values, msg):
    flag = True
    for value in values:
        checkIllegal = values[value].strip()
        if checkIllegal:
            if re.search("[^A-Za-z0-9 ]", checkIllegal) == None:
                flag = True
            else:
                error = 'Remove Special  Character from ' + msg
                raise exceptions.ValidationError(error)
                #                 raise osv.except_osv(('Validation Error'), (msg))
                flag = False
        else:
            flag = False
    if (flag):
        return flag
    else:
        error = msg
        raise exceptions.ValidationError(error)
        #         raise osv.except_osv(('Validation Error'), (msg))
        return flag


def _check_space(self, values, msg):
    flag = True
    msg_store = {}
    for value in values:
        checkIllegal = values[value].strip()
        if checkIllegal:
            flag = True
        else:
            flag = False
            msg_store[value] = value + ': ' + msg['space']
    return msg_store


def _check_special_char(self, values, msg):
    flag = True
    msg_store = {}
    return msg_store


# Check for special character

def _check_space2(values):
    msg_store = {}
    for value in values:
        if values[value]:
            checkIllegal = values[value].strip()
            if not checkIllegal:
                msg_store[value] = value + ': ' + msg['space']

    return msg_store


def _check_special_char2(values):
    msg_store = {}
    for val in values:
        if values[val]:
            checkIllegal = values[val]
            if re.search("[^A-Za-z0-9 ]", checkIllegal) != None:
                msg_store[val] = val + ': ' + msg['special_char']

    return msg_store


def check_special_char(vals, str):
    str = _check_special_char2(str)

    return str


# @api.multi
# def check_duplicate(self, vals, str):
#     if vals:
#         field_name = list(vals.items())[0][0]
#         field_value = list(vals.items())[0][1]
#         if field_value != field_value.strip():
#             raise exceptions.ValidationError("Remove space from start or end of " + str)
#         records = self.search_read([], [unidecode(field_name)])
#         records[:] = [d for d in records if d.get('id') != self.id]
#         for record in records:
#             if (field_value.lower().strip() == record[unidecode(field_name)].lower().strip()):
#                 raise exceptions.ValidationError("'" + str + "' already exist!")


def check_duplicate_size(self, envObj, conditionList, msg):
    records = envObj.search(conditionList, limit=1)
    if records.name == self.name:
        raise exceptions.ValidationError("'" + msg + "' already exist!")

# @api.multi
def check_duplicate_value(self, envObj, conditionList, msg):
    commonList = [('id', '!=', self.id)]
    conditionList = conditionList + commonList

    records = envObj.search(conditionList, limit=1)
    if records:
        raise exceptions.ValidationError("'" + msg + "' already exists!")


def check_report_date_limit(self, first_key, report_id, from_date,to_date):

    #raise exceptions.ValidationError("'" + msg + "' already exists!")

    filter_limit_obj = self.env['report.date.range.limit.settings'].search([('limit_key', '=', first_key)],
                                                                           limit=1)

    date_range = datetime.strptime(to_date, '%Y-%m-%d') - datetime.strptime(from_date, '%Y-%m-%d')
    date_diff = date_range.days
    day_count = date_diff + 1

    # ----------- check report date range
    if filter_limit_obj:
        if day_count > filter_limit_obj[0].value:
            raise UserError(_("Maximum %s days allow between 'From Date' and 'To date' for this report!" % (
                filter_limit_obj[0].value)))
        else:
            user = self.env.user

            if not user.has_group('base.group_system'):
                #rpt_id = self.env.ref('bay_pos.foot_nonfoot_rep_wiz_menu').id

                group_id_list = self.env.user.groups_id.ids

                day_limit_row = self.env['menu.report.day.limit.groups'].search(
                    [('groups_id', 'in', group_id_list), ('report_menu_id', '=', report_id)], order='days_limit desc',
                    limit=1)
                if day_limit_row:
                    days_limit = day_limit_row[0].days_limit
                    if day_count > days_limit:
                        raise UserError(_(
                            "Maximum %s days allow between 'From Date' and 'To date' for this report!" % (
                                days_limit)))



def check_special_character(self, codeStr):
    if codeStr != "":
        alphaNumStr = re.sub(r'[^a-zA-Z0-9 ]', r'', str(codeStr).strip())
        alphaNumStr = alphaNumStr.replace(" ", "")
        return alphaNumStr
    else:
        return ""


# message for ecommerce
# def _send_email_notification_msg(res_obj, mail_mail, recipient_email, subject, body):
#     #res_obj = self.env['ir.mail_server'].search([('name', '=', 'outgoing-server')], limit=1)
# 
#     # Email Notifications
#     #mail_mail = self.env['mail.mail']
#     mail_values = {
#         'email_from': res_obj.smtp_user,
#         'email_to': recipient_email,
#         'subject': subject,
#         'body_html': body,
#         'state': 'outgoing',
#         'message_type': 'email',
#     }
#     mail_id = mail_mail.create(mail_values)
#     if mail_id:
#         return "Success"
#     else:
#         return "Failed"


# (message send to email only)
def _send_email_notification_msg(self, recipient_email, subject, body):
    res_obj = self.env['ir.mail_server'].search([('name', '=', 'outgoing-server')], limit=1)

    # Email Notifications
    mail_mail = self.env['mail.mail']
    mail_values = {
        'email_from': res_obj.smtp_user,
        'email_to': recipient_email,
        'subject': subject,
        'body_html': body,
        'state': 'outgoing',
        'message_type': 'email',
    }
    mail_id = mail_mail.create(mail_values)
    if mail_id:
        return "Success"
    else:
        return "Failed"


# (message send from template to email only)
def _send_email_notification_template_msg(self, template, recipient_email):
    template.write(recipient_email)

    # Email Notifications from template
    self.env['mail.template'].browse(template.id).send_mail(self.id, raise_exception=False, force_send=True)

    return "Success"


# (message send to email, odoo inbox and odoo channel/group)
def _send_system_notification_msg(self, recipient_ids, recipient_channels, subject, body):
    post_vars = {'subject': subject, 'body': body, 'partner_ids': recipient_ids, 'channel_ids': recipient_channels,
                 'needaction_partner_ids': recipient_ids}

    thread_pool = self.env['mail.thread']
    thread_pool.message_post(
        message_type="notification",
        subtype="mt_comment",
        **post_vars)

    return "Success"


# (message send to group message in odoo channel/group )
def _send_message_notification(self, recipient_ids, recipient_channels, subject, body):
    message_data = {
        'message_type': 'notification',
        'subject': subject,
        'body': body,
        'partner_ids': recipient_ids,
        'channel_ids': recipient_channels,
        'needaction_partner_ids': recipient_ids,
        'subtype_id': ''
    }
    msg_obj = self.env['mail.message']
    msg_obj.create(message_data)

    return "Success"


def check_length_cleanhtml(self, record, limit, field_name):
    if record:
        limit = int(limit)
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', record)
        cln_space = cleantext.strip()
        if len(cln_space) > limit:
            raise exceptions.ValidationError(
                "'" + field_name + "' can be maximum " + str(limit) + " characters! ")
        else:
            return cln_space
    else:
        return ""


def _check_length_with_clean_htmltag(self, record, limit, field_name):
    limit = int(limit)
    if record:
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', record)
        if len(cleantext) > limit:
            raise exceptions.ValidationError(
                "'" + field_name + "' can be maximum " + str(limit) + " characters! ")
        else:
            return ""
    else:
        return ""


def _check_length(self, record, limit, field_name):
    limit = int(limit)
    if record:
        if len(record) > limit:
            raise exceptions.ValidationError(
                "'" + field_name + "' can be maximum " + str(limit) + " characters! ")
        else:
            return ""
    else:
        return ""


def _check_integer(self, param, length_param):
    param = str(param)
    length_param = int(length_param)
    if param:
        if len(param) > length_param:
            param = param[:length_param]  # str slicing
            param = int(param)
            return param
        else:
            return ""
    else:
        return ""


def _get_number_length_warning_msg(self, field_name, length):
    return {
        'warning': {
            'title': _('Warning'),
            'message': _("'%s' can be maximum %d digits!" % (field_name, length)),
        }}

# Raise all kinds of validation message
def validation_msg(validate_msg):
    msg_str = ""
    for msg in validate_msg:
        msg_str = msg_str + validate_msg[msg] + "\n"

    if msg_str:
        raise exceptions.ValidationError("Validation Error " + msg_str)

def generate_validation_msg(check_space, check_special_char):
    validation_msg = {}
    validation_msg.update(check_space)
    validation_msg.update(check_special_char)
    msg_store = ""
    for msg in validation_msg:
        msg_store = msg_store + validation_msg[msg] + "\n"

    if msg_store:
        raise exceptions.ValidationError("Validation Error " + msg_store)

def debug(param, all=False):
    #print('--------------------START-------------------------')
    if all:
        for val in param:
            print(val)
    else:
        print(param)
    # print('--------------------END-------------------------')


### All kinds of warning message ###

msg = {}
msg['special_char'] = 'Please remove special character.'
msg['image_uniq'] = 'Two image with the same name? Impossible!'
msg['region_uniq'] = 'Two region with the same name? Impossible!'
msg['unique'] = 'Two record with the same name'
msg['delete_style'] = 'Confirmed style cannot be deleted.'
msg['confirm_delete'] = 'Confirmed record cannot be deleted.'
msg['percentage'] = 'Please provide valid percentage value.'
msg['valid_number'] = 'Please provide valid number.'
msg['record_not_exist'] = 'No record exists! Please give a try with different value.'
msg['space'] = 'Only space is not allowed.'
msg['email'] = 'Please provide valid email.'
msg['size_attr'] = 'Please enter size attribute or check size selection value.'
msg['bwo_data'] = 'Please provide valid Work Order Data.'
msg['mc_data'] = 'Please provide valid Material Consumption Data.'
msg['percent_100'] = 'Yarn Percentage summation should not greater than 100'
