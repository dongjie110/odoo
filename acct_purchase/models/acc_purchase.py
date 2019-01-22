# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
from odoo.http import request
import logging
import xlrd
from collections import Counter
import re
import datetime as dt

import pytz

from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
# from ..controllers.common import localizeStrTime
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class CFTemplateCategory(models.Model):
    """
    采购单继承
    """
    _inherit = "purchase.order"


    title = fields.Char(string=u'标题', required=True)
    crm_ponumber = fields.Char(string=u'老采购单号',readonly=True)
    charge_person = fields.Many2one('res.users',string=u'负责人',required=True)
    traffic_rule = fields.Char(string=u'运输条款',required=True)
    delivery_time = fields.Char(string=u'货期',placeholder="填写格式如(1-2周,1-2weeks,1-2天，1-2days)")
    product_state = fields.Selection([('new', '未到货'), ('part', '部分到货'), ('all', '全部到货'), ('cancel', '取消订单')], '产品到货状态', default='new')
    payment_state = fields.Selection([('partpay', '部分已付'), ('nopay', '未付'), ('allpay', '全部付清')], '付款状态', default='nopay')
    purchase_way = fields.Char(string=u'采购用途')
    purchase_company = fields.Many2one('acc.company',string=u'采购公司',required=True)
    # purchase_company = fields.Many2one('res.company',string=u'采购公司')
    quality_state = fields.Selection([('waitcheck', '待检'), ('qualified', '合格'), ('unqualified', '不合格')], '质检状态', default='qualified')
    payment_rule = fields.Char(string=u'支付条款',required=True)
    end_date = fields.Date(string=u'截止日期')
    forcast_date = fields.Date(string='预计到货日期',required=True)
    # forcast_date = fields.Date(string='预计到货日期')
    gen_date = fields.Datetime(string=u'生成日期',default=lambda self: fields.Datetime.now(),readonly=True)
    demand_purchase = fields.Many2one('demand.purchase',string='关联请购单',readonly=True)
    delivery_address = fields.Many2one('delivery.address',string='交货地址')
    discount_type = fields.Selection([('nodiscount', '无折扣'), ('discount', '折扣(%价格)'), ('minusprice', '直接降价')],'折扣',default='nodiscount')
    discount_rate = fields.Float('折扣比例')
    minus_amount = fields.Float('降价金额')
    ship_fee = fields.Float('运输费用')
    discount_amount = fields.Monetary('折扣总额',store=True, readonly=True, compute='_amount_discount')
    contact_id = fields.Many2one('res.partner',string='联系人')
    en_name = fields.Char(string='负责人英文名')
    origin_order = fields.Many2one('sale.order',string='关联销售订单')


    def search(self, args, offset=0, limit=None, order=None, count=False):
        args = args or []
        if self._uid == 2:
            return super(CFTemplateCategory, self).search(args, offset, limit, order, count)
        # 普通员工
        else:
            args.extend([('charge_person', '=', self._uid)])
        return super(CFTemplateCategory, self).search(args, offset, limit, order, count)



    @api.depends('order_line.price_total','discount_type','discount_rate','minus_amount')
    def _amount_discount(self):
        for order in self:
            amount_untaxed = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
            discount_amount = 0.0
            if order.discount_type == 'nodiscount':
                discount_amount = 0.0
            if order.discount_type == 'discount':
                discount_amount = amount_untaxed * order.discount_rate/100
            if order.discount_type == 'minusprice':
                discount_amount = order.minus_amount
            order.update({
                'discount_amount': discount_amount,
            })

    @api.onchange('delivery_time')
    def onchange_delivery_time(self):
        if self.delivery_time:
            delivery_time = self.delivery_time
            length = len(str(delivery_time))
            if length == 4:
                delivery_num = int(delivery_time[2])
                unit = delivery_time[3]
                if unit == '周':
                    days = delivery_num * 7
                elif unit == '天':
                    days = delivery_num
                else:
                    raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
            elif length == 8:
                delivery_num = int(delivery_time[2])
                unit = delivery_time[3:]
                if unit == 'weeks':
                    days = delivery_num * 7
                else:
                    raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
            elif length == 7:
                delivery_num = int(delivery_time[2])
                unit = delivery_time[3:]
                if unit == 'days':
                    days = delivery_num
                else:
                    raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
            else:
                raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
            forcast_date = datetime.now().date()
            date = forcast_date + dt.timedelta(days=days)
            # current_time = str(datetime.utcnow() + timedelta(hours=8))[0:19]
            # if self.internal_type == 'liquidity':
            self.forcast_date = date

    @api.onchange('charge_person')
    def onchange_en_name(self):
        if self.charge_person:
            login_en_name = 0
            login = self.charge_person.login
            login_index = login.index('@')
            login_en_name = login[0:login_index]
            self.en_name = login_en_name
    @api.model
    def create(self,vals):
        # amount = 0.0
        amount = vals.get('amount_total',0) + vals.get('ship_fee',0)
        vals.update({
                "amount_total": amount
            })
        res = super(CFTemplateCategory, self).create(vals)
        return res

    @api.model
    def write(self, vals):
        # amount = 0.0
        if vals.get('ship_fee'):
            amount = self.amount_total + vals.get('ship_fee', 0)
            vals.update({
                "amount_total": amount
            })
        res = super(CFTemplateCategory, self).write(vals)
        return res

    def import_purchase_data(self, fileName=None, content=None):
        import_tips = ""
        try:
            if content:
                workbook = xlrd.open_workbook(file_contents=content)
            else:
                raise ValidationError(u'请选择正确的文档')
            book_sheet = workbook.sheet_by_index(0)
            all_data = []
            all_card_number = []
            for row in range(1, book_sheet.nrows):
                row_data = []
                for col in range(book_sheet.ncols):
                    cel = book_sheet.cell(row, col)
                    val = cel.value
                    row_data.append(val)
                all_data.append(row_data)
            cr = self.env.cr
            error_purchase_name = []
            success_num = 0
            for import_line in all_data:
                res_partner = self.env['res.partner'].search([('name', '=', str(import_line[2]))])
                if res_partner:
                    partner_id = res_partner.id
                else:
                    partner_id = 77874
                res_company = self.env['res.company'].search([('name', '=', str(import_line[13]))])
                payment_state = import_line[9]
                if payment_state == '全部付清':
                    payment_state = 'allpay'
                elif payment_state == '未付':
                    payment_state = 'nopay'
                else:
                    payment_state = 'partpay'
                product_state = import_line[12]
                if product_state == '全部到货':
                    product_state = 'all'
                elif product_state == '取消订单':
                    product_state = 'cancel'
                else:
                    product_state = 'new'
                currency = import_line[14]
                if currency == 'China, Yuan Renminbi':
                    currency_id = self.env['res.currency'].search([('name', '=', 'CNY')])
                if currency == 'Euro':
                    currency_id = self.env['res.currency'].search([('name', '=', 'EUR')])
                if currency == 'Switzerland Francs':
                    currency_id = self.env['res.currency'].search([('name', '=', 'CHF')])
                if currency == 'United Kingdom, Pounds':
                    currency_id = self.env['res.currency'].search([('name', '=', 'GBP')])
                if currency == 'USA, Dollars':
                    currency_id = self.env['res.currency'].search([('name', '=', 'USD')]) 
                try:
                    vals = {
                        "title":import_line[0],
                        "crm_ponumber":import_line[1],
                        "partner_id":partner_id,
                        # 'end_date':import_line[3],
                        "charge_person":2,
                        # "purchase_company":1,
                        "state":'purchase',
                        "traffic_rule":import_line[6],
                        "payment_rule":import_line[7],
                        "amount_total":float(import_line[8]),
                        'payment_state':payment_state,
                        "delivery_time":import_line[10],
                        "purchase_way":import_line[11],
                        "purchase_company":res_company.id,
                        "currency_id":currency_id.id,
                        "amount_untaxed":float(import_line[15]),
                        "notes":import_line[16]
                    }
                    self.env['purchase.order'].create(vals)
                    cr.commit()
                    success_num += 1
                    # print (import_line[0],import_line[1])
                    _logger.debug('===========%s===============%s', import_line[0], import_line[1])
                except Exception as e:
                    logging.error(e)
                    error_purchase_name.append(import_line[1])
            import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败po编号{}".format(len(all_data), success_num,error_purchase_name)
        except Exception as e:
            logging.error(e)
        else:
            raise ValidationError(import_tips)

    # 增加负责人
    def import_purchase_charge(self, fileName=None, content=None):
        import_tips = ""
        try:
            if content:
                workbook = xlrd.open_workbook(file_contents=content)
            else:
                raise ValidationError(u'请选择正确的文档')
            book_sheet = workbook.sheet_by_index(0)
            all_data = []
            all_card_number = []
            for row in range(1, book_sheet.nrows):
                row_data = []
                for col in range(book_sheet.ncols):
                    cel = book_sheet.cell(row, col)
                    val = cel.value
                    row_data.append(val)
                all_data.append(row_data)
            cr = self.env.cr
            error_purchase_name = []
            success_num = 0
            for import_line in all_data:
                purchase_order = self.env['purchase.order'].search([('crm_ponumber', '=', str(import_line[0]))])
                # if purchase_order:
                #     purchase_order = purchase_order
                # else:
                
                charge_person = self.env['res.users'].search([('login', '=', str(import_line[1]))])
                if charge_person:
                    charge_person_id = charge_person.id
                else:
                    charge_person_id = 2
                try:
                    vals = {
                        "charge_person":charge_person_id
                    }
                    purchase_order.write(vals)
                    cr.commit()
                    success_num += 1
                    # print (import_line[0],import_line[1])
                    _logger.debug('===========%s===============%s', import_line[0], import_line[1])
                except Exception as e:
                    logging.error(e)
                    error_purchase_name.append(import_line[1])
            import_tips = "一共写入 {} 条数据，写入成功条数为{} 写入失败po编号{}".format(len(all_data), success_num,error_purchase_name)
        except Exception as e:
            logging.error(e)
        else:
            raise ValidationError(import_tips)


