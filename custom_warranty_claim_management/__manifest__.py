{
    "name": "Custom Warranty Claim Management",
    "version": "1.0.0",
    "category": "Custom",
    "author": "Mirinfo Systems Limited",
    "company": "Mirinfo Systems Limited",
    "maintainers": "Mirinfo Systems Limited",
    "website": "https://mirinfosys.com/",
    "sequence": 1,
    "depends": [
        "base",
        "portal",
        "sale",
        "account",
        "web",
        "dynamic_approval_process"
    ],
    "data": [
        "security/warranty_security.xml",
        "security/ir.model.access.csv",
        "security/warranty_record_rules.xml",
        "data/warranty_sequence.xml",
        "views/warranty_overview_views.xml",
        "views/warranty_claim_views.xml",
        "views/menu_views.xml",
        "wizard/warranty_approve.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "custom_warranty_claim_management/static/src/js/warranty_overview.js",
            "custom_warranty_claim_management/static/src/xml/warranty_overview.xml",
            "custom_warranty_claim_management/static/src/css/warranty_overview.css",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
