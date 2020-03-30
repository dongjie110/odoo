# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
from odoo.http import request
import logging
import xlrd
from collections import Counter
import re
import datetime

import pytz

from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
# from datetime import datetime
# from ..controllers.common import localizeStrTime
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class AccAccountInvoice(models.Model):
    """
     account.invoice继承
    """
    _inherit = "account.invoice"

    @api.depends('payrecord_line.pay_amount')
    def _invoice_all(self):
        invoice_amount = 0.0
        for order in self:
            for line in order.payrecord_line:
                invoice_amount += line.pay_amount
            if round(invoice_amount,2) > self.amount_total:
                raise ValidationError('所开发票总额已超过账单总额，请核对后重新输入')
            elif round(invoice_amount,2) < self.amount_total and round(invoice_amount,2) !=0:
                invoice_state = 'part'
            elif round(invoice_amount,2) == self.amount_total:
                invoice_state = 'all'
            else:
                invoice_state = 'noinvoice'
            order.update({
                'invoice_acc_total': invoice_amount,
                'invoice_state':invoice_state
            })

    invoice_company = fields.Many2one('acc.company',string = '关联公司')
    invoice_number = fields.Char(string = '发票号')
    sale_invoice_number = fields.Char(string = '发票号')
    sale_invoice_date = fields.Datetime(string = '发票日期')
    payment_rule = fields.Char(string=u'支付条款',readonly=True)
    pay_rate = fields.Float(string='付款比例(%)',readonly=True)
    minus_amount = fields.Float('折扣总额',readonly=True)
    acct_note = fields.Char('备注')
    payrecord_line = fields.One2many('payrecord.line', 'payrecord_id','Payrecord line')
    invoice_acc_total = fields.Float(string='已开票金额', store=True, readonly=True, compute='_invoice_all')
    # invoice_acc_total = fields.Float(string='已开票金额', readonly=True)
    invoice_state = fields.Selection([('part', '部分开票'), ('all', '全部开票'), ('noinvoice', '未开票')], string='账单开票情况',store=True,readonly=True,default='noinvoice',compute='_invoice_all')
    # invoice_state = fields.Selection([('part', '部分开票'), ('all', '全部开票'), ('noinvoice', '未开票')], string='账单开票情况',readonly=True)
    # acc_total = fields.Float(string='acc已开票金额')
    # invoice_acc_total = fields.Float(string='已开票金额')
    state = fields.Selection([
            ('draft','Draft'),
            ('teller', '出纳已审核'),
            # ('boss', '管理部已审核'),
            ('open', 'Open'),
            ('in_payment', 'In Payment'),
            ('paid', 'Paid'),
            ('cancel', 'Cancelled'),
        ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
             " * The 'Open' status is used when user creates invoice, an invoice number is generated. It stays in the open status till the user pays the invoice.\n"
             " * The 'In Payment' status is used when payments have been registered for the entirety of the invoice in a journal configured to post entries at bank reconciliation only, and some of them haven't been reconciled with a bank statement line yet.\n"
             " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Cancelled' status is used when user cancel invoice.")


    @api.multi
    def get_poqty(self):
        for line in self.invoice_line_ids:
            product_qty = line.purchase_line_id.product_qty
            line.quantity = product_qty
        return True

    @api.multi
    def add_discount_line(self):
        minus_amount = self.minus_amount
        if minus_amount == 0.0:
            raise ValidationError("此账单无折扣金额")
        else:
            discount_product_tmpl = self.env['product.template'].search([('name', '=', '折扣调节')])
            discount_product_id = self.env['product.product'].search([('product_tmpl_id', '=', discount_product_tmpl.id)])
            discount_data = {
            'name': self.origin + ': ' + discount_product_tmpl.name,
            'origin': self.origin,
            'uom_id': discount_product_tmpl.uom_id.id,
            'product_id': discount_product_id.id,
            # 'account_id': invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
            'account_id': self.journal_id.default_debit_account_id.id,
            # 'price_unit': line.order_id.currency_id._convert(
            #     line.price_unit, self.currency_id, line.company_id, date or fields.Date.today(), round=False),
            'price_unit': -self.minus_amount,
            'quantity': 1,
            'discount': 0.0,
            'invoice_id':self.id
            # 'account_analytic_id': line.account_analytic_id.id,
            # 'analytic_tag_ids': line.analytic_tag_ids.ids,
            # 'invoice_line_tax_ids': invoice_line_tax_ids.ids
            }
            self.env['account.invoice.line'].create(discount_data)
        return True

    @api.multi
    def add_sale_discount_line(self):
        sale_obj = self.env['sale.order'].search([('name', '=', self.origin)])
        minus_amount = sale_obj.discount
        if minus_amount == 0.0:
            raise ValidationError("此账单无折扣金额")
        else:
            discount_product_tmpl = self.env['product.template'].search([('name', '=', '折扣调节')])
            discount_product_id = self.env['product.product'].search([('product_tmpl_id', '=', discount_product_tmpl.id)])
            discount_data = {
            'name': self.origin + ': ' + discount_product_tmpl.name,
            'origin': self.origin,
            'uom_id': discount_product_tmpl.uom_id.id,
            'product_id': discount_product_id.id,
            # 'account_id': invoice_line.with_context({'journal_id': self.journal_id.id, 'type': 'in_invoice'})._default_account(),
            'account_id': self.journal_id.default_debit_account_id.id,
            # 'price_unit': line.order_id.currency_id._convert(
            #     line.price_unit, self.currency_id, line.company_id, date or fields.Date.today(), round=False),
            'price_unit': -minus_amount,
            'quantity': 1,
            'discount': 0.0,
            'invoice_id':self.id
            # 'account_analytic_id': line.account_analytic_id.id,
            # 'analytic_tag_ids': line.analytic_tag_ids.ids,
            # 'invoice_line_tax_ids': invoice_line_tax_ids.ids
            }
            self.env['account.invoice.line'].create(discount_data)
        return True

    @api.multi
    def boss_accept(self):
        self.filtered(lambda r: r.state == 'teller').write({'state': 'open'})
        return True
    
    @api.onchange('invoice_number')
    def onchange_invoice_number(self):
        if self.invoice_number:
            po_name = self.origin
            po_obj = self.env['purchase.order'].search([('name', '=', po_name)])
            invoice_str = '发票号:' + self.invoice_number
            if po_obj:
                po_obj.write({'notes':invoice_str})
            # move_ids = []
            # # print (self.location_src_id)
            # for line in self.move_raw_ids:
            #     if line.raw_material_production_id:
            #         move_ids.append(line.id)
            #         # line.update({'location_id':self.location_src_id})
            # cr = self.env.cr
            # change_sql = """ UPDATE stock_move
            #                 SET location_id = %s
            #                 WHERE
            #                     id in %s """
            # # cr.execute(all_total)
            # cr.execute(change_sql, (self.location_src_id.id,tuple(move_ids)))
    @api.onchange('sale_invoice_number')
    def onchange_sale_invoice_number(self):
        if self.sale_invoice_number:
            so_name = self.origin
            so_obj = self.env['sale.order'].search([('name', '=', so_name)])
            invoice_str = '发票号:' + self.sale_invoice_number
            if so_obj:
                so_obj.write({'note':invoice_str})

class PayrecordLine(models.Model):
    """
    付款记录
    """
    _name = 'payrecord.line'
    # _inherit = ['mail.thread']
    _description = "付款记录"

    payrecord_id = fields.Many2one('account.invoice', 'Order Reference')
    pay_amount = fields.Float(u'发票金额')
    invoice_datetime = fields.Date(string='发票日期')
    pay_datetime = fields.Datetime(string='登记时间',default=lambda self: fields.Datetime.now(),readonly=True)
    pay_user = fields.Many2one('res.users',string='操作人',default=lambda self: self.env.user.id,readonly=True)
    invoice_number = fields.Char(string='发票号')


class AccAccountAssetAsset(models.Model):
    """
     account.asset.asset继承
    """
    _inherit = "account.asset.asset"

    asset_sequence = fields.Char(string='序列号',copy=False)
    user_id = fields.Many2one('res.users',string='使用人')
    acc_asset_code = fields.Char(string='资产编号')
    acc_type = fields.Selection([('consumable', '易耗品'), ('low', '低值'), ('fixed', '固定资产'), ('book', '图书')], string='资产类型', required=True)
    user_line = fields.One2many('user.line', 'record_id','user line')


class AccAccountAssetCategory(models.Model):
    """
     account.asset.asset继承
    """
    _inherit = "account.asset.category"

    acc_type = fields.Selection([('consumable', '易耗品'), ('low', '低值'), ('fixed', '固定资产'), ('book', '图书')], string='类型', required=True)

class UserLine(models.Model):
    """
    使用记录
    """
    _name = 'user.line'
    # _inherit = ['mail.thread']
    _description = "使用记录"

    record_id = fields.Many2one('account.asset.asset', 'Order Reference')
    start_datetime = fields.Datetime(string='开始日期')
    end_datetime = fields.Datetime(string='结束日期')
    # pay_datetime = fields.Datetime(string='登记时间',default=lambda self: fields.Datetime.now(),readonly=True)
    user_id = fields.Many2one('res.users',string='使用人')
    use_state = fields.Selection([('returned', '已归还'), ('using', '正在使用')], string='使用状态')
    # invoice_number = fields.Char(string='发票号')


    


