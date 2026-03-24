import pytz
from datetime import datetime

from odoo import api, models


class IndentMaterial(models.AbstractModel):
    _name = 'report.indent_process.indent_material_template'
    _description = 'Indent Material'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['indent.process'].browse(docids)

        return {
            'doc_ids': docids,
            'doc_model': 'indent.process',
            'data': data,
            'docs': docs,
            'company': self.env.user.company_id,
            'current_time': self.get_user_local_time(),
        }

    def get_user_local_time(self):
        # Get the user's timezone
        user_tz = self.env.user.tz or 'UTC'

        # Get the current UTC time
        utc_time = datetime.now(pytz.utc)

        # Convert the current time to the user's timezone
        user_time = utc_time.astimezone(pytz.timezone(user_tz))

        return user_time
