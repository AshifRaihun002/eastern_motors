# -*- coding: utf-8 -*-
{
    "name": "Sales Order Customer",
    "summary": """
    This Module will extend the Partner Module of Odoo""",
    "description": """
        Any modification regarding Partner will be done in this module
    """,
    "author": "Ashif",
    "website": "",
    "category": "Purchase",
    "version": "19.0.0.1",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "depends": ["base","account","sale_management"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/inherit_res_partner_views.xml",
        "views/inherit_sales_order_view.xml",
        "wizard/sale_send_back_wizard_view.xml",
    ],
    "license": "LGPL-3",
}
