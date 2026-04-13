{
    "name": "Portal Sale Order Create",
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Allow portal users to create sales quotations from portal",
    "depends": ["sale_management", "portal", "website", "custom_sales_order"],
    "data": [
        "views/portal_sale_order_templates.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "icon": "/portal_sales_order/static/description/icon.png",
}
