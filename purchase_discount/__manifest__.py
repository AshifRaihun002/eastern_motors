{
    'name': 'Purchase Order Discount',
    'version': '19.0.1.0.1',
    'category': 'Purchases',
    'summary': 'Add discount functionality to purchase orders',
    'description': """
        This module allows users to apply discounts on purchase orders 
        either as fixed amount or percentage, with automatic distribution 
        to order lines.
    """,
    'author': 'MISL',
    'website': 'https://www.yourcompany.com',
    'depends': ["purchase","custom_purchase_requisition"],
    'data': [
        # 'security/ir.model.access.csv',
        'views/purchase_order_discount.xml',
        # 'views/direct_purchase_limit.xml',
        # 'views/po_line_limit_config.xml',
        # 'views/purchae_limit_for_direct_purchase.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}