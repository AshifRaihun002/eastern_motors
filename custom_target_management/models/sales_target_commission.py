import calendar
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

class SalesTargetCommission(models.Model):
    _name = "sale.target.commission.head"
    _description = "Sales Target & Commission"

    period = fields.Many2one(comodel_name='fiscal.year.config', string="Target Period")
    branch_id = fields.Many2one(comodel_name='res.company', string="Branch")

    from_period = fields.Date(related='period.from_date', string="From")
    to_period = fields.Date(related='period.to_date', string="To")

    branch_target_qty = fields.Integer(string="Branch Target Quantity")
    branch_target_value = fields.Float(string="Branch Target Value")

    dealer_target_qty = fields.Integer(string="Dealer Target Quantity")
    dealer_target_value = fields.Float(string="Dealer Target Value")

    total_target_qty = fields.Integer(string="Total Target Quantity")
    total_target_value = fields.Float(string="Total Target Value")

    line_ids = fields.One2many(comodel_name='sale.target.commission.line', inverse_name='head_id', string="Target Lines")

    def action_distribute_all_lines(self):
        """Distribute quantity for all lines at once."""
        for record in self:
            record.line_ids.action_distribute_quantity()

class SalesTargetCommissionLine(models.Model):
    _name = "sale.target.commission.line"
    _description = "Sales Target & Commission Line"

    head_id = fields.Many2one(comodel_name='sale.target.commission.head', string="Target")

    branch_partner_id = fields.Many2one(
        comodel_name='res.partner',
        related='head_id.branch_id.partner_id',
        store=False,
    )

    dealer_branch_id = fields.Many2one(comodel_name='res.partner', string="Dealer", domain="['|', ('id', '=', branch_partner_id), '&', ('is_company', '=', False), ('customer_rank', '=', 0)]")
    salesperson_id = fields.Many2one(comodel_name='res.users', related='dealer_branch_id.user_id')

    product_group_id = fields.Many2one(comodel_name='product.custom.group', string="Products")

    target_qty = fields.Integer(string="Target Quantity")
    target_value = fields.Float(string="Target Value")

    detail_line_ids = fields.One2many("sale.target.commission.detail", inverse_name='line_id', string="Target Line Details")

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
            self.env['sale.target.commission.detail'].create(detail_vals)

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
            'res_model': 'sale.target.commission.line',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [
                (self.env.ref('custom_target_management.view_sale_target_commission_line_form').id, 'form'),
            ],
        }


class SalesTargetCommissionDetail(models.Model):
    _name = "sale.target.commission.detail"
    _description = "Sales Target & Commission Details"

    line_id = fields.Many2one(comodel_name='sale.target.commission.line', string="Target Line")

    month_year = fields.Date(string="Month/Year")
    target_qty = fields.Integer(string="Target Quantity")
    target_value = fields.Float(string="Target Value")

    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")



