{
    'name': 'Purchase Requisition',
    'version': '19.0.1.1.1',

    'category': 'Purchase',
    'summary': ' Purchase Requisition in Odoo 19',
    'description': 'Purchase Requisition in Odoo 19',
    'sequence': '1',
    'author': 'Ashif Raihan',
    'maintainer': 'MISL',
    'license': 'LGPL-3',

    'depends': [
        'base', 'mail', 'account', 'account_accountant', 'stock', 'uom', 'hr', 'purchase_stock', 'hr', 'project',
        'purchase', 'account_budget', 'amount_to_word_bd', 'dynamic_approval_process', 'mass_mailing',
    ],

    'data': [
        'security/requisition_security.xml',
        'security/ir.model.access.csv',
        'data/purchase_requisition_email_template.xml',
        'views/custom_requisition_view.xml',
        'views/custom_pr_purchase_order.xml',
        'data/requisition_sequence_data.xml',

    ],

    # 'assets': {
    #     'web.assets_backend': [
    #         # 'brac_procurement/static/description/**/*',
    #         'brac_procurement/static/src/css/hight_light_require_fields.css',
    #         'brac_procurement/static/src/css/report_purchase_requisition.css',
    #         'brac_procurement/static/src/js/**/*',
    #     ],
    # },
}