# -*- coding: utf-8 -*-
{
    'name': 'Indent Process for Product Transfer',
    'summary': 'Indent Process for Product Transfer',
    'description': 'Indent Process for Product Transfer from store to store other wise do Purchase Order by PR',
    'version': '19.0.1.1.1',
    'category': 'Purchase',
    'author': 'Ashif Raihan',
    'maintainer': 'Ashif Raihan',
    'license': 'OPL-1',
    'depends': ['base', 'mail', 'dynamic_approval_process', 'product', 'hr', 'stock', 'custom_purchase_requisition'],
    'data': [
        'data/index_process_seq.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/indent_process_view.xml',
        'views/res_stock_picking_view.xml',
        'views/res_stock_move_view.xml',
        'views/res_purchase_requisition_view.xml',
        'views/indent_transit_location_conf.xml',
    ],
    'installable': True,
    'application': True,
}
