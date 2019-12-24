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
            if invoice_amount > self.amount_total:
                raise ValidationError('所开发票总额已超过账单总额，请核对后重新输入')
            # self.rewrite_info(invoice_amount)
            order.update({
                'invoice_acc_total': invoice_amount
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


    # @api.onchange('payrecord_line')
    # def onchange_payrecord_line(self):
    #     for line in self.
    #     if self.forcast_date:
    #         for line in self.order_line:
    #             line.update({'forcast_date':self.forcast_date})

    # @api.multi
    # def write(self, vals):
    #     _logger.debug('=============%s=============',vals)
    #     if vals.get('payrecord_line'):
    #         _logger.debug('=============11=============')
    #         if self.type == 'out_invoice':
    #             _logger.debug('=============22=============')
    #             sale_obj = self.env['sale.order'].search([('name', '=', self.origin)])
    #             invoices = sale_obj.mapped('invoice_ids')
    #             invoices_total = 0.0
    #             for invoice in invoices:
    #                 invoices_total += invoice.invoice_acc_total
    #             _logger.debug('=============%s=======%s======',self.invoice_acc_total,invoices_total)
    #             if invoices_total < sale_obj.amount_total:
    #                 sale_obj.write({'is_invoice':'part'})
    #             if invoices_total == sale_obj.amount_total:
    #                 sale_obj.write({'is_invoice':'all'})
    #             if invoices_total == 0:
    #                 sale_obj.write({'is_invoice':'noinvoice'})
    #     res = super(AccAccountInvoice, self).write(vals)
    #     return res

    # @api.multi
    # def rewrite_info(self,invoice_amount):
    #     if self.type == 'out_invoice':
    #         sale_obj = self.env['sale.order'].search([('name', '=', self.origin)])
    #         invoices = sale_obj.mapped('invoice_ids')
    #         invoices_total = 0.0
    #         for invoice in invoices:
    #             if invoice.id != self.id:
    #                 invoices_total += invoice.invoice_acc_total
    #         if invoices_total + invoice_amount < sale_obj.amount_total:
    #             sale_obj.write({'is_invoice':'part'})
    #         elif invoices_total + invoice_amount == sale_obj.amount_total:
    #             sale_obj.write({'is_invoice':'all'})
    #         else:
    #             sale_obj.write({'is_invoice':'noinvoice'})
    #     return True         




    # @api.one
    # @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'tax_line_ids.amount_rounding',
    #              'currency_id', 'company_id', 'date_invoice', 'type')
    # def _compute_amount(self):
    #     res = super(AccAccountInvoice, self)._compute_amount()
    #     if self.type == 'in_invoice':
    #         self.amount_untaxed = self.amount_untaxed * (self.pay_rate/100)
    #         self.amount_tax = self.amount_tax * (self.pay_rate/100)
    #         self.amount_total = (self.amount_untaxed + self.amount_tax - self.minus_amount)
    #         amount_total_company_signed = self.amount_total
    #         sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
    #         self.amount_total_company_signed = amount_total_company_signed * sign
    #         self.amount_total_signed = self.amount_total * sign
    #     return res


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

    # @api.multi
    # def teller_accept(self):
    #     self.filtered(lambda r: r.state == 'open').write({'state': 'teller'})
    #     return True
    #     
    # @api.model
    # def create(self,vals):
    #     if vals.get('pay_rate'):
    #         po_obj = self.env['purchase.order'].search([('name', '=', vals.get('origin'))])
    #         paid_rate = po_obj.paid_rate + vals.get('pay_rate')
    #     result = super(AccAccountInvoice,self).create(vals)
    #     return result

    @api.multi
    def boss_accept(self):
        self.filtered(lambda r: r.state == 'teller').write({'state': 'open'})
        return True

    # @api.multi
    # def action_invoice_paid(self):
    #     res = super(AccAccountInvoice,self).action_invoice_paid()
    #     po_name = self.origin
    #     po_obj = self.env['purchase.order'].search([('name', '=', po_name)])
    #     if po_obj:
    #         if self.state == 'paid':
    #             po_obj.write({'payment_state':'allpay'})
    #         if self.state == 'open':
    #             po_obj.write({'payment_state':'partpay'})
    #     return res

    # @api.multi
    # def pay_and_reconcile(self, pay_journal, pay_amount=None, date=None, writeoff_acc=None):
    #     res = super(AccAccountInvoice,self).pay_and_reconcile(pay_journal, pay_amount=None, date=None, writeoff_acc=None)
    #     po_name = self.origin
    #     po_obj = self.env['purchase.order'].search([('name', '=', po_name)])
    #     if po_obj:
    #         po_obj.write({'payment_state':'partpay'})
    #     return res
    #     
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
    pay_datetime = fields.Datetime(string='时间',default=lambda self: fields.Datetime.now(),readonly=True)
    pay_user = fields.Many2one('res.users',string='操作人',default=lambda self: self.env.user.id,readonly=True)
    invoice_number = fields.Char(string='发票号')
    


