# -*- coding: utf-8 -*-
{
    'name': "Mir Inter Company Stock Transfer",

    'summary': "Mir Inter Company Stock Transfer Module",

    'description': """ """,

    'author': "MISL",

    'category': 'Uncategorized',
    'version': '19.0.0.2',
    'license': 'LGPL-3',

    'depends': ['base', 'mail', 'stock', 'account', 'uom', 'account_asset','custom_purchase_requisition'],

    'data': [
        'data/sequence.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'views/inter_company_transfer_view.xml',
    ],
}
