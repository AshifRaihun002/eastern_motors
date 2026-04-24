from odoo import fields, models, api
from odoo.exceptions import ValidationError


class CustomSalesCommissionPolicy(models.Model):
    _name = 'custom.sales.commission.policy.head'
    _description = 'Custom Commission Policy'

    name = fields.Char(string='Name')
    policy_type = fields.Selection([
        ('on_qty', 'Quantity'),
        ('on_amount', 'Amount'),
    ])

    qty_lines = fields.One2many("custom.commission.qty.line", "head_id")
    amount_lines = fields.One2many("custom.commission.amount.line", "head_id")


class CustomCommissionQuantityLine(models.Model):
    _name = 'custom.commission.qty.line'
    _description = 'Custom Commission Quantity Line'

    sequence = fields.Integer(string='Sequence')
    from_qty = fields.Integer(string='From Qty')
    to_qty = fields.Integer(string='To Qty')
    commission_percentage = fields.Float(string='Commission Percentage (%)')

    head_id = fields.Many2one('custom.sales.commission.policy.head')

    def _check_overlap(self, from_qty, to_qty, head_id, exclude_id=None):
        """
        Check if the given range overlaps with any existing line
        under the same head, optionally excluding a specific record
        (used during write to exclude the record being updated).

        Two ranges overlap if:
            new.from_qty <= existing.to_qty
            AND
            new.to_qty >= existing.from_qty
        """
        domain = [
            ('head_id', '=', head_id),
            ('from_qty', '<=', to_qty),
            ('to_qty', '>=', from_qty),
        ]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        overlapping = self.search(domain)
        if overlapping:
            overlap_info = ', '.join(
                f"{line.from_qty} - {line.to_qty}"
                for line in overlapping
            )
            raise ValidationError(
                f"Quantity range {from_qty} - {to_qty} overlaps with "
                f"existing range(s): {overlap_info}"
            )

    def _validate_range(self, from_qty, to_qty):
        """Check that from_qty is less than to_qty."""
        if from_qty >= to_qty:
            raise ValidationError(
                f"'From Qty' ({from_qty}) must be less than 'To Qty' ({to_qty})."
            )
        if from_qty < 0 or to_qty < 0:
            raise ValidationError("From and To Quantity cannot be negative.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            from_qty = vals.get('from_qty', 0)
            to_qty = vals.get('to_qty', 0)
            head_id = vals.get('head_id')
            self._validate_range(from_qty, to_qty)
            self._check_overlap(from_qty, to_qty, head_id)
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            from_qty = vals.get('from_qty', record.from_qty)
            to_qty = vals.get('to_qty', record.to_qty)
            head_id = vals.get('head_id', record.head_id.id)
            self._validate_range(from_qty, to_qty)
            # exclude current record so it doesn't flag itself as an overlap
            self._check_overlap(from_qty, to_qty, head_id, exclude_id=record.id)
        return super().write(vals)


class CustomCommissionAmountLine(models.Model):
    _name = 'custom.commission.amount.line'
    _description = 'Custom Commission Amount Line'

    sequence = fields.Integer(string='Sequence')
    from_amount = fields.Float(string='From Amount')
    to_amount = fields.Float(string='To Amount')
    commission_percentage = fields.Float(string='Commission Percentage')

    head_id = fields.Many2one('custom.sales.commission.policy.head')

    def _check_overlap(self, from_amount, to_amount, head_id, exclude_id=None):
        domain = [
            ('head_id', '=', head_id),
            ('from_amount', '<=', to_amount),
            ('to_amount', '>=', from_amount),
        ]

        if exclude_id:
            domain.append(('id', '!=', exclude_id))

        overlapping = self.search(domain)

        if overlapping:
            overlap_info = ', '.join(
                f"{line.from_amount} - {line.to_amount}"
                for line in overlapping
            )
            raise ValidationError(
                f"Quantity range {from_amount} - {to_amount} overlaps with "
                f"existing range(s): {overlap_info}"
            )


    def _validate_range(self, from_amount, to_amount):
        if from_amount > to_amount:
            raise ValidationError("From Amount cannot be greater than To Amount")

        if from_amount < 0 or to_amount < 0:
            raise ValidationError("From and To Amount cannot be negative.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            from_amount = vals.get('from_amount', 0)
            to_amount = vals.get('to_amount', 0)
            head_id = vals.get('head_id')
            self._validate_range(from_amount, to_amount)
            self._check_overlap(from_amount, to_amount, head_id)
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            from_amount = vals.get('from_amount', record.from_amount)
            to_amount = vals.get('to_amount', record.to_amount)
            head_id = vals.get('head_id', record.head_id.id)
            self._validate_range(from_amount, to_amount)
            # exclude current record so it doesn't flag itself as an overlap
            self._check_overlap(from_amount, to_amount, head_id, exclude_id=record.id)
        return super().write(vals)
