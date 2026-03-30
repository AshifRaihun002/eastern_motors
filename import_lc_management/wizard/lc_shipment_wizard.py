from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime


class LCShipmentWizard(models.TransientModel):
    _name = "lc.shipment.wizard"
    _description = "LC Shipment Wizard"

    lc_id = fields.Many2one(
        "letter.credit",
        string="Letter of Credit",
        required=True,
        readonly=True
    )

    # These should be related fields, not separate fields
    local_currency = fields.Float(
        related="lc_id.local_currency",
        string="Conversion Rate",
        readonly=True
    )
    partner_id = fields.Many2one(
        related="lc_id.partner_id",
     string="Vendor", tracking=True)

    currency_id = fields.Many2one(
        'res.currency',
        related="lc_id.currency_id",
        string='Account Currency',
        readonly=True
    )

    # Add purchase_process field for the computation
    purchase_process = fields.Selection(
        related="lc_id.purchase_process",
        string="Currency Type",
        readonly=True
    )

    shipment_line_ids = fields.One2many(
        "lc.shipment.wizard.line",
        "wizard_id",
        string="Shipment Products"
    )

    @api.model
    def default_get(self, fields_list):
        """Pre-fill wizard lines from LC lines."""
        res = super().default_get(fields_list)

        lc_id = self.env.context.get('active_id')
        if not lc_id:
            return res

        lc = self.env['letter.credit'].browse(lc_id)
        res['lc_id'] = lc.id

        # Build shipment wizard lines from LC lines
        # Changed from line_ids to lc_lines (assuming your field is named lc_lines)
        lines_vals = []
        for line in lc.lc_lines:  # This should be your One2many field name
            available_qty = line.product_qty - (line.shipped_qty or 0)
            if available_qty > 0:
                lines_vals.append((0, 0, {
                    'lc_line_id': line.id,
                    'quantity': 0.0,
                }))
        res['shipment_line_ids'] = lines_vals
        return res

    def action_create_shipment(self):
        self.ensure_one()

        valid_lines = self.shipment_line_ids.filtered(lambda l: l.quantity > 0)
        if not valid_lines:
            raise UserError(_("Please specify quantities for at least one product."))

        shipment_vals = {
            'lc_id': self.lc_id.id,
            'shipment_line_ids': [(0, 0, {
                'lc_line_id': line.lc_line_id.id,
                'quantity': line.quantity
            }) for line in valid_lines]
        }

        shipment = self.env['lc.shipment'].create(shipment_vals)

        for line in valid_lines:
            line.lc_line_id.shipped_qty += line.quantity

        return {
            'name': _('LC Shipment'),
            'view_mode': 'form',
            'res_model': 'lc.shipment',
            'res_id': shipment.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
            'views': [(False, 'form')],
        }


class LCShipmentWizardLine(models.TransientModel):
    _name = "lc.shipment.wizard.line"
    _description = "LC Shipment Wizard Line"

    wizard_id = fields.Many2one(
        "lc.shipment.wizard",
        string="Wizard"
    )

    lc_line_id = fields.Many2one(
        "letter.credit.line",
        string="LC Product Line",
        required=True
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="lc_line_id.product_id",
        readonly=True
    )

    default_code = fields.Char(
        string="Internal Reference",
        readonly=True,
        related="product_id.default_code"
    )

    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        related="lc_line_id.product_uom",
        readonly=True
    )

    product_qty = fields.Float(
        string="Total Quantity",
        related="lc_line_id.product_qty",
        readonly=True,
        digits="Product Unit of Measure"
    )

    shipped_qty = fields.Float(
        string="Already Shipped",
        related="lc_line_id.shipped_qty",
        readonly=True,
        digits="Product Unit of Measure"
    )

    available_qty = fields.Float(
        string="Available Quantity",
        compute='_compute_available_qty',
        readonly=True,
        digits='Product Unit of Measure'
    )

    quantity = fields.Float(
        string="Ship Quantity",
        required=True,
        default=0.0,
        digits='Product Unit of Measure'
    )

    price_unit = fields.Float(
        string='Unit Price',
        related="lc_line_id.price_unit",
        readonly=True,
        digits='Product Price'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        related="lc_line_id.company_currency_id",
        readonly=True
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        related="lc_line_id.price_subtotal",
        readonly=True,
        currency_field='company_currency_id'
    )

    # Add the missing related fields for the computation
    lc_purchase_process = fields.Selection(
        related="lc_line_id.lc_id.purchase_process",
        string="Purchase Process",
        readonly=True
    )

    lc_local_currency = fields.Float(
        related="lc_line_id.lc_id.local_currency",
        string="Conversion Rate",
        readonly=True
    )

    foreign_currency = fields.Float(
        string='Unit Rate(Local)',
        compute='_compute_foreign_currency',
        readonly=True,
        digits='Product Price'
    )

    foreign_price_subtotal = fields.Float(
        string='Subtotal(Local)',
        compute='_compute_foreign_currency',
        readonly=True,
        digits='Product Price'
    )

    @api.depends('lc_line_id.product_qty', 'lc_line_id.shipped_qty')
    def _compute_available_qty(self):
        for line in self:
            total_qty = line.lc_line_id.product_qty
            shipped_qty = line.lc_line_id.shipped_qty or 0
            line.available_qty = total_qty - shipped_qty

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError(_("Quantity cannot be negative."))
            if line.quantity > line.available_qty:
                raise ValidationError(
                    _("Quantity cannot exceed available quantity (%s) for product %s.") %
                    (line.available_qty, line.product_id.display_name)
                )

    @api.depends('price_unit', 'lc_purchase_process', 'lc_local_currency', 'product_qty')
    def _compute_foreign_currency(self):
        for line in self:
            if line.lc_purchase_process == 'foreign_purchase':
                line.foreign_currency = line.price_unit * line.lc_local_currency
                line.foreign_price_subtotal = line.foreign_currency * line.product_qty
            else:
                line.foreign_currency = line.price_unit * line.lc_local_currency
                line.foreign_price_subtotal = 0