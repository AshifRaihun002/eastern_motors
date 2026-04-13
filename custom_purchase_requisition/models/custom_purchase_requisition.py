from itertools import product
from urllib import parse
from datetime import datetime, timedelta
from markupsafe import Markup
from odoo.http import request
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

class PurchaseRequisition(models.Model):
    _name = 'custom.purchase.requisition'
    _inherit = ['mail.thread', 'log.history.mixin']
    _description = 'Purchase Requisition'
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, tracking=True, readonly=True, default='/')
    initiator = fields.Many2one('res.users', string='Initiator', default=lambda self: self.env.user, auto_join=True,
                                readonly=True)
    purchase_type = fields.Selection(
        [
            ('local', 'Local Purchase'),
            ('central', 'HO'),
            ('factory', 'Factory'),
        ],
        string='Purchase Type',
        default='central',
        required=True
    )
    concern_dept = fields.Many2one('hr.department', string='Concern Department', readonly=False,
                                   domain="[('is_procurement', '=', True)]")

    requisition_date = fields.Date(
        string='Requisition Date ',
        required=True, help='requisition Date.',
        default=datetime.today(), readonly=True
    )

    state = fields.Selection([
        ('draft', "Draft"),
        ('approval_pending', "Approval Pending"),
        ('done', "Approved"),
        ('sent_back', 'Sent Back'),
        ('cancel', "cancel"),
    ],
        default='draft', string="State", tracking=True,
        required=True, readonly=True
    )

    remarks = fields.Text(translate=True)

    product_cat_id = fields.Many2one('product.category', string='Product Category', tracking=True, copy=False)

    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')

    line_ids = fields.One2many(
        comodel_name='custom.purchase.requisition.line',
        inverse_name='requisition_id',
        string="Purchase Requisition Line",
        copy=True, auto_join=True
    )

    requesting_dept = fields.Many2one('hr.department', string="Requesting Department")
    total_amount = fields.Float(string="Total Amount", compute='_compute_total_amount', store=True)


    approval_history_new_ids = fields.One2many(
        'approval.history',
        'res_id',
        string="Approval History New",
        domain="[('res_model', '=', _name), ('company_id', '=', company_id)]",
    )
    approval_config_id = fields.Many2one(
        'approval.config', string='Approval TOA',
        domain="[('approval_type', '=', 'requisition'), ('company_id', '=', company_id)]", copy=False
    )

    stage_id = fields.Many2one(
        "approval.line",
        "Approval Stage",
        domain="[('config_id', '=', approval_config_id), ('config_id', '!=', False)]",
        copy=False,
        tracking=True,
    )

    is_user_approver = fields.Boolean(
        string='Is User Approver',
        compute='_compute_is_user_approver'
    )
    is_review = fields.Boolean(string='Is Review', default=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)
    action_type = fields.Selection(
        [
            ('create', 'Create'),
            ('authorized', 'Authorized'),
            ('sent_back', 'Sent Back'),
            ('review', 'Review'),
            ('cancel', 'Cancel'),
            ('draft', 'Reset to Draft'),
            ('confirmed', 'Confirm'),
            ('posted', 'Post'),
            ('paid', 'Paid'),
        ],
        string='Action Type',
        compute='_compute_action_type',
        store=False,
    )
    po_ids = fields.Many2many(
        'purchase.order',
        string='Purchase Orders',
        compute='_compute_po_data',
        store=False
    )

    po_count = fields.Integer(
        string='PO Count',
        compute='_compute_po_data'
    )

    def _compute_po_data(self):
        for rec in self:
            pos = rec.line_ids.mapped('purchase_order_line_ids.order_id')
            rec.po_ids = pos
            rec.po_count = len(pos)

    def action_view_purchase_orders(self):
        self.ensure_one()

        purchase_orders = self.line_ids.mapped('purchase_order_line_ids.order_id')

        if not purchase_orders:
            raise UserError(_("No Purchase Orders found for this requisition."))

        if len(purchase_orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Purchase Order'),
                'res_model': 'purchase.order',
                'view_mode': 'form',
                'res_id': purchase_orders.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', purchase_orders.ids)],
            'target': 'current',
        }

    @api.onchange('purchase_type', 'concern_dept', 'company_id')
    def _onchange_approval_config_id(self):
        for rec in self:
            domain = [
                ('approval_type', '=', 'requisition'),
                ('company_id', '=', rec.company_id.id),
                ('approval_subtype', '=', rec.purchase_type),
                ('approval_dept', '=', rec.concern_dept.id),
            ]
            return {'domain': {'approval_config_id': domain}}

    @api.depends('approval_history_new_ids.action_type', 'approval_history_new_ids.create_date')
    def _compute_action_type(self):
        for record in self:
            # Sort by create_date descending to get the latest
            histories = record.approval_history_new_ids.sorted(lambda h: h.create_date or fields.Datetime.now(),
                                                               reverse=True)
            record.action_type = histories[0].action_type if histories else False

    @api.depends('stage_id.user_ids')
    def _compute_is_user_approver(self):
        for rec in self:
            is_erp_manager = False
            has_approval_access = self.env.user in rec.stage_id.user_ids

            # Check if the current user is in the 'erp_manager' group
            erp_manager_group = self.env.ref('base.group_erp_manager')
            if erp_manager_group and self.env.user in erp_manager_group.user_ids:
                is_erp_manager = True

            rec.is_user_approver = has_approval_access or is_erp_manager

    def send_back_note(self):
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

    def button_draft(self):
        """
        Reset requisition to draft state and reset to first approval stage
        """
        for requisition in self:
            requisition.ensure_one()

            # Check if we can reset to draft based on current state
            if requisition.state not in ['cancel']:
                raise UserError(
                    _("You can only reset requisitions that are in approval pending, approved, sent back, or cancelled state."))

            # Reset approval stage if approval config exists
            if requisition.approval_config_id:
                first_stage = self.env['approval.line'].search([
                    ('config_id', '=', requisition.approval_config_id.id)
                ], order='sequence asc', limit=1)

                if first_stage:
                    requisition.stage_id = first_stage.id
                else:
                    raise UserError(_("No stages defined for the selected approval configuration."))

            # Reset state to draft
            requisition.state = 'draft'

            # Optionally reset other fields
            requisition.is_review = False


            # Reset all requisition lines to draft
            for line in requisition.line_ids:
                line.state = 'draft'
                line.is_processed = False
                line.pro_state = False
                line.selected = False

        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                requested_date = datetime.today().date()
                company_id = vals.get('company_id') or self.env.company.id
                new_seq = self.env['ir.sequence'].with_company(company_id).next_by_code('custom.purchase.requisition',
                                                                                        requested_date) or '/'
                vals['name'] = new_seq
        return super(PurchaseRequisition, self).create(vals_list)

    def review_requisition(self):
        self.ensure_one()
        if all(line.po_quantity > 0 for line in self.line_ids):
            raise ValidationError("PO generated For Purchase Requisition. You can't Review this Requisition.")
        return {
            'type': 'ir.actions.act_window',
            'name': _('REQ Review'),
            'res_model': 'req.review.wizard',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'context': {
                'requisition_id': self.id,
            },
        }

    @api.depends('line_ids')
    def _compute_total_amount(self):
        for record in self:
            total = sum(line.subtotal for line in record.line_ids)
            record.total_amount = total

    def action_approval_cancel(self):
        for records in self:
            if records.state == 'done':
                raise ValidationError("You cannot cancel Approval Data in 'Done' stage")
            records.state = 'cancel'
            for records in records.line_ids:
                records.state = 'cancel'

    def confirm_requisition(self):
        for requisition in self:
            requisition.ensure_one()

            if requisition.state != 'draft':
                raise UserError(_('Only Draft requisitions can be confirmed.'))

            for line in requisition.line_ids:
                if line.price_unit <= 0:
                    raise ValidationError(
                        _('Unit Price must be greater than 0 for product: %s')
                        % (line.product_id.display_name or 'Unknown Product')
                    )

            # 3️⃣ Approval config must exist
            if not requisition.approval_config_id:
                raise ValidationError(
                    _('Approval Configuration is missing. Please set Approval TOA.')
                )

            # 4️⃣ Get FIRST approval stage (MAIN THING)
            first_stage = self.env['approval.line'].first_stage(
                requisition.approval_config_id.id
            )

            if not first_stage or not first_stage.user_ids:
                raise ValidationError(
                    _('First approval stage has no approvers assigned.')
                )

            # 5️⃣ Set state & stage
            requisition.stage_id = first_stage.id
            requisition.state = 'approval_pending'

            # 6️⃣ Send email to FIRST approvers
            requisition.action_send_email(next_stage=first_stage)

        return True

    def get_record_url(self):
        """Prepare current item url."""
        # Retrieve the base URL
        base_url = request.httprequest.host_url

        # Define your parameters
        record_id = self.id
        model_name = self._name
        # Replace with the actual menu and action IDs for your case+
        menu_id = 322  # Example menu_id

        # Construct URL
        params = {
            'id': record_id,
            'model': model_name,
            'view_type': 'form',
            'menu_id': menu_id
        }
        query_string = parse.urlencode(params)
        record_url = f"{base_url}web?#" + query_string

        return record_url

    def action_send_email(self, next_stage, initiator=None):
        """Send mail to Next approver with RFQ Item visit link"""
        self.ensure_one()
        state = self.env.context.get('state')
        template = self.env.ref('custom_purchase_requisition.requisition_send_mail_template')
        # prepare current website url
        current_url = self.get_record_url()
        if not template:
            raise UserError("Email template not found!")

        approval_config = self.approval_config_id
        if not approval_config:
            raise ValidationError(_("No Approval Data Added to Approval Config. Please Add Data to Proceed."))
        if initiator:
            approval_user_emails = [email_list.email for email_list in initiator]
        else:
            approval_user_emails = [email_list.email for email_list in next_stage.user_ids]
        template.send_mail(
            self.id,
            email_values={
                'email_to': ','.join(approval_user_emails),
                'email_from': self.env.user.email if self.env.user.email else self.company_id.email,
                'subject': "Purchase Requisition approval mail",
                'body_html': Markup(
                    f"""Dear Sir / Madam,  
                            <p>
                                A Requisition is waiting ({'Done' if state else next_stage.name}) for your approval</br> 
                                Please click on the link below to see the requisition. </br>
                                <a target="_blank" href='{current_url}'>REQ Link</a>
                            </p>
                        """
                ),
            }, force_send=True,
        )

    def approve_requisition(self):

        # Continue with other validations
        for record in self:
            if record.state != 'approval_pending':
                raise ValidationError(_(f"{record.name} you need to Select Approval Pending item."))
            if record.approval_config_id.id != self[0].approval_config_id.id:
                raise ValidationError(_(f"{record.name} you need to select same Approval TOA."))

            if not record.line_ids:
                raise ValidationError(
                    _("No products added to the requisition %s. Please add products to proceed.") % record.name)

            # Validation: Check if the approval config exists based on approval_type and approval_subtype
            approval_config = record.approval_config_id
            if not approval_config:
                raise ValidationError(_("No Approval Data Added to Approval Config. Please Add Data to Proceed."))

            current_stage_sequence = record.stage_id.sequence

            # Find the next stage based on the current stage's sequence
            next_stage = self.env['approval.line'].sudo().search(
                [
                    ('config_id', '=', approval_config.id),
                    ('sequence', '>', current_stage_sequence),
                ],
                order='sequence asc',  # Ensure it's ascending to get the immediate next stage
                limit=1
            )

            # Log to generic approval history
            record._log_history(
                action_type='authorized',
                stage_id=record.stage_id.id,
                to_stage_id=next_stage.id if next_stage else False,
                note=_("Approved by %s") % self.env.user.name
            )

            if next_stage and self.env.user in record.stage_id.user_ids:
                # Check if the next stage is the final stage

                # If the next stage is the final stage, mark the requisition as done
                record.write({'stage_id': next_stage.id, 'state': 'approval_pending'})
                record.line_ids.state = 'approval_pending'

                # send mail to next approver
                # if next_stage.is_email_send:
                #     record.action_send_email(next_stage)
                # if record.initiator and next_stage:
                #     record.action_send_email(next_stage, record.initiator)

            elif next_stage and self.env.user not in next_stage.user_ids:
                raise UserError("You are not allowed to approve this stage.")
            elif record.state == 'approval_pending':
                # delivery_line_ids = self.env['purchase.requisition.delivery.schedule'].search(
                #     [('requisition_id.id', '=', record.id)]
                # )
                # for line in delivery_line_ids:
                #     line.assigned_date = datetime.today().date()

                record.write({'state': 'done'})
                record.line_ids.state = 'done'

            else:
                # If no next stage, raise an error (this should technically not happen)
                raise ValidationError(_("No Approval Remaining"))

    def action_open_purchase_order_form(self):
        self.ensure_one()

        if self.state != 'done':
            raise ValidationError(_("You can open Purchase Order only from an approved requisition."))


        if not self.line_ids:
            raise ValidationError(_("No requisition lines found."))

        order_line_vals = []
        for line in self.line_ids:
            remaining_qty = line.product_uom_qty - line.po_quantity
            if remaining_qty <= 0:
                continue

            order_line_vals.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.specification or line.product_id.display_name,
                'product_qty': remaining_qty,
                'product_uom_id': line.uom_id.id or line.product_id.uom_po_id.id,
                'price_unit': line.price_unit or 0.0,
                'date_planned': fields.Datetime.now(),
                'requisition_line_id': line.id,
                'size':line.size,
                'pr':line.pr,
                'pattern':line.pattern,
                'hs_code': line.hs_code,
            }))

        if not order_line_vals:
            raise ValidationError(_("No remaining quantity available to create Purchase Order."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                # 'default_partner_id': self.vendor_id.id,
                'default_origin': self.name,
                'default_company_id': self.company_id.id,
                'default_order_line': order_line_vals,
            },
        }

