# -*- coding: utf-8 -*-
{
    'name': "acct_base",

    'summary': """
        锐驰基础模块。
        """,

    'description': """
        锐驰基础模块

    """,

    'author': "jasonD",
    'website': "http://www.acctronics.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'acc',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base','purchase','sale','web','account','stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        # 'report/layout_templates.xml',
        'views/acc_product_view.xml',
        'views/res_groups.xml',
        'views/info_read_group.xml',
        'wizard/import_partner_data_wizard.xml',
        'wizard/import_contact_data_wizard.xml',
        'wizard/import_product_data_wizard.xml',
        'wizard/import_purchase_data_wizard.xml',
        'views/base_menu.xml',

        # 'data/template_category_data.xml',
    ],
}