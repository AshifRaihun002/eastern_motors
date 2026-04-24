from odoo import models, fields, api, exceptions, modules
import math


def _set_default_currency(name):
    # res = self.env['res.currency'].search([('name', '=like', name)])
    # return res and res[0] or False
    r = modules.registry.RegistryManager.get('demo9-test-2')
    cr = r.cursor()
    env = api.Environment(cr, 1, {})
    res = env['res.currency'].search([('name', '=like', name)])
    return res and res[0] or False


def convert_number(number):
    my_number = number
    if (number < 0) | (number > 999999999):
        raise exceptions.ValidationError("Number is out of range")
    Kt = math.floor(number / 10000000)  # Koti */
    number -= Kt * 10000000
    Gn = math.floor(number / 100000)  # /* lakh  */ 
    number -= Gn * 100000
    kn = math.floor(number / 1000)  # /* Thousands (kilo) */ 
    number -= kn * 1000
    Hn = math.floor(number / 100)  # /* Hundreds (hecto) */ 
    number -= Hn * 100
    Dn = int(math.floor(number / 10))  # /* Tens (deca) */ 
    n = int(number % 10)  # /* Ones */ 
    res = ""
    if (Kt):
        res += str(convert_number(Kt)) + " Koti "
    if (Gn):
        res += str(convert_number(Gn)) + " Lakh "
    if (kn):
        if res:
            res += " " + str(convert_number(kn)) + " Thousand "
        else:
            res += " " + str(convert_number(kn)) + " Thousand "

    if (Hn):
        if res:
            res += " " + str(convert_number(Hn)) + " Hundred "
        else:
            res += " " + str(convert_number(Hn)) + " Hundred "

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six",
            "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
            "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eightteen",
            "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty",
            "Seventy", "Eighty", "Ninety"]
    xn = (Dn | n)
    if xn:
        if res:
            res += " and "
        if (Dn < 2):
            res += ones[Dn * 10 + n]
        else:
            res += tens[Dn]
            if (n):
                res += "-" + ones[n]
    if not res:
        res = "zero"
    return res
