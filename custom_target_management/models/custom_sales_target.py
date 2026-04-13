import calendar
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

class CustomSalesTarget(models.Model):
    _name = "custom.sale.target.head"
    _description = "Custom Sales Target"

    name = fields.Char(string="Name")

    period = fields.Many2one(comodel_name='fiscal.year.config', string="Target Period")
    branch_id = fields.Many2one(comodel_name='res.company', string="Branch")

    from_period = fields.Date(related='period.from_date', string="From")
    to_period = fields.Date(related='period.to_date', string="To")

    branch_target_qty = fields.Integer(string="Branch Target Quantity", compute="_compute_target_qty_value")
    branch_target_value = fields.Float(string="Branch Target Value", compute="_compute_target_qty_value")

    dealer_target_qty = fields.Integer(string="Dealer Target Quantity", compute="_compute_target_qty_value")
    dealer_target_value = fields.Float(string="Dealer Target Value", compute="_compute_target_qty_value")

    total_target_qty = fields.Integer(string="Total Target Quantity", compute="_compute_target_qty_value")
    total_target_value = fields.Float(string="Total Target Value", compute="_compute_target_qty_value")

    commission_policy = fields.Many2one("custom.sales.commission.policy.head", string="Commission Policy")

    line_ids = fields.One2many(comodel_name='custom.sale.target.line', inverse_name='head_id', string="Target Lines")

    @api.onchange('branch_id', 'period')
    def _onchange_name(self):
        self.name = f"{self.branch_id.name or ''} {self.period.name or ''}".strip()

    @api.depends("line_ids")
    def _compute_target_qty_value(self):
        line_ids = self.line_ids
        branch_target_qty = 0
        branch_target_value = 0.0
        dealer_target_qty = 0
        dealer_target_value = 0.0
        for record in line_ids:
            if record.dealer_branch_id == record.branch_partner_id:
                branch_target_qty += record.target_qty
                branch_target_value += record.target_value
            else:
                dealer_target_qty += record.target_qty
                dealer_target_value += record.target_value

        self.branch_target_qty = branch_target_qty
        self.branch_target_value = branch_target_value
        self.dealer_target_qty = dealer_target_qty
        self.dealer_target_value = dealer_target_value

        self.total_target_qty = branch_target_qty + dealer_target_qty
        self.total_target_value = branch_target_value + dealer_target_value


    def action_distribute_all_lines(self):
        """Distribute quantity for all lines at once."""
        for record in self:
            record.line_ids.action_distribute_quantity()

    def action_generate_dealer_lines(self):
        product_group_ids = self.env["product.custom.group"].sudo().search([])
        dealer_ids = self.branch_id.partner_id.child_ids

        line_vals = []
        for dealer in dealer_ids:
            for product_group in product_group_ids:
                is_exist = self.line_ids.search([("dealer_branch_id", "=", dealer), ("product_group_id", "=", product_group.id), ("head_id", "=", self.id)])
                if is_exist:
                    continue
                line_vals.append({
                    "head_id": self.id,
                    "dealer_branch_id": dealer.id,
                    "salesperson_id": dealer.user_id if dealer.user_id else None,
                    "product_group_id": product_group.id
                })

        if line_vals:
            new_lines = self.env["custom.sale.target.line"].create(line_vals)
            new_lines.action_distribute_quantity()


    def action_generate_branch_lines(self):
        product_group_ids = self.env["product.custom.group"].sudo().search([])
        branch_id = self.branch_id.partner_id

        line_vals = []

        for product_group in product_group_ids:
            is_exist = self.line_ids.search([("product_group_id", "=", product_group.id), ("dealer_branch_id", "=", branch_id.id), ("head_id", "=", self.id)])

            if is_exist:
                continue

            line_vals.append({
                "head_id": self.id,
                "dealer_branch_id": branch_id.id,
                "product_group_id": product_group.id
            })

        if line_vals:
            new_lines = self.env["custom.sale.target.line"].create(line_vals)
            new_lines.action_distribute_quantity()


    def open_set_target_wizard(self):
        self.ensure_one()
        dealer_ids = self.branch_id.partner_id.child_ids
        return {
            "name": "Set Targets",
            "type": "ir.actions.act_window",
            "res_model": "set.target.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_dealer_ids": dealer_ids.ids,
                "default_branch_partner_id": self.branch_id.partner_id.id,
                "active_id": self.id,
                "active_model": self._name,
            }
        }

