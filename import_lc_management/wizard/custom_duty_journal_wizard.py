from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime


class LcCustomDutyWizard(models.TransientModel):
    _name = 'lc.custom.duty.wizard'
    _description = 'LC Custom Duty Journal Wizard'

    lc_id = fields.Many2one('letter.credit', string="Letter of Credit", required=True, readonly=True)
    journal_id = fields.Many2one('account.journal', string="Journal", required=True)
    wizard_line_ids = fields.One2many('lc.custom.duty.wizard.line', 'wizard_id', string="Custom Duty Lines")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lc_id = self.env.context.get('default_lc_id')
        if lc_id:
            lc = self.env['letter.credit'].browse(lc_id)
            lines = []
            for line in lc.lc_cost_line_ids.filtered(
                    # this line for filter the code as if the line is already paid or not that's why we make is as it is
                    # lambda l: l.amount > 0 and l.landed_cost_type == 'custom_duty' and not l.is_payed):
                    lambda l: l.amount > 0 and l.landed_cost_type == 'custom_duty'):
                lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'landed_cost_type': line.landed_cost_type,
                    'account_id': line.account_id.id,
                    'amount': line.amount,
                    'currency_id': line.currency_id.id,
                    'original_cost_line_id': line.id,  # Add reference to source line
                }))
            res['wizard_line_ids'] = lines
        return res

    def action_confirm(self):
        self.ensure_one()
        lc = self.lc_id

        if not self.wizard_line_ids:
            raise UserError("No custom duty lines available.")

        move_vals = {
            'journal_id': self.journal_id.id,
            'ref': f'LC: {lc.name}',
            'date': fields.Date.context_today(self),
            'line_ids': [],
        }

        total_debit = 0.0

        for line in self.wizard_line_ids:
            if not line.account_id:
                raise UserError(f"Missing account on wizard line: {line.product_id.display_name}")
            move_vals['line_ids'].append((0, 0, {
                'name': line.product_id.display_name or line.landed_cost_type,
                'account_id': line.account_id.id,
                'debit': line.amount,
                'credit': 0.0,
                'currency_id': line.currency_id.id if line.currency_id else False,
            }))
            total_debit += line.amount

        credit_account = self.journal_id.default_account_id
        if not credit_account:
            raise UserError("The selected journal does not have a default account.")

        move_vals['line_ids'].append((0, 0, {
            'name': 'Landed Cost Credit',
            'account_id': credit_account.id,
            'debit': 0.0,
            'credit': total_debit,
            'currency_id': self.wizard_line_ids[0].currency_id.id if self.wizard_line_ids else False,

        }))

        move = self.env['account.move'].create(move_vals)
        move.action_post()
        # this code is for payment is_payed infor so on demand if needed we need to open it

        # for wizard_line in self.wizard_line_ids:
        #     if wizard_line.original_cost_line_id.is_payed is False:
        #         print("asdsadlksald",wizard_line.original_cost_line_id)
        #         wizard_line.original_cost_line_id.write({'is_payed': True})

        lc.custom_duty_journals = [(4, move.id)]
        lc.message_post(
            body=f"Custom Duty Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created.")
        lc.state = 'lc_document'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }


class LcCustomDutyWizardLine(models.TransientModel):
    _name = 'lc.custom.duty.wizard.line'
    _description = 'Custom Duty Wizard Line'

    wizard_id = fields.Many2one('lc.custom.duty.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product")
    landed_cost_type = fields.Selection([
        ('custom_duty', 'Custom Duty'),
        ('freight', 'Freight'),
        ('insurance', 'Insurance'),
        ('others', 'Others')
    ], string="Landed Cost Type")
    account_id = fields.Many2one('account.account', string="Account")
    amount = fields.Float(string="Amount")
    currency_id = fields.Many2one('res.currency', string="Currency")
    original_cost_line_id = fields.Many2one('letter.credit.cost.line', string="Source LC Cost Line")
