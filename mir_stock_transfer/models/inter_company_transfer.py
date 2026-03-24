from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InterCompanyTransfer(models.Model):
    _name = 'inter.company.transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Inter Company Transfer'
    _order = 'id desc'

    name = fields.Char(string='Transfer No.', required=True, copy=False, readonly=True, default='New')
    date = fields.Date(string='Transfer Date', default=fields.Date.context_today, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('sent', 'Sent'), ('done', 'Done'), ('cancel', 'Cancelled')],
                             default='draft', string="Status", tracking=True, copy=False)
    source_company_id = fields.Many2one('res.company', string='Source', default=lambda self: self.env.company, tracking=True)
    destination_company_id = fields.Many2one('res.company', string='Destination', tracking=True)
    notes = fields.Html(string="Description")
    source_warehouse_id = fields.Many2one('stock.warehouse', string='Source Warehouse', tracking=True,
                                          domain="[('company_id', '=', source_company_id)]")
    destination_warehouse_id = fields.Many2one('stock.warehouse', string='Destination Warehouse', tracking=True,
                                               domain="[('company_id', '=', destination_company_id)]")
    source_location_id = fields.Many2one('stock.location', string='Source Location', tracking=True,
                                         domain="[('usage', '=', 'internal'), ('warehouse_id', '=', source_warehouse_id), ('company_id', '=', source_company_id)]")
    destination_location_id = fields.Many2one('stock.location', string='Destination Location', tracking=True,
                                              domain="[('usage', '=', 'internal'), ('warehouse_id', '=', destination_warehouse_id), ('company_id', '=', destination_company_id)]")
    transfer_status = fields.Selection([('pending', 'Pending'),
                                        ('full', 'Fully Transferred')], string="Transfer Status", default='pending',
                                       compute='_compute_transfer_status', store=True, tracking=True)
    receiving_status = fields.Selection([('pending', 'Pending'), ('partial', 'Partially Received'),
                                         ('full', 'Fully Received')], string="Receiving Status", default='pending',
                                        compute='_compute_receiving_status', store=True, tracking=True)
    picking_ids = fields.One2many('stock.picking', 'inter_company_transfer_id', string='Transfers')
    picking_count = fields.Integer(string="Transfer Count", compute='_compute_picking_count', store=True)
    transfer_line_ids = fields.One2many('inter.company.transfer.line', 'transfer_id', string='Transfer Lines')
    active=fields.Boolean(default=True)
    is_fixed_asset_transfer = fields.Boolean(default=False, string="Fixed Asset Transfer?")
    account_move_ids = fields.One2many('account.move', 'inter_company_transfer_id', string='Account Moves')
    account_move_count = fields.Integer(string="Account Move Count", compute='_compute_account_move_count', store=True)

    requisition_id = fields.Many2one('custom.purchase.requisition', string='Requisition No.')

    @api.onchange('source_company_id')
    def _onchange_source_company_id(self):
        for record in self:
            if record.source_company_id:
                source_warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', record.source_company_id.id)], limit=1)
                record.source_warehouse_id = source_warehouse.id if source_warehouse else False

    @api.onchange('destination_company_id')
    def _onchange_destination_company_id(self):
        for record in self:
            if record.destination_company_id:
                destination_warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', record.destination_company_id.id)], limit=1)
                record.destination_warehouse_id = destination_warehouse.id if destination_warehouse else False

    @api.onchange('source_warehouse_id')
    def _onchange_source_warehouse_id(self):
        for record in self:
            if record.source_warehouse_id:
                record.source_location_id = record.source_warehouse_id.lot_stock_id.id or False

    @api.onchange('destination_warehouse_id')
    def _onchange_destination_warehouse_id(self):
        for record in self:
            if record.destination_warehouse_id:
                record.destination_location_id = record.destination_warehouse_id.lot_stock_id.id or False

    def action_view_account_moves(self):
        self.ensure_one()
        return {
            'name': 'Account Moves',
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.account_move_ids.ids)],
            'context': {'create': False, 'delete': False}
        }

    @api.depends('account_move_ids')
    def _compute_account_move_count(self):
        for record in self:
            record.account_move_count = len(record.account_move_ids) if record.account_move_ids else 0

    def button_cancel(self):
        for record in self:
            if record.state == 'done':
                raise UserError("Transfer is already completed!")

            record.state = 'cancel'

    @api.depends('transfer_line_ids.transfer_status')
    def _compute_transfer_status(self):
        for record in self:
            if record.transfer_line_ids:
                if all(line.transfer_status == 'full' for line in record.transfer_line_ids):
                    record.transfer_status = 'full'
                else:
                    record.transfer_status = 'pending'

    @api.depends('transfer_line_ids.receiving_status')
    def _compute_receiving_status(self):
        for record in self:
            if record.transfer_line_ids:
                if all(line.receiving_status == 'full' for line in record.transfer_line_ids):
                    record.receiving_status = 'full'
                elif any(line.receiving_status == 'partial' for line in record.transfer_line_ids):
                    record.receiving_status = 'partial'
                else:
                    record.receiving_status = 'pending'

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids) if record.picking_ids else 0

    def action_view_transfers(self):
        self.ensure_one()
        return {
            'name': 'Transfers',
            'view_mode': 'list,form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {'create': False, 'delete': False}
        }

    def action_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'confirm'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('inter.company.transfer') or _('New')

        return super(InterCompanyTransfer, self).create(vals_list)

    def unlink(self):
        for record in self:
            if record.state not in ('draft', 'cancel'):
                raise UserError('You can not delete any Transfer which is not in draft state!')
        return super().unlink()

    def button_send(self):
        for record in self:
            if record.state != 'confirm':
                raise UserError("The transfer must be in 'Confirm' state to send a transfer!")

            picking_type_out = self.env['stock.picking.type'].sudo().search([
                ('code', '=', 'internal'),
                ('warehouse_id', '=', self.source_warehouse_id.id)
            ], limit=1)

            if not picking_type_out:
                raise UserError("Missing internal transfer type for the source warehouse!")

            source_adjustment_location = self.sudo().source_company_id.inter_company_adjustment_location_id

            if not source_adjustment_location:
                raise UserError("Missing adjustment location for the source company!")

            move_lines_out = []
            for line in self.transfer_line_ids:
                source_cost = line.product_id.with_company(self.sudo().source_company_id).standard_price
                move_lines_out.append((0, 0, {
                    # 'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'price_unit': source_cost,
                    'product_uom': line.product_uom_id.id,
                    'location_id': self.source_location_id.id,
                    'location_dest_id': source_adjustment_location.id,
                    'inter_company_transfer_line_id': line.id,
                    'company_id': self.source_company_id.id
                }))

            picking_out = self.env['stock.picking'].sudo().create({
                'move_ids': move_lines_out,
                'picking_type_id': picking_type_out.id,
                'location_id': self.source_location_id.id,
                'location_dest_id': source_adjustment_location.id,
                'origin': self.name,
                'scheduled_date': self.date,
                'inter_company_transfer_id': self.id,
                'company_id': self.source_company_id.id
            })

            picking_out.sudo().with_context(skip_backorder=True).button_validate()
            self.state = 'sent'


    def button_validate_transfer(self):
        self.ensure_one()

        if not self.transfer_line_ids:
            raise UserError("No product lines to transfer. Please add products to proceed!")

        if self.state != 'sent':
            raise UserError("The transfer must be in 'Confirm' state to create a transfer!")

        picking_type_in = self.destination_warehouse_id.int_type_id

        if not picking_type_in:
            raise UserError("Missing internal transfer type for the destination warehouse!")

        destination_adjustment_location = self.sudo().destination_company_id.inter_company_adjustment_location_id

        if not destination_adjustment_location:
            raise UserError("Missing adjustment locations for the destination company!")

        if any(line.received_quantity <= 0 for line in self.transfer_line_ids):
            raise UserError("Received quantity cannot be zero for any product line!")

        move_lines_in = []
        for line in self.transfer_line_ids:
            source_cost = line.product_id.sudo().with_company(self.sudo().source_company_id).standard_price
            move_lines_in.append((0, 0, {
                # 'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.received_quantity,
                'product_uom': line.product_uom_id.id,
                'price_unit': source_cost,
                'location_id': destination_adjustment_location.id,
                'location_dest_id': self.destination_location_id.id,
                'inter_company_transfer_line_id': line.id,
                'company_id': self.destination_company_id.id
            }))

        picking_in = self.env['stock.picking'].sudo().create({
            'move_ids': move_lines_in,
            'picking_type_id': picking_type_in.id,
            'location_id': destination_adjustment_location.id,
            'location_dest_id': self.destination_location_id.id,
            'origin': self.name,
            'scheduled_date': self.date,
            'inter_company_transfer_id': self.id,
            'company_id': self.destination_company_id.id
        })

        picking_in.sudo().with_context(skip_backorder=True).button_validate()

        self.state = 'done'
        # self.sudo().post_ho_journal_entry() if not self.is_fixed_asset_transfer else self.sudo().post_asset_journal_entry()

    def post_ho_journal_entry(self):
        self.ensure_one()
        for line in self.transfer_line_ids:
            ho = self.env['res.company'].sudo().search([('is_head_office', '=', True)])
            if not ho:
                raise UserError("Head Office company not found!")

            valuation_journal = ho.sudo().inter_company_stock_valuation_journal_id
            if not valuation_journal:
                raise UserError("Head Office Inter Company Stock Valuation Journal not found!")

            move = self.env['account.move'].sudo().create({
                'ref': f"HO Journal Entry for {self.name}",
                'date': fields.Date.context_today(self),
                'journal_id': valuation_journal.id,
                'company_id': ho.id,
                'line_ids': [(0, 0, {
                    'name': line.product_id.display_name,
                    'debit': (line.product_id.standard_price * line.received_quantity),
                    'credit': 0.0,
                    'account_id': self.sudo().destination_company_id.current_account_id.id,
                    'company_id': ho.id
                }), (0, 0, {
                    'name': line.product_id.display_name,
                    'debit': 0.0,
                    'credit': (line.product_id.standard_price * line.received_quantity),
                    'account_id': self.sudo().source_company_id.current_account_id.id  ,
                    'company_id': ho.id
                })],
            })

            move.sudo().action_post()

    def post_asset_journal_entry(self):
        self.ensure_one()
        ho = self.env['res.company'].sudo().search([('is_head_office', '=', True)])
        ho_current_account = ho.sudo().current_account_id
        if not ho or not ho_current_account:
            raise UserError("Head Office Current Account not found!")

        cc1_current_account = self.sudo().source_company_id.current_account_id
        cc2_current_account = self.sudo().destination_company_id.current_account_id

        if not cc1_current_account or not cc2_current_account:
            raise UserError("Current Account not found!")

        for line in self.transfer_line_ids:
            remaining_value = line.asset_value - line.book_value

            cc1_move = self.env['account.move'].sudo().create({
                'ref': f"{self.source_company_id.name} Journal Entry for {self.name}",
                'date': fields.Date.context_today(self),
                'journal_id': line.asset_id.journal_id.id,
                'company_id': self.source_company_id.id,
                'inter_company_transfer_id': self.id,
                'line_ids': [(0, 0, {
                    'name': line.asset_id.name,
                    'account_id': ho_current_account.id,
                    'debit': line.asset_value,
                    'company_id': self.source_company_id.id
                }), (0, 0, {
                    'name': line.asset_id.name,
                    'account_id': line.asset_id.account_asset_id.id,
                    'credit': line.asset_value,
                    'company_id': self.source_company_id.id
                }), (0, 0, {
                    'name': line.asset_id.name,
                    'account_id': line.asset_id.account_depreciation_id.id,
                    'debit': remaining_value,
                    'company_id': self.source_company_id.id
                }), (0, 0, {
                    'name': line.asset_id.name,
                    'account_id': ho_current_account.id,
                    'credit': remaining_value,
                    'company_id': self.source_company_id.id
                })]
            })
            cc1_move.sudo().action_post()

            cc2_move = self.env['account.move'].sudo().create({
                'ref': f"{self.destination_company_id.name} Journal Entry for {self.name}",
                'date': fields.Date.context_today(self),
                'journal_id': self.env['account.journal'].search(
                    [('company_id', '=', self.destination_company_id.id), ('type', '=', 'general')], limit=1).id,
                'company_id': self.destination_company_id.id,
                'inter_company_transfer_id': self.id,
                'line_ids': [(0, 0, {
                    'name': line.asset_id.name,
                    'account_id': line.asset_id.account_asset_id.id,
                    'debit': line.asset_value,
                    'company_id': self.destination_company_id.id
                }), (0, 0, {
                    'name': line.asset_id.name,
                    'account_id': ho_current_account.id,
                    'credit': line.asset_value,
                    'company_id': self.destination_company_id.id
                }), (0, 0, {
                    'name': line.asset_id.name,
                    'account_id': line.asset_id.account_depreciation_id.id,
                    'credit': remaining_value,
                    'company_id': self.destination_company_id.id
                }), (0, 0, {
                    'name': line.asset_id.name,
                    'account_id': ho_current_account.id,
                    'debit': remaining_value,
                    'company_id': self.destination_company_id.id
                })]
            })
            cc2_move.sudo().action_post()

            ho_move = self.env['account.move'].sudo().create({
                'ref': f"{ho.name} Journal Entry for {self.name}",
                'date': fields.Date.context_today(self),
                'journal_id': self.env['account.journal'].sudo().search(
                    [('company_id', '=', ho.id), ('type', '=', 'general')], limit=1).id,
                'company_id': ho.id,
                'inter_company_transfer_id': self.id,
                'line_ids': [(0, 0, {
                    'name': line.asset_id.name,
                    'account_id': cc2_current_account.id,
                    'debit': (line.asset_value - line.book_value),
                    'credit': 0.0,
                    'company_id': ho.id
                }), (0, 0, {
                    'name': line.asset_id.name,
                    'account_id': cc1_current_account.id,
                    'credit': (line.asset_value - line.book_value),
                    'debit': 0.0,
                    'company_id': ho.id
                })]
            })
            ho_move.sudo().action_post()

            line.asset_id.sudo().write({'company_id': self.sudo().destination_company_id.id,
                                        'asset_location_id': self.sudo().destination_warehouse_id.id})




