{
    'name': 'Custom Product',

    'version': '19.0.1.1.1',

    'category': 'Product',
    'sequence': 1,
    'summary': 'Product Custom filed',
    'description': """Manage your Product.""",
    'author': 'Mir InfoSys',
    'depends': [
        'base', 'mail','product','purchase',
    ], #'stock', 'accountant',
    'data': [
        'security/ir.model.access.csv',
        'views/custom_product_view.xml',
        'views/product_inherited_view.xml',


    ],
    'application': True,
    'license': 'LGPL-3',
}