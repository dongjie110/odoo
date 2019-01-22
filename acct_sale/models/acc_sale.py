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

class AccSaleOrder(models.Model):
    """
    销售单继承
    """
    _inherit = "sale.order"

    title = fields.Char(string=u'标题', required=True)
    crm_sonumber = fields.Char(string=u'老销售单号',readonly=True)
    charge_person = fields.Many2one('res.users',string=u'负责人',required=True)
    contact_id = fields.Many2one('res.partner',string='联系人')
    transfer = fields.Char(string='承运人')
    sale_commission = fields.Float(string='销售佣金')
    in_country = fields.Boolean(string='是否为国内订单')
    is_invoice = fields.Boolean(string='是否开票')
    is_purchasing = fields.Boolean(string='是否开始采购')
    is_send = fields.Boolean(string='是否发货')
    is_pay = fields.Boolean(string='是否收款')
    send_status = fields.Selection([('no', '未发货'), ('yes', '已发货'), ('part', '部分发货')], '发货情况')
    transaction_mode = fields.Many2one('transaction.rule',string='交易方式')
    transaction_rule = fields.Char(string='交易条款')
    # validity_date = fields.Date(string='有效期至')
    sale_company = fields.Many2one('acc.company',string = '卖方公司')


    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     args = args or []
    #     if self._uid == 2:
    #         return super(CFTemplateCategory, self).search(args, offset, limit, order, count)
    #     # 普通员工
    #     else:
    #         args.extend([('charge_person', '=', self._uid)])
    #     return super(CFTemplateCategory, self).search(args, offset, limit, order, count)
    #     
    
    @api.multi
    def action_confirm(self):
        res = super(AccSaleOrder, self).action_confirm()
        self.create_po()
        return res



    # @api.depends('order_line.price_total','discount_type','discount_rate','minus_amount')
    # def _amount_discount(self):
    #     for order in self:
    #         amount_untaxed = 0.0
    #         for line in order.order_line:
    #             amount_untaxed += line.price_subtotal
    #         discount_amount = 0.0
    #         if order.discount_type == 'nodiscount':
    #             discount_amount = 0.0
    #         if order.discount_type == 'discount':
    #             discount_amount = amount_untaxed * order.discount_rate/100
    #         if order.discount_type == 'minusprice':
    #             discount_amount = order.minus_amount
    #         order.update({
    #             'discount_amount': discount_amount,
    #         })
    @api.multi        
    def create_po(self):
        res_line = []
        for line in self.order_line:
            product_partner_id = line.product_id.product_tmpl_id.partner_id.id
            if not product_partner_id:
                raise UserError(u'订单中有产品未正确配置供应商')
            exits_order = self.compare_partner_id(line)
            line_vals = {
                      'product_id':line.product_id.id,
                      'name':line.name,
                      'product_qty':line.product_uom_qty,
                      'price_unit':line.product_id.product_tmpl_id.acc_purchase_price,
                      # 'taxes_id':line.taxes_id,
                      'date_planned':fields.Datetime.now(),
                      'product_uom':line.product_id.uom_id.id
            }
            # res.append((0,0,line_vals))
            res_line = [(0,0,line_vals)]
            po_vals = {
                    'partner_id':line.product_id.product_tmpl_id.partner_id.id,
                    'title':self.name,
                    'purchase_company':self.sale_company.id,
                    'charge_person':self.charge_person.id,
                    'forcast_date':fields.Datetime.now(),
                    'date_planned':fields.Datetime.now(),
                    'traffic_rule':' ',
                    'payment_rule':' ',
                    'origin_order':self.id,
                    'order_line':res_line
            }
            if not exits_order:
                po_obj = self.env['purchase.order'].create(po_vals)
            if exits_order:
                exits_order.write({'order_line':res_line})
                # if po_obj:
                #     self.write({'purchase_order_id':po_obj.id})
            # if exits_order:
        return True

    @api.multi
    def compare_partner_id(self,line):
        supply_partner_id = line.product_id.product_tmpl_id.partner_id.id
        exits_order = self.env['purchase.order'].search([('partner_id', '=', supply_partner_id),('origin_order', '=', self.id)])
        return exits_order


    # @api.model
    # def create(self,vals):
    #     # amount = 0.0
    #     amount = vals.get('amount_total',0) + vals.get('ship_fee',0)
    #     vals.update({
    #             "amount_total": amount
    #         })
    #     res = super(CFTemplateCategory, self).create(vals)
    #     return res

    # @api.model
    # def write(self, vals):
    #     # amount = 0.0
    #     if vals.get('ship_fee'):
    #         amount = self.amount_total + vals.get('ship_fee', 0)
    #         vals.update({
    #             "amount_total": amount
    #         })
    #     res = super(CFTemplateCategory, self).write(vals)
    #     return res

    def import_sale_data(self, fileName=None, content=None):
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


class AccSaleLine(models.Model):
    """
    采购单继承
    """
    _inherit = "sale.order.line"

    @api.onchange('product_uom_qty', 'product_uom')
    def product_uom_change(self):
        res = super(AccSaleLine, self).product_uom_change()
        # your logic here
        for rec in self:
            # rec.price_unit = self.product_id.product_tmpl_id.acc_purchase_price
            rec.name = self.product_id.product_tmpl_id.product_model

        return res

#     def import_purchase_line_data(self, fileName=None, content=None):
#         import_tips = ""
#         try:
#             if content:
#                 workbook = xlrd.open_workbook(file_contents=content)
#             else:
#                 raise ValidationError(u'请选择正确的文档')
#             book_sheet = workbook.sheet_by_index(0)
#             all_data = []
#             all_card_number = []
#             for row in range(1, book_sheet.nrows):
#                 row_data = []
#                 for col in range(book_sheet.ncols):
#                     cel = book_sheet.cell(row, col)
#                     val = cel.value
#                     row_data.append(val)
#                 all_data.append(row_data)
#             cr = self.env.cr
#             error_purchase_line_name = []
#             success_num = 0
#             for import_line in all_data:
#                 purchase_order = self.env['purchase.order'].search([('crm_ponumber', '=', str(import_line[0]))],limit=1)
#                 product = self.env['product.product'].search([('name', '=', str(import_line[1])),('product_describe_cn', '=', str(import_line[4]))])
#                 # print (len(product))
#                 if len(product) == 1:
#                     product_id = product.id
#                     uom_id = product.uom_id.id
#                 elif len(product) > 1:
#                     for p in product:
#                         product_id = p.id
#                         uom_id = p.uom_id.id
#                         if p.acc_purchase_price == float(import_line[3]):
#                             break
#                 else:
#                     product_id = 11638
#                     uom_id = 25               
#                 try:
#                     vals = {
#                         "order_id":purchase_order.id,
#                         "product_id":product_id,
#                         'date_planned':fields.Datetime.now(),
#                         'product_uom':uom_id,
#                         'name':import_line[4],
#                         "product_qty":import_line[2],
#                         "price_unit":float(import_line[3])
#                     }
#                     self.env['purchase.order.line'].create(vals)
#                     cr.commit()
#                     success_num += 1
#                     # print (import_line[1])
#                     _logger.debug('===========%s===============', import_line[1])
#                 except Exception as e:
#                     logging.error(e)
#                     error_purchase_line_name.append(import_line[1])
#             import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败产品名称{}".format(len(all_data), success_num,error_purchase_line_name)
#         except Exception as e:
#             logging.error(e)
#         else:
#             raise ValidationError(import_tips)




