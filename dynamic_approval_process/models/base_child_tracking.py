from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class ChildTrackingMixin(models.AbstractModel):
    _name = 'child.tracking.mixin'
    _description = 'Child Change Tracking Mixin'
    _parent_tracking_field = None  # Must be set in child model, e.g., 'parent_field_name'

    @api.model_create_multi
    def create(self, vals_list):
        """Capture initial values on creation."""
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            rec._track_child_changes('create', vals)
        return records

    def write(self, vals):
        """Detect and log changes on write."""
        for rec in self:
            old_vals = {f: rec[f] for f in vals.keys() if f in rec._fields}
            res = super(ChildTrackingMixin, rec).write(vals)
            rec._track_child_changes('write', vals, old_vals)
        return res

    def _track_child_changes(self, operation, vals, old_vals=None):
        """Handles actual tracking logic."""
        tracked_fields = [
            name for name, field in self._fields.items()
            if getattr(field, 'tracking', False)
        ]

        # filter only tracked fields in this operation
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
        if operation == 'create':
            msg = (
                f"{self._description}: Field '{self._fields[field_name].string}' changed ({operation.upper()}) "
                f"New: {new_val or '-'}"
            )
        elif operation == 'write':
            msg = (
                f"{self._description}: Field '{self._fields[field_name].string}' changed ({operation.upper()}) "
                f"Old: {old_val or '-'} → New: {new_val or '-'}"
            )

        if hasattr(parent, 'message_post'):
            parent.message_post(body=msg)
        else:
            _logger.info(f"[ChildTracking] {parent._name} → {msg}")
