# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
# from openerp.osv import osv, fields
from odoo import api, models
from odoo.exceptions import UserError, ValidationError
import datetime,time

class AccPurchaseInvoice(models.AbstractModel):
    _name = 'report.acct_account.acct_report_purchase_invoice'

    def rmb_upper(self, value):
        map = [u"零",u"壹",u"贰",u"叁",u"肆",u"伍",u"陆",u"柒",u"捌",u"玖"]
        unit = [u"分",u"角",u"元",u"拾",u"佰",u"仟",u"万",u"拾",u"佰",u"仟",u"亿",u"拾",u"佰",u"仟",u"万",u"拾",u"佰",u"仟",u"兆"]

        nums = []   #取出每一位数字，整数用字符方式转换避大数出现误差   
        for i in range(len(unit)-3, -3, -1):
            if value >= 10**i or i < 1:
                nums.append(int(round(value/(10**i),2))%10)

        words = []
        zflag = 0   #标记连续0次数，以删除万字，或适时插入零字
        start = len(nums)-3
        for i in range(start, -3, -1):   #使i对应实际位数，负数为角分
            if 0 != nums[start-i] or len(words) == 0:
                if zflag:
                    words.append(map[0])
                    zflag = 0
                words.append(map[nums[start-i]])
                words.append(unit[i+2])
            elif 0 == i or (0 == i%4 and zflag < 3): #控制‘万/元’
                words.append(unit[i+2])
                zflag = 0
            else:
                zflag += 1
                
        if words[-1] != unit[0]:    #结尾非‘分’补整字
            words.append(u"整")
        return ''.join(words)

    def _get_datas(self,docids,data=None):
        # products = self.env['product.product'].browse(data.get('ids', data.get('active_ids')))
        invoice = self.env['account.invoice']
        res = {}
        if len(docids)>1:
            final_total = 0.0
            po_names = ''
            note_str = ''
            bank_str = ''
            invoice_str = ''
            invoice_models = invoice.browse(docids)
            partner_ids = set([tmp.partner_id.id for tmp in invoice_models])
            if len(partner_ids) > 1:
                raise UserError('请选择供应商相同的账单')
            po_name = [po.origin for po in invoice_models]
            po_names = ','.join(po_name)
            today = time.strftime("%Y-%m-%d")
            for invoice_model in invoice_models:
                amount_total = invoice_model.amount_total or 0.00 
                amount_total = round(amount_total,2)
                if invoice_model.partner_bank_id:
                    bank_str = invoice_model.partner_bank_id.bank_id.name + ':' + invoice_model.partner_bank_id.acc_number
                if invoice_model.origin and invoice_model.payment_rule:
                    note_str += invoice_model.origin + ':' + invoice_model.payment_rule + ','
                if invoice_model.invoice_number:
                    invoice_str += invoice_model.invoice_number + ','
                final_total += amount_total
            res = {
                    'amount_total':final_total,
                    'po_names':po_names,
                    'note_str':note_str,
                    'bank_str':bank_str,
                    'invoice_str':invoice_str,
                    'today':today
            }
        else:
            po_names = ''
            note_str = ''
            bank_str = ''
            invoice_str = ''
            # a = {}
            # for invoice_model in invoice.browse(docids):
            invoice_model = invoice.browse(docids)
            amount_total = invoice_model.amount_total or 0.00 
            amount_total = round(amount_total,2)
            upper_amount = self.rmb_upper(amount_total)
            if invoice_model.origin and invoice_model.payment_rule:
                note_str = invoice_model.origin + ':' + invoice_model.payment_rule
            if invoice_model.origin:
                po_names = invoice_model.origin
            if invoice_model.partner_bank_id:
                bank_str = invoice_model.partner_bank_id.bank_id.name + invoice_model.partner_bank_id.acc_number
            if invoice_model.invoice_number:
                    invoice_str = invoice_model.invoice_number
            today = time.strftime("%Y-%m-%d")
            # a = {'upper_amount':upper_amount or 0,'amount_total':amount_total or 0}
            # res[purchase_model.id] = {'upper_amount':upper_amount or 0,'amount_total':amount_total or 0}
            res = {
                    'amount_total':amount_total,
                    'po_names':po_names,
                    'note_str':note_str,
                    'bank_str':bank_str,
                    'invoice_str':invoice_str,
                    'today':today
            }
        return res

    def _get_logo(self,useids,data=None):
        # company_id = self.env.user.company_id
        obj_model = self.env['account.invoice'].browse(useids)
        company_id = obj_model.invoice_company
        logo = company_id.logo
        logo_transfer = str(logo, encoding="UTF8")
        # print (logo_transfer)
        return logo_transfer


    @api.model
    def _get_report_values(self,docids,data=None):
        report_obj = self.env['ir.actions.report']
        report = report_obj._get_report_from_name('acct_account.acct_report_purchase_invoice')
        # ac = self._get_total(docids)
        # if len[docids] > 1:
        datas = self._get_datas(docids)
        useids = [docids[0]]
        logo_transfer = self._get_logo(useids)
        # partner_info = self._get_partner_info(docids)
        return {
            'doc_ids': report.ids,
            'doc_model': report.model,
            'docs': self.env[report.model].browse(useids),
            'final_datas':datas,
            'logo':logo_transfer,
            # 'partner_info':partner_info,
            'report_type': data.get('report_type') if data else '',
        }