from odoo import api, fields, models, _
from num2words import num2words


class Currency(models.Model):
    _inherit = "res.currency"

    @api.model
    def amount_to_word(self, number, currency='BDT'):
        # Convert the number to words using num2words
        amount_in_words = num2words(number, lang='en_IN').title()  # Use 'en_IN' for the Indian numbering system

        # Customize the output based on your requirements
        if currency == 'BDT':
            amount_in_words += ' Taka'
        elif currency == 'USD':
            amount_in_words += ' Dollars'
        # Add more currencies as needed

        return amount_in_words