class InterCompanyTransferLine(models.Model):
    _name = 'inter.company.transfer.line'
    _description = 'Inter Company Transfer Line'

    transfer_id = fields.Many2one('inter.company.transfer', string='Transfer', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product')
    asset_id = fields.Many2one('account.asset', string='Asset')
    book_value = fields.Float(string='Book Value')
    asset_value = fields.Float(string='Asset Value')
    product_uom_id = fields.Many2one('uom.uom', string='UoM')
    quantity = fields.Float(string='Transfer Quantity', default=1)
    transfer_status = fields.Selection([('pending', 'Pending'), ('full', 'Fully Transferred')], string="Transfer Status",
                                       default='pending', compute='_compute_transfer_status', store=True)
    receiving_status = fields.Selection([('pending', 'Pending'), ('partial', 'Partially Received'),
                                         ('full', 'Fully Received')], string="Receiving Status", default='pending',
                                        compute='_compute_receiving_status', store=True)
    move_ids = fields.One2many('stock.move', 'inter_company_transfer_line_id', string='Moves')
    received_quantity = fields.Float(string='Received Quantity')
    transfer_date = fields.Date(string='Transfer Date', related='transfer_id.date', store=True)
    source_company_id = fields.Many2one('res.company', string='Source Company', related='transfer_id.source_company_id')
    destination_company_id = fields.Many2one('res.company', string='Destination Company', related='transfer_id.destination_company_id')
    source_warehouse_id = fields.Many2one('stock.warehouse', string='Source Warehouse', related='transfer_id.source_warehouse_id')
    destination_warehouse_id = fields.Many2one('stock.warehouse', string='Destination Warehouse', related='transfer_id.destination_warehouse_id')

    requisition_line_id = fields.Many2one('custom.purchase.requisition.line', string='Requisition Line ID')

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.transfer_id.is_fixed_asset_transfer and line.quantity != 1:
                raise UserError("Quantity must be 1 for Fixed Asset Transfer")

    @api.onchange('asset_id')
    def _onchange_asset_id(self):
        for line in self:
            line.book_value = line.asset_id.book_value
            line.asset_value = line.asset_id.original_value

    @api.depends('quantity', 'transfer_id.state')
    def _compute_transfer_status(self):
        for line in self:
            if line.quantity <= 0:
                line.transfer_status = 'pending'
            elif line.transfer_id.state in ('sent', 'done'):
                line.transfer_status = 'full'
            else:
                line.transfer_status = 'pending'


    @api.depends('received_quantity', 'quantity', 'transfer_id.state')
    def _compute_receiving_status(self):
        for line in self:
            if line.received_quantity >= line.quantity and line.transfer_id.state == 'done':
                line.receiving_status = 'full'
            elif line.received_quantity > 0 and line.received_quantity < line.quantity and line.transfer_id.state == 'done':
                line.receiving_status = 'partial'
            else:
                line.receiving_status = 'pending'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id


class AccountMove(models.Model):
    _inherit = 'account.move'

    inter_company_transfer_id = fields.Many2one('inter.company.transfer', string='Inter Company Transfer Line')
