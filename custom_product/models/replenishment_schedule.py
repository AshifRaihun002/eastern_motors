from urllib import parse
from datetime import datetime, timedelta
from markupsafe import Markup
import logging
import base64
from odoo.http import request
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    @api.model
    def check_reordering_rules_and_notify(self):
        """Generate replenishment PDF report (with wizard filters) and send email."""

        # Step 1: Build default wizard-like filters
        form_data = {
            'date_from': (date.today() - timedelta(days=10)).strftime('%Y-%m-%d'),
            'date_to': date.today().strftime('%Y-%m-%d'),
            'location_id': False,  # all locations
            'include_all_locations': True,
            'show_only_critical': True,
        }

        # Step 2: Compute report data using the wizard’s method
        wizard = self.env['replenishment.report.wizard'].create(form_data)
        report_data = wizard.get_report_data(form_data)

        if not report_data:
            return  # nothing to notify

        # Step 3: Render report with form + report_data
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            'brac_procurement.action_report_replenishment_summary',
            res_ids=[],
            data={
                'form': {**form_data, 'report_data': report_data},
                'current_time': datetime.now(),
            }
        )

        # Step 4: Encode PDF & create attachment
        pdf_base64 = base64.b64encode(pdf_content)
        attachment = self.env['ir.attachment'].create({
            'name': f"Stock_Replenishment_{date.today().strftime('%Y%m%d')}.pdf",
            'type': 'binary',
            'datas': pdf_base64,
            'mimetype': 'application/pdf',
            'res_model': 'stock.warehouse.orderpoint',
            'res_id': 0,
        })

        # Step 5: Send email with attachment
        template = self.env.ref('brac_procurement.email_template_reordering_notify')
        template.sudo().send_mail(
            self.env.user.id,
            force_send=True,
            email_values={'attachment_ids': [(6, 0, [attachment.id])]}
        )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    needs_replenishment = fields.Boolean(string='Needs Replenishment', compute='_compute_needs_replenishment', store=False)



    critical_locations = fields.Integer(
        string='Critical Locations', compute='_compute_critical_locations', help='Number of locations where stock is below minimum'
    )

    # is_gift = fields.Boolean(string='Is Gift Product', related='product_tmpl_id.is_gift', store=True)

    @api.depends('qty_available', 'reordering_min_qty')
    def _compute_needs_replenishment(self):
        for product in self:
            min_qty = product.reordering_min_qty or 0.0
            product.needs_replenishment = product.qty_available < min_qty

    @api.depends(
        'stock_quant_ids.quantity',
        'stock_quant_ids.location_id',
        'stock_quant_ids.location_id.usage',
        'stock_quant_ids.needs_replenishment',
        # 'stock_quant_ids.replenish_location',
    )
    def _compute_critical_locations(self):
        for product in self:
            quants = product.stock_quant_ids.filtered(
                lambda q: q.location_id
                          and q.location_id.usage == 'internal'
                          and q.location_id.replenish_location == True

            )
            product.critical_locations = len(set(quants.mapped('location_id').ids))

    def action_view_critical_locations(self):
        """Action to view locations needing replenishment for this product"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Critical Locations - {self.display_name}',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [
                ('product_id', '=', self.id),
                ('needs_replenishment', '=', True),
                ('location_id.usage', '=', 'internal')
            ],
            'context': {
                'default_product_id': self.id,
                'search_default_needs_replenishment': 1
            }
        }




class StockQuant(models.Model):
    _inherit = 'stock.quant'

    needs_replenishment = fields.Boolean(
        string='Needs Replenishment',
        compute='_compute_needs_replenishment',
        store=True
    )

    replenishment_status = fields.Float(
        string='Replenishment Status',
        compute='_compute_replenishment_status',
        help='Percentage of current stock compared to minimum quantity'
    )

    @api.depends('quantity', 'product_id.reordering_min_qty')
    def _compute_needs_replenishment(self):
        for quant in self:
            product = quant.product_id
            if product and product.reordering_min_qty > 0:
                quant.needs_replenishment = quant.quantity < product.reordering_min_qty
            else:
                quant.needs_replenishment = False

    @api.depends('quantity', 'product_id.reordering_min_qty')
    def _compute_replenishment_status(self):
        for quant in self:
            product = quant.product_id
            if product and product.reordering_min_qty > 0 and product.reordering_min_qty > 0:
                quant.replenishment_status = min(100, (quant.quantity / product.reordering_min_qty) * 100)
            else:
                quant.replenishment_status = 100
