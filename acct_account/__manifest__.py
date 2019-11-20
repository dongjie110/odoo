# -*- coding: utf-8 -*-
{
    'name': "acct_account",

    'summary': """
        锐驰财务模块。
        """,

    'description': """
        锐驰财务模块

    """,

    'author': "jasonD",
    'website': "http://www.acctronics.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'acc',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base','acct_base','acct_purchase','web','account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/acc_account_view.xml',
        'views/acc_account_asset_view.xml',

        # 'report/accstock_report_views.xml',

        # 'views/report_menu.xml',
    ],
}