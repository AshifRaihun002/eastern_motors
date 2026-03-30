from datetime import datetime
from email.policy import default

from odoo import models, fields, api, _, tools
from odoo.api import ValuesType, Self
from odoo.tools import float_round
from odoo.exceptions import ValidationError, UserError


class IndentProcess(models.Model):
    _name = 'indent.process'
    _description = 'Indent Process'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'log.history.mixin', 'child.tracking.mixin']

    name = fields.Char(string='Indent Number', default="New", copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('approval_pending', 'Approved Pending'), ('approved', 'Approved'), ('cancel', 'Cancel')],
        string='Status', default='draft', tracking=True)
    requesting_user_id = fields.Many2one('hr.employee', string='Requisitioner',
                                         default=lambda self: self.env.user.employee_id, tracking=True)
    requesting_department_id = fields.Many2one('hr.department', string='Requesting Department', tracking=True)
    indent_type = fields.Selection([
        ('transfer', 'Transfer'),
        ('consume', 'Consume'),
    ], string='Indent Type', default='transfer')
    indent_date = fields.Date(string='Indent Date', default=fields.Datetime.now, tracking=True)
    issue_date = fields.Date(string='Issue Date', compute='_compute_issue_date', store=True, tracking=True)
    location_id = fields.Many2one(
        'stock.location', string='Destination Location', tracking=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]"
    )
    warehouse_id = fields.Many2one('stock.warehouse', string="Destination Warehouse", tracking=True)
    # concern_dept_id = fields.Many2one('hr.department', string='Submitted To', tracking=True)
    indent_ref = fields.Char(string='Indent Reference', tracking=True)
    indent_line_ids = fields.One2many('indent.line', 'indent_id', string='Indent Lines', tracking=True, copy=True)
    approval_config_id = fields.Many2one(
        'approval.config', string='Approval', tracking=True, compute='_compute_indent_approval_config', store=False,
        domain="[('approval_type', '=', 'in_pr'), ('company_id', '=', company_id)]"
    )
    stage_id = fields.Many2one(
        "approval.line", string="Approval Stage", copy=True, tracking=True,
        domain="[('config_id', '=', approval_config_id), ('config_id', '!=', False)]"
    )
    approval_history_ids = fields.One2many(
        'approval.history', 'res_id', string="Approval History",
        domain=lambda self: [('res_model', '=', self._name), ('company_id', '=', self.company_id.id)],
    )
    picking_ids = fields.One2many('stock.picking', 'indent_id', string='Picking', tracking=True)
    picking_count = fields.Integer('Picking Count', compute='_compute_picking_count')
    # transfer_picking_count = fields.Integer('Transfer Picking Count', compute='_compute_picking_transfer_count')
    purchase_requisition_ids = fields.Many2many(
        'custom.purchase.requisition', string='Purchase Requisition ID', compute='_compute_purchase_requisition'
    )
    purchase_requisition_count = fields.Integer('Purchase Requisition Count',
                                                compute='_compute_purchase_requisition_count')

    issue_status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Received'),
        ('received', 'Fully Received'),
    ], string='Issue Status', tracking=True, default='pending', compute='_compute_issue_status', store=True)

    indented_by_id = fields.Many2one('hr.employee', string='Indented By', tracking=True)
    authorised_by_id = fields.Many2one('hr.employee', string='Authorised By', tracking=True)
    issued_by_id = fields.Many2one('hr.employee', string='Issued By', tracking=True)
    received_by_id = fields.Many2one('hr.employee', string='Received By', tracking=True,
                                     compute='_compute_received_by_id', store=True)



    @api.depends('indent_line_ids.issue_status')
    def _compute_issue_status(self):
        for rec in self:
            if all(line.issue_status == 'received' for line in rec.indent_line_ids):
                rec.issue_status = 'received'
            elif any(line.issue_status == 'partial' for line in rec.indent_line_ids):
                rec.issue_status = 'partial'
            else:
                rec.issue_status = 'pending'

    # @api.onchange('factory_plant')
    # def onchange_based_factory_plant(self):
    #     """Changing Factory Plant should reset Product."""
    #     for rec in self:
    #         rec.indent_line_ids = [(5, 0, 0)]



    # is_transit_active = fields.Boolean(
    #     string="Use Transit Location",
    #     compute='_compute_transit_active',
    #     store=False
    # )
    # transit_location_id = fields.Many2one(
    #     'stock.location',
    #     string="Transit Location",
    #     compute='_compute_transit_location',
    #     store=False
    # )
    # is_indent_issue = fields.Boolean(string="Indent Issue", default=False)

    # def _compute_picking_ids(self):
    #     for rec in self:
    #         rec.picking_ids = rec.indent_line_ids.move_ids.picking_id

    # def _compute_picking_transfer_count(self):
    #     for rec in self:
    #         rec.transfer_picking_count = len(rec.picking_ids.filtered(lambda p: p.is_indent_transfer == True))

    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids.ids)

    @api.depends('picking_ids.state', 'picking_ids.date_done')
    def _compute_issue_date(self):
        for rec in self:
            done_pickings = rec.picking_ids.filtered(lambda p: p.state == 'done')
            if done_pickings:
                latest_date = max(done_pickings.mapped('date_done'))
                rec.issue_date = latest_date.date() if latest_date else False
            else:
                rec.issue_date = False

    @api.depends('picking_ids.state', 'picking_ids.date_done')
    def _compute_received_by_id(self):
        for rec in self:
            if rec.picking_ids:
                # Get the user who validated the last done picking
                last_picking = rec.picking_ids.filtered(lambda p: p.state == 'done').sorted('date_done', reverse=True)
                if last_picking:
                    rec.received_by_id = last_picking[0].write_uid.employee_id.id
                else:
                    rec.received_by_id = False
            else:
                rec.received_by_id = False

    def _compute_purchase_requisition(self):
        for indent in self:
            indent.purchase_requisition_ids = self.env['custom.purchase.requisition'].sudo().search([
                ('indent_ids', 'in', indent.id)
            ])

    # @api.depends('company_id')
    # def _compute_transit_active(self):
    #     for record in self:
    #         record.is_transit_active = record.company_id.is_indent_transit_active

    # @api.depends('company_id')
    # def _compute_transit_location(self):
    #     for record in self:
    #         record.transit_location_id = record.company_id.indent_transit_location_id

    @api.depends('purchase_requisition_ids')
    def _compute_purchase_requisition_count(self):
        for rec in self:
            rec.purchase_requisition_count = len(rec.purchase_requisition_ids)

    @api.onchange('location_id')
    def onchange_based_on_location_id(self):
        for rec in self:
            rec.warehouse_id = rec.location_id.warehouse_id.id


    @api.onchange('requesting_user_id')
    def onchange_based_requesting_user_id(self):
        for rec in self:
            rec.requesting_department_id = rec.requesting_user_id.department_id.id


    def action_confirm(self):
        for rec in self:
            if not rec.indent_line_ids:
                raise ValidationError(_("No Products Added to the Indent. Please Add Products to Proceed."))
            if any(line.quantity < 1 for line in rec.indent_line_ids):
                raise ValidationError(_("Indent quantity must be greater than 0."))
            rec.write({
                'state': 'approval_pending',
                'indented_by_id': rec.requesting_user_id.id or self.env.user.employee_id.id
            })

    def action_generate_purchase_requisition(self):
        """Generate a Purchase Requisition from multiple selected Indent Processes."""
        if not self:
            raise UserError(_("Please select at least one Indent Process."))

        # Check compatibility: same department, store and approved state
        first_indent = self[0]
        if any(
               indent.company_id != first_indent.company_id or
               indent.state != 'approved' or
               indent.requesting_department_id != first_indent.requesting_department_id
               for indent in self):
            raise ValidationError(_("Please select same department, units and Approved Indent items."))

        pr_lines_vals = []
        product_groups = {}
        for indent in self:
            for line in indent.indent_line_ids:
                if line.remaining_qty <= 0:
                    continue

                key = line.product_id.id
                if key not in product_groups:
                    product_groups[key] = {
                        'product_id': line.product_id.id,
                        'product_cat_id': line.product_cat_id.id,
                        'specification': tools.html2plaintext(line.product_specification or ''),
                        'product_uom_qty': 0.0,
                        'uom_id': line.product_id.uom_id.id,
                        'price_unit': line.unit_price or 0.0,
                        'remarks': [],
                        'indent_ids': set(),
                        'indent_line_id': line.id,
                    }

                group = product_groups[key]
                group['product_uom_qty'] += line.remaining_qty
                group['indent_ids'].add(indent.id)
                if line.remarks:
                    group['remarks'].append(line.remarks)
                # Use the highest price for the requisition
                if line.unit_price > group['price_unit']:
                    group['price_unit'] = line.unit_price

        for val in product_groups.values():
            pr_lines_vals.append((0, 0, {
                'product_id': val['product_id'],
                'product_cat_id': val['product_cat_id'],
                'specification': val['specification'],
                'product_uom_qty': val['product_uom_qty'],
                'uom_id': val['uom_id'],
                'price_unit': val['price_unit'],
                'remarks': "\n".join(filter(None, val['remarks'])),
                'indent_ids': [(6, 0, list(val['indent_ids']))],
                'indent_line_id': val['indent_line_id'],

            }))

        if not pr_lines_vals:
            raise UserError(_("No valid indent lines found to create Purchase Requisition."))

        requisition_ctx = {
            'default_initiator': first_indent.requesting_user_id.user_id.id if first_indent.requesting_user_id.user_id else self.env.user.id,
            'default_requesting_dept': first_indent.requesting_department_id.id,
            'default_requisition_date': fields.Date.today(),
            'default_warehouse_id': first_indent.warehouse_id.id or False,
            'default_line_ids': pr_lines_vals,
            'default_indent_ids': [(6, 0, self.ids)],
        }

        return {
            'name': _('Purchase Requisition'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.purchase.requisition',
            'view_mode': 'form',
            'target': 'current',
            'context': requisition_ctx,
        }

    def action_view_purchase_requisition(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Requisition'),
            'res_model': 'custom.purchase.requisition',
            'view_mode': 'list,form',
            'domain': [('indent_ids', 'in', self.ids)],
            'target': 'current',
        }

    def create_transfer(self):
        indent_ref = ",".join(self.mapped('name'))
        indent = self[0]
        move_lines = []

        for indent in self:
            if not indent.indent_line_ids:
                raise UserError(_("No lines to transfer."))

            # Check if transit location is active and available
            # use_transit = indent.is_transit_active and indent.transit_location_id
            # indent.is_indent_issue = use_transit  # Set the flag

            source_location = indent.warehouse_id.lot_stock_id.id if indent.warehouse_id else False
            dest_location = indent.location_id.id
            for line in indent.indent_line_ids:
                qty_to_transfer = min(line.quantity, line.on_hand_qty, line.remaining_qty)
                
                # Handling consume type to use product's virtual location
                current_dest_loc = dest_location
                if indent.indent_type == 'consume' and line.product_id.property_stock_inventory:
                    current_dest_loc = line.product_id.property_stock_inventory.id

                move_vals = {
                    'name': line.product_id.display_name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': qty_to_transfer,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': source_location,
                    'location_dest_id': current_dest_loc,
                }

                # Only include custom fields if your stock.move has them
                if 'indent_line_id' in self.env['stock.move']._fields:
                    move_vals['indent_line_id'] = line.id
                if 'unit_rate' in self.env['stock.move']._fields:
                    move_vals['unit_rate'] = line.product_id.standard_price

                move_lines.append((0, 0, move_vals))

            if not move_lines:
                raise UserError(_("No products available in stock to transfer."))

        # Create picking with appropriate locations
        picking_vals = {
            'default_origin': indent_ref,
            'default_location_id': source_location,
            'default_location_dest_id': dest_location,
            'default_picking_type_id': indent.warehouse_id.int_type_id.id if indent.warehouse_id and indent.warehouse_id.int_type_id else False,
            'default_company_id': indent.company_id.id,
            'default_indent_id': indent.id,
            # 'default_move_ids_without_package': move_lines,
        }

        # picking = self.env['stock.picking'].sudo().create(picking_vals)

        # Open the created picking form view
        return {
            'name': _('Internal Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            # 'res_id': picking.id,
            'target': 'current',
            'context': picking_vals,

        }

    def action_view_picking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfer'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'target': 'current',
        }

    def action_view_picking_transfer(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfer'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'target': 'current',
        }

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancel'})

    def send_back_indent(self):
        """Open wizard to capture send-back note"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Back Note'),
            'res_model': 'send.back.wizard',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context': {
                'default_note': '',
                'active_id': self.id,
                'active_model': self._name
            },
        }

    def get_current_stage_sequence(self):
        """Return the sequence of the current stage."""
        self.ensure_one()
        return self.stage_id.sequence if self.stage_id else 0

    def approve_indent(self):
        """Approve Indent with stage flow and log history"""
        self.ensure_one()
        # Validation: Must have lines
        if not self.indent_line_ids:
            raise ValidationError(_("No Products Added to the Indent. Please Add Products to Proceed."))

        # Validation: Must have approval config
        if not self.approval_config_id:
            raise ValidationError(_("No Approval Config found. Please configure approval stages first."))

        current_stage_sequence = self.get_current_stage_sequence()
        current_user = self.env.user.employee_id
        req_user_manager = self.requesting_user_id.parent_id
        req_department = self.requesting_department_id

        # if current_user != req_department.manager_id and current_user != req_user_manager:
        #     raise UserError(_("Only line manager can approve."))

        # Find next stage
        next_stage = self.stage_id.get_next_stage(self.approval_config_id.id, current_stage_sequence,
                                                  self.company_id.id)

        # Check user permission
        if next_stage and self.env.user not in self.stage_id.user_ids:
            raise UserError(_("You are not allowed to approve this stage."))

        # Log to generic approval history
        self._log_history(
            action_type='authorized',
            stage_id=self.stage_id.id,
            to_stage_id=next_stage.id if next_stage else False,
            note=_("Approved by %s") % self.env.user.name
        )

        if next_stage:
            self.write({'stage_id': next_stage.id, 'state': 'approval_pending'})
        else:
            self.write({
                'stage_id': self.stage_id.id,
                'state': 'approved',
                'authorised_by_id': self.env.user.employee_id.id
            })

    @api.onchange('approval_config_id')
    def onchange_approval_config_id(self):
        for rec in self:
            rec.stage_id = self.env["approval.line"].search([
                ('config_id', '=', rec.approval_config_id.id)
            ], limit=1).id

    @api.depends('company_id')
    def _compute_indent_approval_config(self):
        for record in self:
            approval_config = self.env["approval.config"].search([
                ('approval_type', '=', 'in_pr'),
                ('company_id', '=', record.company_id.id)
            ], limit=1)

            if approval_config:
                record.approval_config_id = approval_config
            else:
                raise UserError(_("No Approval Config found. Please configure indent approval stages first."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                requested_date = datetime.today().date()
                new_seq = self.env['ir.sequence'].next_by_code(self._name, requested_date) or '/'
                vals['name'] = new_seq
        return super(IndentProcess, self).create(vals_list)


class IndentLine(models.Model):
    _name = 'indent.line'
    _description = 'Indent Line'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'child.tracking.mixin']
    _parent_tracking_field = 'indent_id'

    serial_no = fields.Char(string='Ref', default="New", copy=False)
    indent_id = fields.Many2one('indent.process', string='Indent', tracking=True)
    company_id = fields.Many2one('res.company', related='indent_id.company_id', string='Company', store=True)
    indent_state = fields.Selection(related='indent_id.state', string='Indent State', tracking=True, store=True)
    indent_date = fields.Date(related='indent_id.indent_date', string='Indent Date', store=True)
    product_id = fields.Many2one('product.product', string='Product', tracking=True)
    product_cat_id = fields.Many2one('product.category', string='Product Category', tracking=True)
    department_id = fields.Many2one('hr.department', related='indent_id.requesting_department_id', string='Department',
                                    store=True)

    product_specification = fields.Html(string='Product Specification')
    quantity = fields.Float(string='Quantity', default=1.0, tracking=True)
    product_uom = fields.Many2one('uom.uom', string='Unit', tracking=True)
    unit_price = fields.Float(string='Last PO Unit Price', tracking=True)
    transferred_qty = fields.Float(string='Issue Qty', compute='_compute_transferred_qty', store=False, tracking=False)
    returned_qty = fields.Float(string='Return Qty', compute='_compute_returned_qty', store=False, tracking=False)
    remaining_qty = fields.Float(string='Remaining Qty', tracking=True, compute='_compute_remaining_qty', store=False)
    on_hand_qty = fields.Float(string='Available Qty', compute="_get_on_hand_qty", store=False)
    received_qty = fields.Float(string='Received Qty', compute='_compute_received_qty', store=False, tracking=True)
    remarks = fields.Text(string='Remarks', tracking=True)
    move_ids = fields.One2many('stock.move', 'indent_line_id')
    issue_status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Received'),
        ('received', 'Fully Received'),
    ], string='Issue Status', tracking=True, compute='_set_issue_status')

    @api.depends(
        'move_ids.state',
        'move_ids.quantity',
        'move_ids.origin_returned_move_id',
        'move_ids.picking_id.picking_type_id.code',
        'quantity',
    )
    @api.onchange('product_cat_id')
    def onchange_product_cat_id(self):
        for rec in self:
            rec.product_id = False
            rec.quantity = False
            rec.on_hand_qty = False
            rec.transferred_qty = False
            rec.returned_qty = False
            rec.remaining_qty = False
            rec.issue_status = False
            rec.remarks = False

    @api.depends(
        'move_ids.state', 'move_ids.quantity',
        'move_ids.origin_returned_move_id', 'quantity',
        'move_ids.picking_id.picking_type_id.code',
    )
    def _compute_returned_qty(self):
        for line in self:
            if not line.indent_id or not line.product_id:
                line.returned_qty = 0.0
                continue

            # only internal transfers that are done
            moves = line.move_ids.filtered(
                lambda mv: mv.state == 'done'
                           and mv.picking_id.picking_type_id.code == 'internal'
            )

            returned = 0.0
            issued = 0.0

            for mv in moves:
                qty = mv.quantity  # best practice for done moves

                if mv.origin_returned_move_id:
                    # this is a return move (back to stock)
                    returned += qty
                else:
                    # this is an issue/normal internal movement
                    issued += qty

            # If you want "how much returned out of what was issued"
            net_returned = max(0.0, returned)  # usually returned is what you want directly

            # Cap by requested qty (your line.quantity)
            line.returned_qty = min(net_returned, line.quantity)

    @api.depends('transferred_qty', 'quantity')
    def _set_issue_status(self):
        """Set issue status based on transferred_qty and remaining_qty"""
        for line in self:
            if line.transferred_qty == line.quantity:
                line.issue_status = 'received'
            elif line.transferred_qty > 0:
                line.issue_status = 'partial'
            else:
                line.issue_status = 'pending'

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.serial_no}"



    # @api.depends('product_id')
    # def _product_cat_get(self):
    #     for line in self:
    #         line.product_cat_id = line.product_id.categ_id.id if line.product_id else False

    def action_generate_purchase_requisition_item(self):
        """Generate a Purchase Requisition from selected Indent Lines."""
        if not self:
            raise UserError(_("Please select at least one Indent Line."))

        # Validate compatibility (same department, store and approved state)
        indents = self.mapped('indent_id')
        first_indent = indents[0]
        if any(
               indent.company_id != first_indent.company_id or
               indent.state != 'approved' or
               indent.requesting_department_id != first_indent.requesting_department_id
               for indent in indents):
            raise ValidationError(_("Please select same department, units and Approved Indent items."))

        pr_lines_vals = []
        product_groups = {}
        for line in self:
            if line.remaining_qty <= 0:
                continue

            key = line.product_id.id
            if key not in product_groups:
                product_groups[key] = {
                    'product_id': line.product_id.id,
                    'product_cat_id': line.product_cat_id.id,
                    'specification': tools.html2plaintext(line.product_specification or ''),
                    'product_uom_qty': 0.0,
                    'uom_id': line.product_id.uom_id.id,
                    'price_unit': line.unit_price or 0.0,
                    'remarks': [],
                    'indent_ids': set(),
                    'indent_line_id': line.id,
                }

            group = product_groups[key]
            group['product_uom_qty'] += line.remaining_qty
            group['indent_ids'].add(line.indent_id.id)
            if line.remarks:
                group['remarks'].append(line.remarks)
            # Use the highest price for the requisition
            if line.unit_price > group['price_unit']:
                group['price_unit'] = line.unit_price

        for val in product_groups.values():
            pr_lines_vals.append((0, 0, {
                'product_id': val['product_id'],
                'product_cat_id': val['product_cat_id'],
                'specification': val['specification'],
                'product_uom_qty': val['product_uom_qty'],
                'uom_id': val['uom_id'],
                'price_unit': val['price_unit'],
                'remarks': "\n".join(filter(None, val['remarks'])),
                'indent_ids': [(6, 0, list(val['indent_ids']))],
                'indent_line_id': val['indent_line_id'],

            }))

        if not pr_lines_vals:
            raise UserError(_("No valid indent lines selected to create Purchase Requisition."))

        requisition_ctx = {
            'default_initiator': first_indent.requesting_user_id.user_id.id if first_indent.requesting_user_id.user_id else self.env.user.id,
            'default_requesting_dept': first_indent.requesting_department_id.id,
            'default_requisition_date': fields.Date.today(),
            'default_warehouse_id': first_indent.warehouse_id.id or False,

            'default_line_ids': pr_lines_vals,
            'default_indent_ids': [(6, 0, indents.ids)],
        }

        return {
            'name': _('Purchase Requisition'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.purchase.requisition',
            'view_mode': 'form',
            'target': 'current',
            'context': requisition_ctx,
        }

    def create_transfer(self):
        move_lines = []
        indent_ref = ",".join(self.mapped('serial_no'))
        indent = self.indent_id[0]
        for line in self:
            qty_to_transfer = min(line.quantity, line.on_hand_qty, line.remaining_qty)
            
            # Handling consume type to use product's virtual location
            current_dest_loc = indent.location_id.id
            if indent.indent_type == 'consume' and line.product_id.property_stock_inventory:
                current_dest_loc = line.product_id.property_stock_inventory.id

            move_vals = {
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': qty_to_transfer,
                'product_uom': line.product_id.uom_id.id,
                'location_id': indent.warehouse_id.lot_stock_id.id if indent.warehouse_id else False,
                'location_dest_id': current_dest_loc,
            }

            # Only include custom fields if your stock.move has them
            if 'indent_line_id' in self.env['stock.move']._fields:
                move_vals['indent_line_id'] = line.id
            if 'unit_rate' in self.env['stock.move']._fields:
                move_vals['unit_rate'] = line.product_id.standard_price

            move_lines.append((0, 0, move_vals))

        if not move_lines:
            raise UserError(_("No products available in stock to transfer."))

        picking_vals = {
            'origin': indent_ref,
            # 'location_id': indent.warehouse_id.lot_stock_id.id if indent.warehouse_id else False,
            'location_dest_id': indent.location_id.id if indent.location_id else False,
            'picking_type_id': indent.warehouse_id.int_type_id.id if indent.warehouse_id and indent.warehouse_id.int_type_id else False,
            'company_id': indent.company_id.id,
            'move_ids_without_package': move_lines,
        }
        if 'indent_id' in self.env['stock.picking']._fields:
            picking_vals['indent_id'] = indent.id
        picking = self.env['stock.picking'].sudo().create(picking_vals)

        # Open the created picking form view
        return {
            'name': _('Internal Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals_list):
        """
        Generate serial_no like <indent_name>-001, -002, etc.
        Works even for multi-record creation with the same indent.
        """
        # Group records by indent_id for bulk numbering
        indent_groups = {}
        for vals in vals_list:
            indent_id = vals.get('indent_id')
            if not indent_id:
                raise ValidationError(_("Indent reference is missing."))
            indent_groups.setdefault(indent_id, []).append(vals)

        for indent_id, records in indent_groups.items():
            indent = self.env['indent.process'].browse(indent_id)
            if not indent:
                raise ValidationError(_("Indent not found."))

            # Find the last number already used for this indent
            existing_lines = self.env['indent.line'].sudo().search([('indent_id', '=', indent_id)], order='id desc',
                                                                   limit=1)
            last_number = 0
            if existing_lines and existing_lines.serial_no:
                # Extract the last numeric part if it exists (e.g. "IND00035-005" → 5)
                try:
                    last_number = int(existing_lines.serial_no.split('-')[-1])
                except ValueError:
                    last_number = 0

            # Assign serial numbers incrementally
            for i, vals in enumerate(records, start=1):
                if vals.get('serial_no', _('New')) == _('New'):
                    next_number = last_number + i
                    vals['serial_no'] = f"{indent.name}-{next_number:03d}"

        return super(IndentLine, self).create(vals_list)

    @api.onchange('product_id')
    def onchange_based_product_id(self):
        for rec in self:
            rec.product_specification = rec.product_id.product_tmpl_id.description
            rec.product_uom = rec.product_id.uom_id.id

    @api.depends('move_ids', 'move_ids.state', 'move_ids.product_uom_qty', 'move_ids.picking_id.picking_type_id.code')
    def _compute_transferred_qty(self):
        for line in self:
            total_done = 0.0

            if not line.indent_id or not line.product_id:
                line.transferred_qty = 0.0
                continue

            # Get all moves related to this indent line
            moves = line.move_ids.filtered(lambda mv: mv.state == 'done')

            for move in moves:
                if move.origin_returned_move_id and move.picking_id.picking_type_id.code == 'internal':
                    # Return move → subtract from transferred
                    total_done -= move.product_uom_qty
                elif move.picking_id.picking_type_id.code == 'internal':
                    # Normal internal transfer (out) → add
                    total_done += move.product_uom_qty

            line.transferred_qty = min(total_done, line.quantity)

    @api.depends('move_ids', 'move_ids.state', 'move_ids.quantity', 'move_ids.picking_id.picking_type_id.code',
                 'move_ids.location_dest_id')
    def _compute_received_qty(self):
        """Compute received quantity from final destination moves"""
        for line in self:
            total_received = 0.0

            if not line.indent_id or not line.product_id:
                line.received_qty = 0.0
                continue

            # Get all done moves for this indent line
            moves = line.move_ids.filtered(lambda mv: mv.state == 'done')

            for move in moves:
                # Check if this move is going to the final destination location
                is_final_destination = (
                        move.location_dest_id == line.indent_id.location_id or
                        move.location_dest_id == line.indent_id.location_id.location_id  # In case of nested locations
                )

                # For transit scenario: received when goods reach final destination
                if is_final_destination and move.picking_id.picking_type_id.code == 'internal':
                    if move.origin_returned_move_id:
                        # Return move from final destination → subtract from received
                        total_received -= move.quantity
                    else:
                        # Normal move to final destination → add to received
                        total_received += move.quantity

            line.received_qty = min(total_received, line.quantity)

    @api.depends('quantity', 'transferred_qty')
    def _compute_remaining_qty(self):
        for line in self:
            remaining = line.quantity - line.transferred_qty
            line.remaining_qty = max(remaining, 0.0)

    @api.onchange('product_id')
    def _onchange_available_quantity(self):
        for rec in self:
            domain = [('company_id', '=', self.env.company.id)]
            if rec.product_id:
                domain.append(('product_id', '=', rec.product_id.id))
            po_line_id = self.env['purchase.order.line'].search(domain, order='id desc', limit=1)
            rec.unit_price = po_line_id.price_unit or 0.0

    @api.depends('indent_id.warehouse_id.lot_stock_id', 'product_id')
    def _get_on_hand_qty(self):
        for rec in self:
            location_obj = self.env['stock.location'].search(
                [('usage', '=', 'internal')])
            available_lines = self.env['stock.quant'].sudo().search(
                [('product_id', '=', rec.product_id.id),
                 ('location_id', 'in', location_obj.ids)]
            )
            available_qty = sum(available_lines.mapped('available_quantity'))
            rec.on_hand_qty = available_qty

    def action_open_quants(self):
        self.ensure_one()
        action = self.product_id.action_open_quants()
        action['name'] = _('Available Quantity')
        action['context'].update({'create': False, 'edit': False})
        return action


class ApprovalLine(models.Model):
    _inherit = 'approval.config'

    approval_type = fields.Selection(selection_add=[('in_pr', 'Indent Process')], ondelete={'in_pr': 'set default'})
