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

    invoice_company = fields.Many2one('acc.company',string = '关联公司')
    invoice_number = fields.Char(string = '发票号')
    sale_invoice_number = fields.Char(string = '发票号')
    sale_invoice_date = fields.Datetime(string = '发票日期')
    payment_rule = fields.Char(string=u'支付条款',readonly=True)
    payrecord_line = fields.One2many('payrecord.line', 'payrecord_id','Payrecord line')
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




    # @api.model
    # def create(self,vals):
    #     # if vals.get('product_tmpl_id'):
    #     #     id_list = []
    #     #     new_id = vals.get('product_tmpl_id','')
    #     #     request.cr.execute("""select product_tmpl_id from mrp_bom""")
    #     #     lists = request.cr.dictfetchall()
    #     #     for p_id in lists:
    #     #         id_list.append(int(p_id['product_tmpl_id']))
    #     #     if new_id in id_list:
    #     #         raise ValidationError('物料清单重复！！')
    #     res = super(AccMrpBom, self).create(vals)
    #     return res


    @api.multi
    def get_poqty(self):
        for line in self.invoice_line_ids:
            product_qty = line.purchase_line_id.product_qty
            line.quantity = product_qty
        return True

    # @api.multi
    # def teller_accept(self):
    #     self.filtered(lambda r: r.state == 'open').write({'state': 'teller'})
    #     return True

    @api.multi
    def boss_accept(self):
        self.filtered(lambda r: r.state == 'teller').write({'state': 'open'})
        return True

    @api.multi
    def action_invoice_paid(self):
        res = super(AccAccountInvoice,self).action_invoice_paid()
        po_name = self.origin
        po_obj = self.env['purchase.order'].search([('name', '=', po_name)])
        if po_obj:
            if self.state == 'paid':
                po_obj.write({'payment_state':'allpay'})
            if self.state == 'open':
                po_obj.write({'payment_state':'partpay'})
        return res

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
    pay_amount = fields.Float(u'金额')
    pay_datetime = fields.Datetime(string='时间')
    pay_user = fields.Many2one('res.users',string='操作人')

