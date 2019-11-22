# -*- coding: utf-8 -*-
{
    'name': "acct_purchase",

    'summary': """
        锐驰采购模块。
        """,

    'description': """
        锐驰采购模块

    """,

    'author': "jasonD",
    'website': "http://www.acctronics.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'acc',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['acct_base','base','purchase','sale','web','account','mrp'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # 'report/layout_templates.xml',
        'wizard/import_bom_view.xml',
        'wizard/add_partner_view.xml',
        'wizard/purchase_separate_view.xml',
        'wizard/recreate_before_purchase_view.xml',
        'views/bom_view.xml',
        'views/acc_purchase_view.xml',
        'wizard/merge_purchase_view.xml',
        'wizard/merge_bom_view.xml',
        'views/demand_purchase_view.xml',
        'views/delivery_address_view.xml',
        'views/acc_company_view.xml',
        'views/before_purchase_view.xml',
        'views/ir_sequence.xml',

        'wizard/export_purchase_view.xml',

        'views/acc_purchase_report_view.xml',
        'views/en_purchase_report_view.xml',

        'views/report_menu.xml',
        'views/menu_items.xml',
    ],
}