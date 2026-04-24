from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from datetime import datetime
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"
    _order = "id desc"

    state = fields.Selection(selection_add=[("actual", "Actual Cost Posted")])
    # cost_lines = fields.One2many(states={"actual": [("readonly", True)]})
    actual_account_move_id = fields.Many2one(
        "account.move", "Actual Cost Journal Entry", copy=False, readonly=True
    )
    actual_cost_val_date = fields.Datetime(
        string="Actual Cost Date", copy=False, store=True, readonly=True
    )
    show_add_cost_line = fields.Boolean(
        string="Show Populate Cost Line", compute="_compute_show_populate_cost_line"
    )

    lc_id = fields.Many2one('letter.credit', string='Letter of Credit')
    shipment_id = fields.Many2one('lc.shipment', string='LC Shipment Landed Cost')

    # date = fields.Date(
    #     states={"done": [("readonly", True)], "actual": [("readonly", True)]}
    # )
    # target_model = fields.Selection(
    #     states={"done": [("readonly", True)], "actual": [("readonly", True)]},
    # )
    # picking_ids = fields.Many2many(
    #     states={"done": [("readonly", True)], "actual": [("readonly", True)]},
    # )
    # account_journal_id = fields.Many2one(
    #     states={"done": [("readonly", True)], "actual": [("readonly", True)]},
    # )

    def _get_cost_templates(self):
        self.ensure_one()

        if not self.picking_ids:
            return []

        products = self.picking_ids.move_line_ids.product_id
        landed_cost_templates = self.env["landed.cost.template"].search(
            [
                ("product_id", "in", products.ids),
                "|",
                ("company_id", "=", self.company_id.id),
                ("company_id", "=", False),
            ],
            order="company_id asc",
        )

        return landed_cost_templates

    def button_validate(self):
        # First, call the original validation
        result = super(StockLandedCost, self).button_validate()

        # Then add your custom validation
        for cost in self:
            # Check if there are any pickings with purchase orders
            pickings_with_po = cost.picking_ids.filtered(lambda p: p.purchase_id)

            if pickings_with_po:
                # Get all unique purchase orders from the pickings
                purchase_orders = pickings_with_po.mapped('purchase_id')

                # Check if any purchase order doesn't have bills
                pos_without_bills = purchase_orders.filtered(lambda po: not po.invoice_ids)

                if pos_without_bills:
                    po_names = ", ".join(pos_without_bills.mapped('name'))
                    raise UserError(_(
                        'Cannot validate landed cost because the following purchase orders '
                        'do not have any bills/vendor bills:\n%s\n\n'
                        'Please create bills for these purchase orders first.'
                    ) % po_names)

        return result
    @api.depends("picking_ids")
    def _compute_show_populate_cost_line(self):
        for rec in self:
            rec.show_add_cost_line = (
                True if rec.state == "draft" and rec._get_cost_templates() else False
            )

    def _populate_cost_lines(self):
        self.ensure_one()
        cost_templates = self._get_cost_templates()

        if not cost_templates:
            _logger.warning("No landed cost templates found")
            return

        tmpl_dict = {}

        for tmpl in cost_templates:
            key = tmpl.product_id.id
            tmpl_dict[key] = tmpl_dict.get(key, False) or tmpl

        prod_dict = defaultdict(int)

        for move in self.picking_ids.move_line_ids:
            product_uom_qty = (
                move.qty_done
                if move.product_uom_id.id == move.product_id.uom_id.id
                else move.product_uom_id._compute_quantity(
                    move.qty_done, move.product_id.uom_id, rounding_method="HALF-UP"
                )
            )

            prod_dict[move.product_id.id] += product_uom_qty

        cost_lines = []

        for product, qty in prod_dict.items():
            tmpl = tmpl_dict.get(product)

            if tmpl:
                lines = [
                    (
                        0,
                        0,
                        {
                            "name": line.product_id.name or "",
                            "product_id": line.product_id.id,
                            "split_method": line.split_method or "equal",
                            "price_unit": qty * line.price_unit,
                            "account_id": line.account_id.id,
                        },
                    )

                    for line in tmpl.cost_lines
                ]
                cost_lines += lines
            else:
                _logger.warning(
                    f"Landed cost template not found for product_id: {product}, qty: {qty}"
                )

        self.cost_lines = [(5, 0, 0)]  # Clear old cost lines
        self.cost_lines = cost_lines

    def populate_cost_lines(self):
        for rec in self:
            rec._populate_cost_lines()

    def post_actual_cost(self):
        for rec in self:
            rec._post_actual_cost()

    def _post_actual_cost(self):
        self.ensure_one()

        if not self.cost_lines:
            return

        AccountMove = self.env["account.move"]
        actual_cost_date = fields.Datetime.now()

        vals = {
            "company_id": self.company_id.id,
            "journal_id": self.account_journal_id.id,
            "date": actual_cost_date,
            "ref": "Actual Cost - " + self.name,
        }
        account_move_id = AccountMove.create(vals)
        account_move_lines = []

        for line in self.cost_lines:
            cost_diff = line.price_unit_actual - line.price_unit
            product = line.product_id.product_tmpl_id
            accounts = product.get_product_accounts()

            pro_expense_account = accounts["expense"]
            probation_account = line.account_id or accounts["stock_input"]
            gain_loss_account = (
                    product.property_account_creditor_price_difference
                    or product.categ_id.property_account_creditor_price_difference_categ
            )

            if not (pro_expense_account and probation_account and gain_loss_account):
                raise UserError(
                    _(
                        "There is no account defined for the landed cost type.\n"
                        f"{'Expense Account' if not pro_expense_account else ''} "
                        f"{'Stock Input Account' if not probation_account else ''} "
                        f"{'Price Difference Account' if not gain_loss_account else ''}"
                    )
                )

            # Handling cost difference greater than zero
            if cost_diff > 0:
                account_move_lines += [
                    (
                        0,
                        0,
                        {
                            "credit": abs(line.price_unit_actual),
                            "account_id": pro_expense_account.id,
                            "move_id": account_move_id.id,
                            "debit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "debit": abs(line.price_unit),
                            "account_id": probation_account.id,
                            "move_id": account_move_id.id,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "debit": abs(cost_diff),
                            "account_id": gain_loss_account.id,
                            "move_id": account_move_id.id,
                            "credit": 0.0,
                        },
                    ),
                ]
            # Handling cost difference less than zero
            elif cost_diff < 0:
                account_move_lines += [
                    (
                        0,
                        0,
                        {
                            "credit": abs(line.price_unit_actual),
                            "account_id": pro_expense_account.id,
                            "move_id": account_move_id.id,
                            "debit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "credit": abs(cost_diff),
                            "account_id": gain_loss_account.id,
                            "move_id": account_move_id.id,
                            "debit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "debit": abs(line.price_unit),
                            "account_id": probation_account.id,
                            "move_id": account_move_id.id,
                            "credit": 0.0,
                        },
                    ),
                ]
            # Handling no cost difference
            else:
                account_move_lines += [
                    (
                        0,
                        0,
                        {
                            "credit": abs(line.price_unit_actual),
                            "account_id": pro_expense_account.id,
                            "move_id": account_move_id.id,
                            "debit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "debit": abs(line.price_unit),
                            "account_id": probation_account.id,
                            "move_id": account_move_id.id,
                            "credit": 0.0,
                        },
                    ),
                ]

        # Assigning the account move lines to the account move
        account_move_id.line_ids = account_move_lines
        account_move_id.action_post()

        # Updating the state to "actual" and adding relevant fields
        self.write(
            {
                "state": "actual",
                "actual_account_move_id": account_move_id.id,
                "actual_cost_val_date": actual_cost_date,
            }
        )
        self.message_post(body=_("Actual Cost Posted"))

    def action_view_journal_items(self):
        self.ensure_one()
        move_ids = []

        # Collecting the actual and standard account moves for the journal view
        if self.actual_account_move_id:
            move_ids.append(self.actual_account_move_id.id)

        if self.account_move_id:
            move_ids.append(self.account_move_id.id)

        return {
            "name": _("Journal Items"),
            "view_mode": "list,form",
            "res_model": "account.move.line",
            "type": "ir.actions.act_window",
            "domain": [("move_id", "in", move_ids)],
            "target": "current",
            "context": self.env.context,
        }



class InheritLandedCostLines(models.Model):
    _inherit = "stock.landed.cost.lines"

    price_unit_actual = fields.Float("Actual Cost", digits="Product Price")
    state = fields.Selection(related="cost_id.state", store=True)
    is_only_actual = fields.Boolean(
        "Is Only Actual",
        compute="_compute_is_only_actual",
        store=True,
        readonly=True,
        default=False,
        copy=False,
    )

    @api.depends("product_id", "price_unit", "state")
    def _compute_is_only_actual(self):
        for rec in self:
            # In Odoo 17, we keep the same logic but ensure proper handling of state
            rec.is_only_actual = rec.state == "done"
            # if rec.state == "done":
            #     rec.price_unit = 0.0