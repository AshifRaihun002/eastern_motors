# -*- coding: utf-8 -*-
{
    'name': "Dynamic Approval System",

    'summary': "This module is for managing all kinds of dynamic approval system.",

    'description': """
Long description of module's purpose
    """,

    'author': "MISL",
    'website': "https://www.mirinfosys.com",

    'category': 'Uncategorized',
    'version': '19.0.1.1.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'portal'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/approval_multi_company_security_groups.xml',

        'views/approval_view.xml',
        'views/approval_history_views.xml',

        'wizard/send_back_wizard_views.xml',
    ],
    'license': 'LGPL-3',
}

