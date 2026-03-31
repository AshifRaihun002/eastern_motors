from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    discount_type = fields.Selection([
        ('no_discount', 'No Discount'),
        ('fixed', 'Fixed Amount'),
        ('percentage', 'Percentage'),
        ('global', 'Global Discount')
    ], string='Discount Type', default='no_discount')

    discount_amount = fields.Float(string='Discount Amount')
    discount_percentage = fields.Float(string='Discount Percentage (%)')
    amount_before_discount = fields.Monetary(string='Amount Before Discount',
                                             compute='_compute_amount_before_discount', store=True)

    # is_direct_purchase_limit_exceeded = fields.Boolean(
    #     string='Limit Exceeded',
    #     compute='_compute_direct_purchase_limit',
    #     store=False
    # )
    # direct_purchase_limit_display = fields.Char(
    #     string='Direct Purchase Limit',
    #     compute='_compute_direct_purchase_limit_display'
    # )

    # is_direct_purchase_line_limit_exceeded = fields.Boolean(
    #     string='Line Limit Exceeded',
    #     compute='_compute_direct_purchase_limit',
    #     store=False
    # )

    # exceeded_line_ids = fields.Many2many(
    #     'purchase.order.line',
    #     string="Lines Exceeding Limit",
    #     compute='_compute_direct_purchase_limit',
    #     store=False
    # )

    # def _compute_direct_purchase_limit_display(self):
    #     """Compute display value for direct purchase limits"""
    #     for order in self:
    #         if order.procurement_method == 'direct_purchase':
    #             # Get config using the new method
    #             config = self.env['direct.purchase.config'].get_direct_purchase_config(
    #                 company_id=order.company_id.id,
    #                 concern_dept_id=order.concern_dept.id if order.concern_dept else False
    #             )
    #
    #             if config:
    #                 display_parts = []
    #                 if config.direct_purchase_limit:
    #                     display_parts.append(
    #                         f"Total Limit: {order.currency_id.symbol} {config.direct_purchase_limit:.2f}"
    #                     )
    #                 if config.direct_purchase_line_limit:
    #                     display_parts.append(
    #                         f"Line Limit: {order.currency_id.symbol} {config.direct_purchase_line_limit:.2f}"
    #                     )
    #
    #                 order.direct_purchase_limit_display = " | ".join(display_parts)
    #             else:
    #                 order.direct_purchase_limit_display = "No configuration found"
    #         else:
    #             order.direct_purchase_limit_display = ""

    # @api.constrains('amount_total', 'order_line', 'procurement_method')
    # def _check_direct_purchase_limits(self):
    #     for order in self:
    #         company = order.company_id
    #
    #         # Only run check if procurement method = 'direct_purchase'
    #         if order.procurement_method != 'direct_purchase':
    #             continue
    #
    #         # Check only if the line-limit feature is active and limit value is set
    #         if (
    #                 company.is_direct_purchase_line_limit_active
    #                 and company.direct_purchase_line_limit
    #         ):
    #             for line in order.order_line:
    #                 if line.price_subtotal > company.direct_purchase_line_limit:
    #                     raise ValidationError(_(
    #                         "Line '%s' exceeds the Direct Purchase Line Limit (%.2f)."
    #                     ) % (line.name, company.direct_purchase_line_limit))

    def _get_discount_product(self):
        """Fetch discount product (service type)."""
        discount_product = self.env['product.product'].search([('default_code', '=', 'DISCOUNT')], limit=1)
        if not discount_product:
            raise UserError(_("Please create a Discount product with Internal Reference 'DISCOUNT' (service type)."))
        return discount_product

    @api.depends('order_line.price_subtotal', 'order_line.is_global_discount_line')
    def _compute_amount_before_discount(self):
        """Compute total amount before any discount (exclude global discount lines)"""
        for order in self:
            order.amount_before_discount = sum(
                line.product_qty * line.price_unit
                for line in order.order_line
                if not line.is_global_discount_line
            )

    @api.depends('order_line.price_total', 'discount_type', 'discount_amount', 'discount_percentage')
    def _amount_all(self):
        """Compute total amounts, excluding discount creation logic."""
        super(PurchaseOrder, self)._amount_all()

    def _calculate_and_distribute_discount(self):
        """Calculate and apply discounts (fixed, percentage, global) safely."""
        for order in self:
            # Find any existing discount line
            discount_line = order.order_line.filtered(lambda l: l.is_global_discount_line)

            if order.discount_type == 'fixed' and order.discount_amount:
                total_before_discount = order.amount_before_discount
                total_discount = min(order.discount_amount, total_before_discount)
                if total_before_discount > 0:
                    for line in order.order_line:
                        if not line.is_global_discount_line:
                            line_subtotal = line.product_qty * line.price_unit
                            if line_subtotal > 0:
                                proportion = line_subtotal / total_before_discount
                                discount_value = total_discount * proportion
                                line.discount = (discount_value / line_subtotal) * 100
                            else:
                                line.discount = 0.0
                else:
                    for line in order.order_line:
                        line.discount = 0.0

                # Remove global discount line if exists
                if discount_line:
                    discount_line.unlink()

            elif order.discount_type == 'percentage' and order.discount_percentage:
                discount_rate = min(order.discount_percentage, 100)
                for line in order.order_line:
                    if not line.is_global_discount_line:
                        line.discount = discount_rate

                # Remove global discount line if exists
                if discount_line:
                    discount_line.unlink()

            elif order.discount_type == 'global' and order.discount_amount:
                discount_product = order._get_discount_product()
                discount_value = -abs(order.discount_amount)

                if discount_line:
                    # ✅ Update existing global discount line
                    discount_line.write({'price_unit': discount_value})
                else:
                    # ✅ Create new one if not already present
                    if order.id:
                        order.env['purchase.order.line'].create({
                            'order_id': order.id,
                            'product_id': discount_product.id,
                            'name': _('Global Discount'),
                            'product_qty': 1,
                            'product_uom': discount_product.uom_id.id,
                            'price_unit': discount_value,
                            'is_global_discount_line': True,
                        })
                    else:
                        new_line = order.order_line.new({
                            'product_id': discount_product.id,
                            'name': _('Global Discount'),
                            'product_qty': 1,
                            'product_uom': discount_product.uom_id.id,
                            'price_unit': discount_value,
                            'is_global_discount_line': True,
                        })
                        order.order_line += new_line

            else:
                # No discount type selected → reset everything
                for line in order.order_line:
                    if not line.is_global_discount_line:
                        line.discount = 0.0
                if discount_line:
                    discount_line.unlink()

    def action_apply_discount(self):
        """Manual method to apply discount"""
        self._calculate_and_distribute_discount()

    # @api.depends('amount_total', 'order_line.price_subtotal', 'procurement_method', 'concern_dept')
    # def _compute_direct_purchase_limit(self):
    #     """Compute if the direct purchase limit is exceeded based on department configuration."""
    #     for order in self:
    #         exceeded = False
    #         line_exceeded = False
    #         exceeded_lines = self.env['purchase.order.line']
    #
    #         if order.procurement_method == 'direct_purchase':
    #             # Get config using the helper method
    #             config = self.env['direct.purchase.config'].get_direct_purchase_config(
    #                 company_id=order.company_id.id,
    #                 concern_dept_id=order.concern_dept.id if order.concern_dept else False
    #             )
    #
    #             if config:
    #                 # Check total limit
    #                 if config.direct_purchase_limit:
    #                     exceeded = order.amount_total > config.direct_purchase_limit
    #
    #                 # Check line limit
    #                 if config.direct_purchase_line_limit:
    #                     for line in order.order_line:
    #                         if line.price_subtotal > config.direct_purchase_line_limit:
    #                             line_exceeded = True
    #                             exceeded_lines += line
    #
    #         order.is_direct_purchase_limit_exceeded = exceeded
    #         order.is_direct_purchase_line_limit_exceeded = line_exceeded
            # order.exceeded_line_ids = exceeded_lines

    # @api.constrains('amount_total', 'order_line.price_subtotal', 'procurement_method', 'concern_dept')
    # def _check_direct_purchase_limits(self):
    #     for order in self:
    #         if order.procurement_method != 'direct_purchase':
    #             continue
    #         config = self.env['direct.purchase.config'].get_direct_purchase_config(
    #             company_id=order.company_id.id,
    #             concern_dept_id=order.concern_dept.id if order.concern_dept else False
    #         )
    #
    #         if not config:
    #             # No config found, skip validation
    #             continue
    #
    #         # Only validate if department matches (or config is global)
    #         if not config.concern_dept or config.concern_dept.id == order.concern_dept.id:
    #             error_messages = []
    #
    #             # 1. Check total amount limit
    #             if config.direct_purchase_limit and order.amount_total > config.direct_purchase_limit:
    #                 error_messages.append(_(
    #                     "Total amount (%(currency)s %(amount).2f) exceeds the configured total limit "
    #                     "(%(currency)s %(limit).2f)."
    #                 ) % {
    #                                           'currency': order.currency_id.symbol,
    #                                           'amount': order.amount_total,
    #                                           'limit': config.direct_purchase_limit,
    #                                       })
    #
    #             # 2. Check line amount limits
    #             if config.direct_purchase_line_limit:
    #                 exceeded_lines = []
    #                 for line in order.order_line:
    #                     if line.price_subtotal > config.direct_purchase_line_limit:
    #                         exceeded_lines.append(line)
    #
    #                 if exceeded_lines:
    #                     line_details = []
    #                     for line in exceeded_lines:
    #                         line_details.append(
    #                             f"• {line.product_id.display_name or line.name}: "
    #                             f"{order.currency_id.symbol} {line.price_subtotal:.2f} "
    #                             f"(Limit: {order.currency_id.symbol} {config.direct_purchase_line_limit:.2f})"
    #                         )
    #
    #                     error_messages.append(_(
    #                         "Line amount(s) exceed the configured line limit "
    #                         "(%(currency)s %(limit).2f).\n\n"
    #                         "Lines exceeding limit:\n%(lines)s"
    #                     ) % {
    #                                               'currency': order.currency_id.symbol,
    #                                               'limit': config.direct_purchase_line_limit,
    #                                               'lines': '\n'.join(line_details)
    #                                           })
    #
    #             # Raise combined error if any limits are exceeded
    #             if error_messages:
    #                 full_message = _("Direct Purchase validation failed for department '%(dept)s':\n\n%(errors)s\n\n"
    #                                  "Please reduce the amount(s) or change the procurement method.") % {
    #                                    'dept': order.concern_dept.name or _('N/A'),
    #                                    'errors': '\n\n'.join(error_messages)
    #                                }
    #                 raise ValidationError(full_message)

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_global_discount_line = fields.Boolean(string="Is Global Discount Line", default=False)
    discount = fields.Float(
        digits=(12, 4),
        readonly=False
    )