class PurchaseRequisitionLine(models.Model):
    _name = 'custom.purchase.requisition.line'
    _description = 'Purchase Requisition Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    requisition_id = fields.Many2one(
        comodel_name='custom.purchase.requisition',
        string="Order Reference",
        required=True,
        ondelete='restrict',
        index=True,
        copy=False
    )
    is_processed = fields.Boolean(
        string="Processed",
        default=False
    )
    serial_no = fields.Char(string='SR No', copy=False,default="New")

    selected = fields.Boolean(
        string='Selected'
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=True,
        ondelete='restrict'
    )
    specification = fields.Text(
        string='Specification', required=True
    )
    stage_id = fields.Many2one(
        "approval.line",
        "Approval Stage",
        related="requisition_id.stage_id",
        copy=False,
        tracking=True,
    )

    product_cat_id = fields.Many2one(
        'product.category',
        string='Product Category',
        # compute='_product_cat_get',
        copy=False,
        tracking=True,
        store=True
    )
    product_uom_qty = fields.Float(
        string='Quantity',
        default=1,
        required=True
    )

    pro_state = fields.Boolean(string="Process", default=False, copy=False)


    price_unit = fields.Float(
        string='Unit Price',
        compute='_compute_price_unit',
        store=True
    )
    size = fields.Char(string="Size")
    pr = fields.Char(string="PR")
    pattern = fields.Char(string="Pattern")
    hs_code = fields.Char(string="HS Code")

    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        required=True,  # Only show UoMs under the product's UoM category
    )
    responsible_person = fields.Many2one(
        "hr.employee",
        string="Responsible Person"
    )
    last_po_id = fields.Many2one(
        'purchase.order',
        string="Last Purchase Order",
        compute="_compute_last_po_data",
        store=True,
        readonly=True
    )

    last_po_line_id = fields.Many2one(
        'purchase.order.line',
        string="Last Purchase Order Line",
        compute="_compute_last_po_data",
        store=True,
        readonly=False
    )
    last_po_vendor = fields.Many2one('res.partner', string="Last Po Vendor", compute='_compute_last_po_vendor',
                                     store=True)
    last_po_qty = fields.Float(string="Last PO QTY",
                               compute='_compute_last_po_data',
                               store=True,
                               readonly=False)

    last_price_unit = fields.Float(
        string="Last PO Price",
        compute='_compute_last_po_data',
        store=True,
        readonly=False
    )

    @api.depends('last_po_id')
    def _compute_last_po_vendor(self):
        for rec in self:
            rec.last_po_vendor = rec.last_po_id.partner_id if rec.last_po_id else False

    @api.onchange('product_id')
    def _load_product_data(self):
        for rec in self:
            tmpl = rec.product_id.product_tmpl_id
            rec.update({
                'size': tmpl.size,
                'pr': tmpl.pr,
                'pattern': tmpl.pattern,
                'hs_code': tmpl.hs_code,
                'uom_id': tmpl.uom_id,
            })



    @api.depends('last_price_unit')
    def _compute_price_unit(self):
        for rec in self:
            if rec.last_price_unit and rec.last_price_unit > 0:
                rec.price_unit = rec.last_price_unit
            else:
                rec.price_unit = rec.price_unit

    subtotal = fields.Float(
        string='Approximate Cost',
        compute='_compute_subtotal',
        store=True
    )

    remarks = fields.Text(
        string='Remarks',
        translate=True
    )
    state = fields.Selection([
        ('draft', "Draft"),
        ('approval_pending', "Approval Pending"),
        ('done', "Approved"),
        ('sent_back', 'Sent Back'),
        ('cancel', "cancel"),
    ], default='draft', string="State", tracking=True, required=True, readonly=True
    )

    purchase_order_line_ids = fields.One2many(
        comodel_name='purchase.order.line',
        inverse_name='requisition_line_id',
        string='Purchase Order Line'
    )

    po_remaining_qty = fields.Float(
        string='PO Remaining Qty',
        compute='_compute_po_remaining_qty',
        store=True,
    )
    po_rec_qty = fields.Float(
        string='PO Received Qty',
        compute='compute_po_line_product_qty',
        store=True
    )

    rfq_product_qty = fields.Float(
        string='RFQ Product Qty', default=0.0
    )

    po_quantity = fields.Float(
        string='Ordered Quantity',
        compute='_compute_total_po_quantity',
        store=True,
    )
    po_remaining_qty = fields.Float(
        string='PO Remaining Qty',
        compute='_compute_po_remaining_qty',
        store=True,
    )

    stock_qty = fields.Float(string='Current Stock', compute='get_stock_qty', store=True)
    prod_current_stock = fields.Float(string="Present Stock", related="product_id.qty_available", store=True)

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        compute='_compute_company_id',
        # inverse='_inverse_company_id',
        store=True
    )
    concern_dept = fields.Many2one(
        related='requisition_id.concern_dept',
        store=True,
        readonly=False
    )
    requesting_dept = fields.Many2one(
        related='requisition_id.requesting_dept',
        store=True,
        readonly=False
    )
    purchase_type = fields.Selection(
        related='requisition_id.purchase_type',
        store=True,
        readonly=False
    )
    last_line_serial = fields.Integer(string="Last Line Serial", default=0)

    # product_domain_ids = fields.Binary(compute='_compute_product_domain_ids')


    @api.onchange('product_cat_id')
    def _onchange_product_cat_id_reset_product(self):
        for rec in self:
            # Clear selected product when category changes
            rec.product_id = False

    @api.depends('product_uom_qty', 'po_quantity')
    def _compute_po_remaining_qty(self):
        for rec in self:
            rec.po_remaining_qty = rec.product_uom_qty - rec.po_quantity





    @api.constrains('product_id')
    def _check_product_category(self):
        """Also enforce on save (for imports, etc.)."""
        for line in self:
            if line.requisition_id.product_cat_id and line.product_id.categ_id != line.requisition_id.product_cat_id:
                raise ValidationError(
                    f"Product '{line.product_id.display_name}' must belong to "
                    f"category '{line.requisition_id.product_cat_id.display_name}'."
                )

    @api.depends('product_id')
    def _compute_last_po_data(self):
        """
        Get the last approved PO line for the product
        based on purchase.order.date_approve.
        """
        for rec in self:
            if not rec.product_id:
                rec.last_po_id = False
                rec.last_po_line_id = False
                rec.last_price_unit = 0.0
                rec.last_po_qty = 0.0
                continue

            # Search PO lines by product
            po_lines = self.env['purchase.order.line'].search(
                [
                    ('product_id', '=', rec.product_id.id),
                    ('order_id.state', 'in', ['purchase', 'done']),
                    ('order_id.date_approve', '!=', False),
                ],
                limit=1,
                order='id desc'  # fallback ordering
            )

            # Sort them in Python by order_id.date_approve
            last_po_line = sorted(
                po_lines,
                key=lambda l: l.order_id.date_approve or fields.Datetime.from_string("1970-01-01"),
                reverse=True
            )[:1]

            last_po_line = last_po_line[0] if last_po_line else False

            if last_po_line:
                rec.last_po_id = last_po_line.order_id.id
                rec.last_po_line_id = last_po_line.id
                rec.last_price_unit = last_po_line.price_unit
                rec.last_po_qty = last_po_line.product_qty
            else:
                rec.last_po_id = False
                rec.last_po_line_id = False
                rec.last_price_unit = 0.0
                rec.last_po_qty = 0.0

    @api.depends('requisition_id.company_id')
    def _compute_company_id(self):
        for line in self:
            if line.requisition_id:
                line.company_id = line.requisition_id.company_id
            else:
                line.company_id = False

    @api.depends('product_id', 'product_uom_qty')
    def get_stock_qty(self):
        """Get Product total stock from all warehouses and locations"""
        for rec in self:
            rec.stock_qty = 0.0

            if not rec.product_id:
                continue

            quants = self.env['stock.quant'].sudo().read_group(
                [('product_id', '=', rec.product_id.id)],
                ['quantity:sum'],
                []
            )

            rec.stock_qty = quants[0]['quantity'] if quants else 0.0

    def unlink(self):
        for record in self:
            if record.requisition_id.state != 'draft':
                raise UserError(_("You cannot delete a record that is not in draft state."))
        return super(PurchaseRequisitionLine, self).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Generate serial_no like <requisition_reference>-001, -002, etc.
        Works even for multi-record creation with the same requisition.
        """
        # Group records by requisition_id for bulk numbering
        requisition_groups = {}
        for vals in vals_list:
            requisition_id = vals.get('requisition_id')
            if not requisition_id:
                raise ValidationError(_("Requisition reference is missing."))
            requisition_groups.setdefault(requisition_id, []).append(vals)

        for requisition_id, records in requisition_groups.items():
            # Browse the requisition to get its name/reference
            requisition = self.env['custom.purchase.requisition'].browse(requisition_id)
            if not requisition.exists():
                raise ValidationError(_("Requisition not found."))

            # Find the last number already used for this requisition
            existing_lines = self.env['custom.purchase.requisition.line'].search(
                [('requisition_id', '=', requisition_id)],
                order='id desc',
                limit=1
            )
            last_number = 0
            if existing_lines and existing_lines.serial_no:
                # Extract the last numeric part if it exists (e.g. "PR-00035-005" → 5)
                try:
                    # Split by hyphen and get the last part
                    last_part = existing_lines.serial_no.split('-')[-1]
                    last_number = int(last_part)
                except (ValueError, IndexError):
                    last_number = 0

            # Assign serial numbers incrementally
            for i, vals in enumerate(records, start=1):
                if vals.get('serial_no', _('New')) == _('New'):
                    next_number = last_number + i
                    # Format the serial number with leading zeros
                    vals['serial_no'] = f"{requisition.name}-{next_number:03d}"

        return super(PurchaseRequisitionLine, self).create(vals_list)

    @api.depends('purchase_order_line_ids.product_qty', 'purchase_order_line_ids.state')
    def _compute_total_po_quantity(self):
        """
        Compute the total quantity ordered for this requisition line.
        """
        for line in self:
            total_qty = sum(
                order_line.product_qty for order_line in line.purchase_order_line_ids if
                order_line.state != 'cancel' and order_line.product_id.id == line.product_id.id)
            line.po_quantity = total_qty

    @api.depends('purchase_order_line_ids.qty_received', 'purchase_order_line_ids.product_qty')
    def compute_po_line_product_qty(self):
        for rec in self:
            rec.po_rec_qty = sum(
                line.qty_received for line in rec.purchase_order_line_ids if line.product_id.id == rec.product_id.id
            )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"Record - {rec.id}"


    @api.depends('product_uom_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_uom_qty * line.price_unit

    @api.depends('product_uom_qty', 'po_quantity')
    def _compute_po_remaining_qty(self):
        for rec in self:
            rec.po_remaining_qty = rec.product_uom_qty - rec.po_quantity

