# 🧩 Child Tracking Mixin for Odoo 18

## 📘 Overview

The **ChildTrackingMixin** is a reusable abstract model designed to **automatically log field changes** made in child records and post them as messages in the **parent record’s chatter**.

Whenever a tracked field (`tracking=True`) in a child model is created or modified, the mixin:

* Detects which fields changed.
* Retrieves old and new values.
* Posts a message to the parent record (using `message_post`).
* Optionally logs to the server log if no parent chatter is available.

---

## ⚙️ How It Works

The mixin hooks into Odoo’s `create()` and `write()` methods.

1. **On `create()`**

   * It tracks all fields with `tracking=True` in the child model.
   * Posts a message to the parent record with the new field values.

2. **On `write()`**

   * It compares the old and new values of tracked fields.
   * If any tracked field changes, it posts a summary message to the parent chatter showing what changed.

3. **Parent Relationship**

   * The child model must define `_parent_tracking_field` (the field name linking to the parent).
   * Example: `_parent_tracking_field = 'order_id'`

---

## 🧰 Example Implementation

### 1️⃣ Define your mixin (already done)

```python
# models/mixins/child_tracking_mixin.py
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class ChildTrackingMixin(models.AbstractModel):
    _name = 'child.tracking.mixin'
    _description = 'Child Change Tracking Mixin'
    _parent_tracking_field = None

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            rec._track_child_changes('create', vals)
        return records

    def write(self, vals):
        for rec in self:
            old_vals = {f: rec[f] for f in vals.keys() if f in rec._fields}
            res = super(ChildTrackingMixin, rec).write(vals)
            rec._track_child_changes('write', vals, old_vals)
        return res

    def _track_child_changes(self, operation, vals, old_vals=None):
        tracked_fields = [
            name for name, field in self._fields.items()
            if getattr(field, 'tracking', False)
        ]
        changed_fields = [f for f in vals if f in tracked_fields]
        if not changed_fields:
            return

        for field_name in changed_fields:
            old_val = old_vals.get(field_name) if old_vals else None
            new_val = vals[field_name]
            self._notify_parent_change(field_name, old_val, new_val, operation)

    def _notify_parent_change(self, field_name, old_val, new_val, operation):
        parent_field_name = getattr(self, '_parent_tracking_field', None)
        if not parent_field_name or parent_field_name not in self._fields:
            _logger.warning(f"[ChildTracking] No parent field defined for {self._name}")
            return

        parent = getattr(self, parent_field_name)
        if not parent:
            _logger.warning(f"[ChildTracking] No parent record found for {self._name}")
            return

        # Create message
        field_label = self._fields[field_name].string or field_name
        if operation == 'create':
            msg = f"{self._description}: Field '{field_label}' created → {new_val or '-'}"
        else:
            msg = f"{self._description}: Field '{field_label}' updated → {old_val or '-'} → {new_val or '-'}"

        # Post to parent chatter
        if hasattr(parent, 'message_post'):
            parent.message_post(body=msg)
        else:
            _logger.info(f"[ChildTracking] {parent._name} → {msg}")
```

---

### 2️⃣ Use it in your child model

```python
from odoo import models, fields
from .mixins.child_tracking_mixin import ChildTrackingMixin

class IndentLine(models.Model):
    _name = 'indent.line'
    _description = 'Indent Line'
    _inherit = ['child.tracking.mixin']

    _parent_tracking_field = 'indent_id'  # The parent model relation

    indent_id = fields.Many2one('indent.process', string='Indent', required=True)
    product_id = fields.Many2one('product.product', string='Product', tracking=True)
    quantity = fields.Float(string='Quantity', tracking=True)
    unit_price = fields.Float(string='Unit Price', tracking=True)
```

---

### 3️⃣ Ensure parent has chatter support

Your **parent model** (e.g., `indent.process`) should inherit from:

```python
_inherit = ['mail.thread', 'mail.activity.mixin']
```

That allows `message_post()` to log tracked changes in the chatter.

Example:

```python
class IndentProcess(models.Model):
    _name = 'indent.process'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Indent Process'

    name = fields.Char(string='Indent Reference', required=True)
    line_ids = fields.One2many('indent.line', 'indent_id', string='Indent Lines')
```

---

## 🧾 Example Log Message in Parent Chatter

When you change a field in `Indent Line`, the parent `Indent Process` chatter will show:

```
Indent Line: Field 'Quantity' updated → 7.0 → 5.0
Indent Line: Field 'Unit Price' updated → 1500 → 1800
```

Or, on creation:

```
Indent Line: Field 'Quantity' created → 10
```

---

## ⚠️ Notes and Best Practices

✅ **Do**

* Set `_parent_tracking_field` in every child model.
* Use `tracking=True` only on fields you actually want logged.
* Make sure parent model inherits from `mail.thread`.

❌ **Don’t**

* Use `tracking=True` on `Html`, `Binary`, or `Text` fields (Odoo doesn’t support tracking on those types).
* Expect chatter messages if the parent doesn’t have chatter mixins.
* Expect multi-record create/write to combine messages — currently each record logs separately.

---

## 🧪 Optional Enhancements

You can extend this mixin to:

* Combine **all field changes** into **a single message**.
* Support **delete tracking** (`unlink()` override).
* Use **human-readable values** for selection fields.
