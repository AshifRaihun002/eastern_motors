{
    'name': 'Custom Product',

    'version': '19.0.1.1.3',

    'category': 'Product',
    'sequence': 1,
    'summary': 'Product Custom filed',
    'description': """Manage your Product.""",
    'author': 'Mir InfoSys',
    'depends': [
        'base', 'mail', 'stock', 'accountant','product','purchase',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/custom_product_view.xml',
        'views/product_inherited_view.xml',


    ],
    'application': True,
    'license': 'LGPL-3',
}