from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):

        no_partner_vals_list = [
            vals
            for vals in vals_list
            if vals.get('name') and not vals.get('partner_id')
        ]
        if no_partner_vals_list:
            partners = self.env['res.partner'].create([
                {
                    'name': vals['name'],
                    'is_company': True,
                    'image_1920': vals.get('logo'),
                    'email': vals.get('email'),
                    'phone': vals.get('phone'),
                    'website': vals.get('website'),
                    'vat': vals.get('vat'),
                    'country_id': vals.get('country_id'),
                    'company_id': False
                }
                for vals in no_partner_vals_list
            ])
            # compute stored fields, for example address dependent fields
            partners.flush_model()
            for vals, partner in zip(no_partner_vals_list, partners):
                vals['partner_id'] = partner.id

        self.clear_caches()
        companies = super().create(vals_list)

        return companies
