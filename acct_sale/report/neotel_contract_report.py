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
import datetime,time
# from openerp.tools.float_utils import float_round as round

class NeotelReport(models.AbstractModel):
    _name = 'report.acct_sale.neotel_report_contract'

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

    def _get_total(self,docids,data=None):
        quotation = self.env['acc.quotation']
        today = time.strftime("%Y-%m-%d")
        res = {}
        # a = {}
        for quotation_model in quotation.browse(docids):
            # amount_total = sale_model.quo_amount_total or 0.00 
            amount_total = round(quotation_model.amount_total,2)
            upper_amount = self.rmb_upper(amount_total)
            # a = {'upper_amount':upper_amount or 0,'amount_total':amount_total or 0}
            # res[purchase_model.id] = {'upper_amount':upper_amount or 0,'amount_total':amount_total or 0}
            res = {
                    'amount_total':amount_total,
                    'upper_amount':upper_amount,
                    'today':today
            }
        return res

    def _get_logo(self,docids,data=None):
        # company_id = self.env.user.company_id
        quotation = self.env['acc.quotation'].browse(docids)
        company_id = quotation.sale_company
        logo = company_id.logo
        logo_transfer = str(logo, encoding="UTF8")
        # print (logo_transfer)
        return logo_transfer


    @api.model
    def _get_report_values(self,docids,data=None):
        report_obj = self.env['ir.actions.report']
        report = report_obj._get_report_from_name('acct_sale.neotel_report_contract')
        ac = self._get_total(docids)
        logo_transfer = self._get_logo(docids)
        # partner_info = self._get_partner_info(docids)
        return {
            'doc_ids': report.ids,
            'doc_model': report.model,
            'docs': self.env[report.model].browse(docids),
            'total':ac,
            'logo':logo_transfer,
            # 'partner_info':partner_info,
            'report_type': data.get('report_type') if data else '',
        }