from odoo import fields, models

class InspectionPictureOne(models.Model):
    _name = 'inspection.picture.one'
    _description = 'Inspection Picture Type One'

    warranty_claim_id = fields.Many2one("warranty.claim", string='Warranty Claim', ondelete='cascade')
    name = fields.Char(string='Picture Name')
    image = fields.Binary(string='Image', required=True)

class InspectionPictureTwo(models.Model):
    _name = 'inspection.picture.two'
    _description = 'Inspection Picture Type Two'

    warranty_claim_id = fields.Many2one("warranty.claim", string='Warranty Claim', ondelete='cascade')
    name = fields.Char(string='Picture Name')
    image = fields.Binary(string='Image', required=True)

class InspectionPictureThree(models.Model):
    _name = 'inspection.picture.three'
    _description = 'Inspection Picture Type Three'

    warranty_claim_id = fields.Many2one("warranty.claim", string='Warranty Claim', ondelete='cascade')
    name = fields.Char(string='Picture Name')
    image = fields.Binary(string='Image', required=True)

class InspectionPictureFour(models.Model):
    _name = 'inspection.picture.four'
    _description = 'Inspection Picture Type Four'

    warranty_claim_id = fields.Many2one("warranty.claim", string='Warranty Claim', ondelete='cascade')
    name = fields.Char(string='Picture Name')
    image = fields.Binary(string='Image', required=True)

class InspectionPictureFive(models.Model):
    _name = 'inspection.picture.five'
    _description = 'Inspection Picture Type Five'

    warranty_claim_id = fields.Many2one("warranty.claim", string='Warranty Claim', ondelete='cascade')
    name = fields.Char(string='Picture Name')
    image = fields.Binary(string='Image', required=True)