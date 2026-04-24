from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime




class ShipmentCustomDutyWizard(models.TransientModel):
    _name = 'shipment.custom.duty.wizard'
    _description = 'Shipment Custom Duty Journal Wizard'

    shipment_id = fields.Many2one(
        'lc.shipment',
        string="LC Shipment",
        required=True,
        readonly=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        string="Journal",
        required=True
    )
    wizard_line_ids = fields.One2many(
        'shipment.custom.duty.wizard.line',
        'wizard_id',
        string="Custom Duty Lines"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        shipment_id = self.env.context.get('default_shipment_id')
        if shipment_id:
            shipment = self.env['lc.shipment'].browse(shipment_id)
            lines = []
            for line in shipment.cost_line_ids.filtered(
                    lambda l: l.amount > 0 and l.landed_cost_type == 'custom_duty' and not l.is_payed
            ):
                lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'landed_cost_type': line.landed_cost_type,
                    'account_id': line.account_id.id,
                    'amount': line.amount,
                    'currency_id': line.currency_id.id,
                    'original_cost_line_id': line.id,  # Reference to shipment cost line
                }))
            res['wizard_line_ids'] = lines
        return res

    def action_confirm(self):
        self.ensure_one()
        shipment = self.shipment_id

        if not self.wizard_line_ids:
            raise UserError("No custom duty lines available.")

        move_vals = {
            'journal_id': self.journal_id.id,
            'ref': f'Shipment: {shipment.name}',
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
            'name': 'Shipment Landed Cost Credit',
            'account_id': credit_account.id,
            'debit': 0.0,
            'credit': total_debit,
            'currency_id': self.wizard_line_ids[0].currency_id.id if self.wizard_line_ids else False,
        }))

        move = self.env['account.move'].create(move_vals)
        move.action_post()
        shipment.custom_duty_journals = [(4, move.id)]
        shipment.state = 'received'

        # Update the payment status on the original cost lines
        for wizard_line in self.wizard_line_ids:
            if wizard_line.original_cost_line_id:
                paid_amount = wizard_line.original_cost_line_id.payment_amount + wizard_line.amount
                remaining_amount = wizard_line.original_cost_line_id.amount - paid_amount
                is_payed = remaining_amount <= 0

                wizard_line.original_cost_line_id.write({
                    'payment_amount': paid_amount,
                    'remaining_amount': remaining_amount,
                    'is_payed': is_payed,
                    'lc_journal_id': self.journal_id.id
                })

        # Add the journal entry to the shipment
        if not hasattr(shipment, 'custom_duty_journals'):
            # If the field doesn't exist on shipment, you might want to add it
            # For now, we'll just post a message
            pass

        shipment.message_post(
            body=f"Custom Duty Journal Entry <a href='/web#id={move.id}&model=account.move'>{move.name}</a> created."
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ShipmentCustomDutyWizardLine(models.TransientModel):
    _name = 'shipment.custom.duty.wizard.line'
    _description = 'Shipment Custom Duty Wizard Line'

    wizard_id = fields.Many2one(
        'shipment.custom.duty.wizard',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string="Product"
    )
    landed_cost_type = fields.Selection([
        ('custom_duty', 'Custom Duty'),
        ('freight', 'Freight'),
        ('insurance', 'Insurance'),
        ('others', 'Others')
    ], string="Landed Cost Type")
    account_id = fields.Many2one(
        'account.account',
        string="Account"
    )
    amount = fields.Float(string="Amount")
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency"
    )
    original_cost_line_id = fields.Many2one(
        'shipment.cost.line',
        string="Source Shipment Cost Line"
    )