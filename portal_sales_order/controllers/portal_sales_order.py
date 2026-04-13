import json

from odoo import http, _, fields
from odoo.http import request


class PortalSaleOrder(http.Controller):

    def _get_partner_pricelist(self, partner):
        return partner.property_product_pricelist or request.env['product.pricelist'].sudo().search([
            '|', ('company_id', '=', False), ('company_id', '=', request.env.company.id)
        ], limit=1)

    def _get_available_partners(self):
        user = request.env.user
        return request.env['res.partner'].sudo().search([
            ('customer_rank', '>', 0),
            ('active', '=', True),
            ('user_id', '=', user.id),
        ], order='name asc')

    def _get_available_products(self):
        return request.env['product.product'].sudo().search([
            ('sale_ok', '=', True),
            ('active', '=', True),
        ], order='name asc')

    def _get_selected_partner(self, partner_id):
        if not partner_id:
            return request.env['res.partner']
        try:
            partner_id = int(partner_id)
        except (TypeError, ValueError):
            return request.env['res.partner']
        return request.env['res.partner'].sudo().browse(partner_id).exists()

    def _get_product_price(self, partner, product, quantity=1.0):
        pricelist = self._get_partner_pricelist(partner)
        if not pricelist:
            return product.lst_price
        return pricelist._get_product_price(
            product,
            quantity=quantity,
            currency=pricelist.currency_id,
            uom=product.uom_id,
            date=fields.Datetime.now(),
        )

    def _prepare_product_cards(self, partner, products, entered_quantities=None):
        entered_quantities = entered_quantities or {}
        cards = []
        for product in products:
            cards.append({
                'product': product,
                'qty': entered_quantities.get(str(product.id), ''),
                'price': self._get_product_price(partner, product, quantity=1.0) if partner else product.lst_price,
                'uom_name': product.uom_id.name,
                'default_code': product.default_code,
            })
        return cards

    def _prepare_form_values(self, partner=None, error=None, note='', entered_quantities=None, payment_type='cash'):
        partners = self._get_available_partners()
        products = self._get_available_products()
        selected_partner = partner or partners[:1]
        return {
            'partners': partners,
            'selected_partner': selected_partner,
            'product_cards': self._prepare_product_cards(selected_partner, products, entered_quantities=entered_quantities),
            'payment_type_options': [
                ('cash', 'Cash'),
                ('bank', 'Bank'),
                ('credit', 'Credit'),
            ],
            'selected_payment_type': payment_type or 'cash',
            'error': error,
            'note': note or '',
            'entered_quantities': entered_quantities or {},
        }

    @http.route(['/sales/apply'], type='http', auth='user', website=True)
    def apply_sales_order(self, partner_id=None, **kwargs):
        partner = self._get_selected_partner(partner_id) or self._get_available_partners()[:1]
        values = self._prepare_form_values(partner=partner)
        return request.render('portal_sales_order.portal_apply_sales_order', values)

    @http.route(['/sales/product_price'], type='json', auth='user', website=True)
    def get_sales_product_price(self, partner_id=None, product_id=None, quantity=1.0, **kwargs):
        partner = self._get_selected_partner(partner_id)
        if not partner:
            return {'price': 0.0, 'currency_symbol': ''}

        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            return {'price': 0.0, 'currency_symbol': ''}

        product = request.env['product.product'].sudo().browse(product_id).exists()
        if not product:
            return {'price': 0.0, 'currency_symbol': ''}

        try:
            quantity = float(quantity or 1.0)
        except (TypeError, ValueError):
            quantity = 1.0
        quantity = quantity if quantity > 0 else 1.0

        pricelist = self._get_partner_pricelist(partner)
        return {
            'price': self._get_product_price(partner, product, quantity=quantity),
            'currency_symbol': pricelist.currency_id.symbol if pricelist and pricelist.currency_id else '',
        }

    @http.route(['/sales/submit'], type='http', auth='user', website=True, methods=['POST'])
    def submit_sales_order(self, **kwargs):
        partner = self._get_selected_partner(kwargs.get('partner_id'))
        payment_type = kwargs.get('payment_type') or 'cash'
        note = kwargs.get('note') or ''

        if not partner:
            return request.redirect('/sales/apply')

        products = self._get_available_products()
        entered_quantities = {}
        order_lines = []
        product_map = {product.id: product for product in products}

        raw_order_lines_json = kwargs.get('order_lines_json') or '[]'
        try:
            submitted_lines = json.loads(raw_order_lines_json)
        except json.JSONDecodeError:
            submitted_lines = []

        if submitted_lines:
            for line in submitted_lines:
                try:
                    product_id = int(line.get('product_id'))
                    qty = float(line.get('qty') or 0.0)
                except (TypeError, ValueError):
                    continue

                if qty <= 0:
                    continue

                product = product_map.get(product_id)
                if not product:
                    continue

                entered_quantities[str(product.id)] = str(qty)
                price_unit = self._get_product_price(partner, product, quantity=qty)
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'name': product.get_product_multiline_description_sale() or product.display_name,
                    'price_unit': price_unit,
                }))
        else:
            for product in products:
                qty_key = f'qty_{product.id}'
                raw_qty = kwargs.get(qty_key, '').strip()
                if raw_qty:
                    entered_quantities[str(product.id)] = raw_qty
                try:
                    qty = float(raw_qty or 0.0)
                except (TypeError, ValueError):
                    qty = 0.0

                if qty <= 0:
                    continue

                price_unit = self._get_product_price(partner, product, quantity=qty)
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': qty,
                    'name': product.get_product_multiline_description_sale() or product.display_name,
                    'price_unit': price_unit,
                }))

        if not order_lines:
            values = self._prepare_form_values(
                partner=partner,
                error=_("Please add at least one product quantity greater than zero."),
                note=note,
                entered_quantities=entered_quantities,
                payment_type=payment_type,
            )
            return request.render('portal_sales_order.portal_apply_sales_order', values)

        invoice_partner = partner.address_get(['invoice']).get('invoice') or partner.id
        shipping_partner = partner.address_get(['delivery']).get('delivery') or partner.id

        sale_order_vals = {
            'partner_id': partner.id,
            'partner_invoice_id': invoice_partner,
            'partner_shipping_id': shipping_partner,
            'pricelist_id': self._get_partner_pricelist(partner).id,
            'order_line': order_lines,
            'origin': _('Portal Sales Order Request'),
            'note': note,
            'user_id': request.env.user.id,
        }
        if 'payment_type' in request.env['sale.order']._fields:
            sale_order_vals['payment_type'] = payment_type

        sale_order = request.env['sale.order'].sudo().create(sale_order_vals)
        sale_order._portal_ensure_token()
        return request.redirect('/my/sales_orders')

    @http.route(['/my/sales_orders'], type='http', auth='user', website=True)
    def my_sales_orders(self, **kwargs):
        user = request.env.user
        sales_orders = request.env['sale.order'].sudo().search([
            ('user_id', '=', user.id)
        ], order='create_date desc')
        return request.render('portal_sales_order.portal_my_sales_orders', {
            'sales_orders': sales_orders,
        })

    @http.route(['/my/customer_profile'], type='http', auth='user', website=True)
    def my_customer_profile(self, **kwargs):
        partner = self._get_available_partners()[:1]
        return request.render('portal_sales_order.portal_my_customer_profile', {
            'partner': partner,
        })