class AccPurchaseLine(models.Model):
    """
    采购单继承
    """
    _inherit = "purchase.order.line"

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        res = super(AccPurchaseLine, self)._onchange_quantity()
        # your logic here
        for rec in self:
            rec.price_unit = self.product_id.product_tmpl_id.acc_purchase_price
            rec.name = self.product_id.product_tmpl_id.product_model

        return res

    def import_purchase_line_data(self, fileName=None, content=None):
        import_tips = ""
        try:
            if content:
                workbook = xlrd.open_workbook(file_contents=content)
            else:
                raise ValidationError(u'请选择正确的文档')
            book_sheet = workbook.sheet_by_index(0)
            all_data = []
            all_card_number = []
            for row in range(1, book_sheet.nrows):
                row_data = []
                for col in range(book_sheet.ncols):
                    cel = book_sheet.cell(row, col)
                    val = cel.value
                    row_data.append(val)
                all_data.append(row_data)
            cr = self.env.cr
            error_purchase_line_name = []
            success_num = 0
            for import_line in all_data:
                purchase_order = self.env['purchase.order'].search([('crm_ponumber', '=', str(import_line[0]))],limit=1)
                product = self.env['product.product'].search([('name', '=', str(import_line[1])),('product_describe_cn', '=', str(import_line[4]))])
                # print (len(product))
                if len(product) == 1:
                    product_id = product.id
                    uom_id = product.uom_id.id
                elif len(product) > 1:
                    for p in product:
                        product_id = p.id
                        uom_id = p.uom_id.id
                        if p.acc_purchase_price == float(import_line[3]):
                            break
                else:
                    product_id = 11638
                    uom_id = 25               
                try:
                    vals = {
                        "order_id":purchase_order.id,
                        "product_id":product_id,
                        'date_planned':fields.Datetime.now(),
                        'product_uom':uom_id,
                        'name':import_line[4],
                        "product_qty":import_line[2],
                        "price_unit":float(import_line[3])
                    }
                    self.env['purchase.order.line'].create(vals)
                    cr.commit()
                    success_num += 1
                    # print (import_line[1])
                    _logger.debug('===========%s===============', import_line[1])
                except Exception as e:
                    logging.error(e)
                    error_purchase_line_name.append(import_line[1])
            import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败产品名称{}".format(len(all_data), success_num,error_purchase_line_name)
        except Exception as e:
            logging.error(e)
        else:
            raise ValidationError(import_tips)




