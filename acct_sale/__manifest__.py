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
    'depends': ['acct_base','acct_purchase','base','sale','web','account','crm'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/acc_sale_view.xml',
        'views/transaction_rule_view.xml',
        'views/acc_crm_lead_view.xml',

        'report/acc_quotation_report_view.xml',
        'report/acc_contract_report_view.xml',
        'report/accen_quotation_report_view.xml',
        'report/accen_contract_report_view.xml',
        'report/accall_quotation_report_view.xml',
        'report/accenall_quotation_report_view.xml',
        'report/neotel_contract_report_view.xml',

        'wizard/export_sale_invoice_view.xml',
        'report/accenall_quotation_report_view.xml',
        'views/ir_sequence.xml',


        'views/base_menu.xml',
        'views/report_menu.xml',
    ],
}