from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_customer = fields.Boolean(string='Is a Customer')
    is_vendor = fields.Boolean(string='Is a Vendor')
    contact_address_complete = fields.Char(compute='_compute_complete_address', store=True)
    company_id = fields.Many2one('res.company', 'Company', index=True, default=lambda self: self.env.company)
    nid = fields.Char(string='NID')
    tin = fields.Char(string='TIN')

    @api.depends('street', 'zip', 'city', 'country_id')
    def _compute_complete_address(self):
        for record in self:
            record.contact_address_complete = ''
            if record.street:
                record.contact_address_complete += record.street + ', '
            if record.zip:
                record.contact_address_complete += record.zip + ' '
            if record.city:
                record.contact_address_complete += record.city + ', '
            if record.state_id:
                record.contact_address_complete += record.state_id.name + ', '
            if record.country_id:
                record.contact_address_complete += record.country_id.name
            record.contact_address_complete = record.contact_address_complete.strip().strip(',')