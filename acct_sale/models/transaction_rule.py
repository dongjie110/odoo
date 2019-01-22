# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request

# 交易条款
class TransactionRule(models.Model):
    """
    交易条款
    """
    _name = 'transaction.rule'
    _inherit = ['mail.thread']
    _description = "交易条款"

    name = fields.Char(string='名称',required=True)
    active = fields.Boolean(string='有效',default=True)