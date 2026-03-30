Approval Workflow - History Logging & Send Back Wizard
===========================================================

This module provides reusable **Approval History tracking** and a **Send Back Wizard**
for any Odoo model that follows an approval process. It is designed for Odoo 18
and can be easily extended to Procurement, Comparative Statements, Purchase Orders,
Expense Claims, and other approval-based models.

Key Features
============

* Approval History tab for every record
* Logs actions: *create*, *authorized*, *sent_back*, *review*
* Send Back Wizard with note capture
* Reusable `_log_history` method for developers
* Works across multiple models with minimal configuration
* Audit-ready (read-only history records)

Usage
=====

**For End Users:**
------------------
1. Open a record (e.g., Indent Process).
2. Approve or use the **Send Back** button.
3. Enter a note in the wizard if sending back.
4. Track all actions in the **Approval History** tab.

**For Functional Consultants/Admins:**
--------------------------------------
1. Configure Approval Config and Stages in *Settings → Approvals*.
2. Assign users to the correct stages.
3. Add the Approval History tab to your form views if not already included.
4. Enable the **Send Back** button where necessary.

**For Developers:**
-------------------
1. Inherit from `log.history.mixin` in your model::
```python
class PurchaseOrderCustom(models.Model):
    _name = "purchase.order.custom"
    _inherit = ["log.history.mixin"]

    stage_id = fields.Many2one(
        "approval.line", string="Approval Stage", copy=False, tracking=True,
        domain="[('config_id', '=', approval_config_id), ('config_id', '!=', False)]"
    )
    approval_history_ids = fields.One2many(
        'approval.history',
        'res_id',
        string="Approval History",
        domain=lambda self: [('res_model', '=', self._name), ('company_id', '=', self.company_id.id)],
    )
```
2. Use `_log_history()` in your methods to track actions::
```python
   self._log_history(
       action_type='authorized',
       note="Approved by %s" % self.env.user.name,
       stage_id=self.stage_id.id,
       to_stage_id=next_stage.id if next_stage else False,
   )
or
    records._log_history(
        action_type='cancel',
        stage_id=records.stage_id.id,
        note=_("Cancel by %s") % self.env.user.name
    )
```
3. Add the Send Back Wizard button::
```xml
    <button class="oe_highlight" name="approve_process" string="Approve" type="object"/>
    <button name="open_send_back_wizard" type="object" string="Send Back" class="btn-secondary"/>
```
4. Reuse the wizard in other models by passing context:
```python
    # You can use this method in any model that has an approval workflow
    'context': {
        'default_note': '',
        'active_id': self.id,
        'active_model': self._name,
        'action_type': 'sent_back',  # 'create', 'authorized', 'sent_back', 'review', 'cancel'
    }
```


```python
    def open_send_back_wizard(self):
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
```

```python
    def approve_process(self):
        """Approve Indent with stage flow and log history"""
        self.ensure_one()
        # Validation: Must have lines
        if not self.indent_line_ids:
            raise ValidationError(_("No Products Added to the Indent. Please Add Products to Proceed."))

        # Validation: Must have approval config
        if not self.approval_config_id:
            raise ValidationError(_("No Approval Config found. Please configure approval stages first."))

        current_stage_sequence = record.stage_id.sequence
        user_dept = self.env.user.employee_id.department_id

        if user_dept != self.requesting_department_id:
            raise UserError(_(
                "You are not allowed to approve this stage. "
                "Only the %s department can approve."
            ) % user_dept.name)

        # Find next stage
        next_stage = self.stage_id.get_next_stage(self.approval_config_id.id, current_stage_sequence, self.company_id.id)

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
            self.write({'stage_id': next_stage.id, 'state': 'draft'})  # Keep state draft until final stage
        else:
            self.write({'stage_id': self.stage_id.id, 'state': 'approved'})  # Final approval
```

Installation
============

1. Copy this module into your Odoo ``addons`` folder.
2. Update the app list:  
   ``Apps → Update Apps List``
3. Install the module **dynamic_approval_process**.

Dependencies
============
```python
'depends': ['base', 'portal'],
```

Changelog
=========

* **1.0.0** – Initial release with:
  - Approval History logging
  - Send Back Wizard
  - Reusable `_log_history` method

License
=======

LGPL-3.0 or later

