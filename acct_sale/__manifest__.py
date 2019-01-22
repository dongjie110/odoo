# -*- coding: utf-8 -*-
{
    'name': "acct_sale",

    'summary': """
        锐驰销售模块。
        """,

    'description': """
        锐驰销售模块

    """,

    'author': "jasonD",
    'website': "http://www.acctronics.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'acc',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base','sale','web','account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/acc_sale_view.xml',
        'views/transaction_rule_view.xml',

        # 'data/template_category_data.xml',
    ],
}