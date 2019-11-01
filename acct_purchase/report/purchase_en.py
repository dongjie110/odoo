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
from datetime import datetime,timedelta
# from openerp.tools.float_utils import float_round as round

class accenReport(models.AbstractModel):
    _name = 'report.acct_purchase.acc_report_purchaseorder'

    def rmb_upper(self, value):
        map = [u"零",u"壹",u"贰",u"叁",u"肆",u"伍",u"陆",u"柒",u"捌",u"玖"]
        unit = [u"分",u"角",u"元",u"拾",u"百",u"千",u"万",u"拾",u"百",u"千",u"亿",u"拾",u"百",u"千",u"万",u"拾",u"百",u"千",u"兆"]

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
        # products = self.env['product.product'].browse(data.get('ids', data.get('active_ids')))
        purchase = self.env['purchase.order']
        res = {}
        a = {}
        for purchase_model in purchase.browse(docids):
            amount_total = purchase_model.amount_total or 0.00 
            amount_total = round(amount_total,2)
            upper_amount = self.rmb_upper(amount_total)
            a = {'upper_amount':upper_amount or 0,'amount_total':amount_total or 0}
            res[purchase_model.id] = {'upper_amount':upper_amount or 0,'amount_total':amount_total or 0}
        return res

    def _get_logo(self,docids,data=None):
        # company_id = self.env.user.company_id
        purchase = self.env['purchase.order'].browse(docids)
        company_id = purchase.purchase_company
        logo = company_id.en_logo
        logo_transfer = str(logo, encoding="UTF8")
        # print (logo_transfer)
        return logo_transfer

    def _format_date_code(self,docids,data=None):
        purchase = self.env['purchase.order'].browse(docids)
        order_name = purchase.name
        date = purchase.gen_date
        forcast_date = purchase.forcast_date
        en_forcast_date = str(forcast_date.day)+ '-' + str(forcast_date.month) + '-' + str(forcast_date.year)
        # m = test_date.month
        en_date = str(date.day)+ '-' + str(date.month) + '-' + str(date.year)
        # en_date = str(datetime.strptime(date, '%Y-%m-%d %H:%M:%S'))[0:10]
        code = 'CD-000' + '-' + str(en_date) + '-' + order_name
        res = {
                'code':code,
                'date':en_date,
                'en_forcast_date':en_forcast_date
        }

        return res

    @api.model
    def _get_report_values(self,docids,data=None):
        report_obj = self.env['ir.actions.report']
        report = report_obj._get_report_from_name('acct_purchase.acc_report_purchaseorder')
        ac = self._get_total(docids)
        logo_transfer = self._get_logo(docids)
        date_code = self._format_date_code(docids)
        return {
            'doc_ids': report.ids,
            'doc_model': report.model,
            'docs': self.env[report.model].browse(docids),
            'total':ac.get('amount_total',0),
            'date_code':date_code,
            'logo':logo_transfer,
            'report_type': data.get('report_type') if data else '',
        }