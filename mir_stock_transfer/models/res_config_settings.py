from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    inter_company_adjustment_location_id = fields.Many2one(
        comodel_name='stock.location',
        string="Inter Company Adjustment Location",
        domain="[('usage', '=', 'inventory')]",
        check_company=True
    )

    inter_company_stock_valuation_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Inter Company Stock Valuation Journal",
        check_company=True
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    inter_company_adjustment_location_id = fields.Many2one(
        comodel_name='stock.location',
        related="company_id.inter_company_adjustment_location_id",
        string="Inter Company Adjustment Location",
        readonly=False,
        check_company=True
    )

    inter_company_stock_valuation_journal_id = fields.Many2one(
        comodel_name='account.journal',
        related="company_id.inter_company_stock_valuation_journal_id",
        string="Inter Company Stock Valuation Journal",
        readonly=False,
        check_company=True
    )