class CustomSalesTargetLine(models.Model):
    _name = "custom.sale.target.line"
    _description = "Sales Target Line"

    head_id = fields.Many2one(comodel_name='custom.sale.target.head', string="Target", ondelete="cascade")

    branch_partner_id = fields.Many2one(
        comodel_name='res.partner',
        related='head_id.branch_id.partner_id',
        store=False,
    )

    dealer_branch_id = fields.Many2one(comodel_name='res.partner', string="Dealer", domain="['|', ('id', '=', branch_partner_id), '&', ('is_company', '=', False), ('customer_rank', '=', 0)]")
    salesperson_id = fields.Many2one(comodel_name='res.users', related='dealer_branch_id.user_id')

    product_group_id = fields.Many2one(comodel_name='product.custom.group', string="Product Group")

    target_qty = fields.Integer(string="Target Quantity")
    target_value = fields.Float(string="Target Value")

    detail_line_ids = fields.One2many("custom.sale.target.detail", inverse_name='line_id', string="Target Line Details")

    def _generate_month_segments(self):
        """Generate date segments from head's from_period to to_period."""
        self.ensure_one()
        from_date = self.head_id.from_period
        to_date = self.head_id.to_period

        if not from_date or not to_date:
            return []

        segments = []
        current_start = from_date

        while current_start <= to_date:
            # Get last day of current month
            last_day_of_month = current_start.replace(
                day=calendar.monthrange(current_start.year, current_start.month)[1]
            )
            # If last day of month exceeds to_date, cap it
            current_end = min(last_day_of_month, to_date)
            segments.append((current_start, current_end))
            # Move to first day of next month
            current_start = (current_start.replace(day=1) + relativedelta(months=1))

        return segments

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._create_detail_lines()
        return records

    def _create_detail_lines(self):
        """Create detail lines with date ranges, no quantities yet."""
        self.ensure_one()
        # Clear existing detail lines before recreating
        self.detail_line_ids.unlink()
        segments = self._generate_month_segments()
        detail_vals = []
        for date_from, date_to in segments:
            detail_vals.append({
                'line_id': self.id,
                'date_from': date_from,
                'date_to': date_to,
                'target_qty': 0,
                'target_value': 0.0,
            })
        if detail_vals:
            self.env['custom.sale.target.detail'].create(detail_vals)

    def action_distribute_quantity(self):
        """Evenly distribute target_qty and target_value across detail lines."""
        for record in self:
            detail_lines = record.detail_line_ids
            count = len(detail_lines)
            if not count:
                continue

            qty_per_month = record.target_qty // count
            value_per_month = record.target_value / count

            # Handle remainder for quantity
            qty_remainder = record.target_qty % count

            for i, line in enumerate(detail_lines):
                # Add remainder to the first month
                extra = qty_remainder if i == 0 else 0
                line.write({
                    'target_qty': qty_per_month + extra,
                    'target_value': round(value_per_month, 2),
                })

    def action_open_detail_lines(self):
        self.ensure_one()
        return {
            'name': f'Details - {self.dealer_branch_id.name} / {self.product_group_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'custom.sale.target.line',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [
                (self.env.ref('custom_target_management.view_custom_sale_target_line_form').id, 'form'),
            ],
        }


class CustomSalesTargetDetail(models.Model):
    _name = "custom.sale.target.detail"
    _description = "Sales Target Details"

    line_id = fields.Many2one(comodel_name='custom.sale.target.line', string="Target Line", ondelete="cascade")

    month_year = fields.Date(string="Month/Year")
    target_qty = fields.Integer(string="Target Quantity")
    target_value = fields.Float(string="Target Value")

    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")



