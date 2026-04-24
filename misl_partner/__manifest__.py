# -*- coding: utf-8 -*-
{
    "name": "MISL Partner Modification",
    "summary": """
        This Module will extend the Partner Module of Odoo""",
    "description": """
        Any modification regarding Partner will be done in this module
    """,
    "author": "MISL",
    "website": "",
    "category": "Purchase",
    "version": "19.0.0.1",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "depends": ["base","account"],
    # always loaded
    "data": ["views/inherit_res_partner_views.xml"],
    "license": "LGPL-3",
}
