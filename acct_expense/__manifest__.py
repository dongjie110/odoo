# -*- coding: utf-8 -*-
{
    'name': "acct_expense",

    'summary': """
        锐驰费用模块。
        """,

    'description': """
        锐驰费用模块

    """,

    'author': "jasonD",
    'website': "http://www.acctronics.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'acc',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base','acct_base','web','hr'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/acc_hr_expense_view.xml',
        'report/acc_expense_report_view.xml',
        'views/report_menu.xml',

        # # 'data/template_category_data.xml',
    ],
}