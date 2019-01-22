# -*- coding: utf-8 -*-
{
    'name': "cfprint",

    'summary': """
        康虎云报表基础模块，基于康虎云报表的打印功能必须依赖此模块。
        """,

    'description': """
康虎云报表基础模块
============================
基于康虎云报表的打印功能必须依赖此模块。


本模块主要功能：
----------------------------
* 引入康虎云报表所需的javascript库
* 实现打印模板管理功能，模板可以存入数据库，便于统一管理（从菜单  设置--技术--报告--康虎云报表 进入）
* 增加了根据原QWeb报表取值功能，该功能按QWeb模板中的方式取值，但把HTML去掉，否则数据不干净
* (功能持续增加中...)

    """,

    'author': "康虎软件工作室（QQ：360026606， 微信：360026606）",
    'website': "http://www.cfsoft.cf",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'CFSoft',
    'version': '12.0.1.0',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'report/layout_templates.xml',
        'views/cf_template_view.xml',

        'data/template_category_data.xml',
    ],
}