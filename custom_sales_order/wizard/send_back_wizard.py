from odoo import models, fields, _
from odoo.exceptions import ValidationError


class SentBackWizardSale(models.TransientModel):
    _name = 'sent.back.wizard.so'
    _description = 'Sent Back Wizard Sales'

    note = fields.Text(string='Note')

    def send_back_so(self):
        sale_id = self.env.context.get('active_id')
        sale = self.env['sale.order'].browse(sale_id)

        if not sale_id:
            raise ValidationError(_("No sales order associated with this record."))

        if not sale.stage_id:
            raise ValidationError(_("No current approval stage found."))

        current_stage_sequence = sale.stage_id.sequence

        # Find previous stage in same approval config
        previous_stage = self.env['approval.line'].sudo().search(
            [
                ('config_id', '=', sale.stage_id.config_id.id),
                ('sequence', '<', current_stage_sequence),
            ],
            order='sequence desc',
            limit=1
        )

        if previous_stage:
            # Log send back action
            self.env['so.approval.history'].create({
                'action_type': 'sent_back',
                'sale_id': sale.id,
                'stage_id': sale.stage_id.id,
                'to_stage_id': previous_stage.id,
                'user_id': self.env.user.id,
                'date': fields.Datetime.now(),
                'note': self.note,
            })

            # Move back to previous stage
            sale.write({
                'stage_id': previous_stage.id,
                'state': 'approval_pending',
            })
        else:
            raise ValidationError(_("No previous stage found to send back."))