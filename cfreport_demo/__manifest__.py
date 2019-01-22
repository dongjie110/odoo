# -*- coding: utf-8 -*-
{
    'name': "cfreport_demo",

    'summary': """
        康虎云报表与ODOO集成的例子""",

    'description': """
        本模块演示了在ODOO中如何集成康虎云报表以实现精准精细打印。
    """,

    'author': "CFSoft Studio",
    'website': "http://www.khcloud.net",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'cfsoft',
    'version': '12.0.1.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale','product', 'cfprint'],

    # always loaded
    'data': [
        'report/cfprint_report_templates.xml',
        'report/cfprint_report_views.xml',

        'data/cfprint_templates.xml',
    ],
}