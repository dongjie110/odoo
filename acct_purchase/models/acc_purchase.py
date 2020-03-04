# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
from odoo.http import request
import logging
import xlrd
import xlwt
from collections import Counter
import re
import datetime as dt

import pytz
import sys,os
file_url = 'my_addons/acct_purchase'
file_url = os.path.join(sys.path[0],file_url)
import logging
from datetime import datetime
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def check_path(image_path):
    try:
        dir_path = os.path.dirname(image_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    except OSError as e:
        logging.debug("file cant be created!{}".format(e))
    return True

class CFTemplateCategory(models.Model):
    """
    采购单继承
    """
    _inherit = "purchase.order"


    title = fields.Char(string=u'标题', required=True)
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('confirm', '已提交审批'),
        ('pomanager', '采购经理已审批'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('boss', '管理部已批准'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')
    crm_ponumber = fields.Char(string=u'老采购单号',readonly=True)
    charge_person = fields.Many2one('res.users',string=u'负责人',default=lambda self: self.env.user.id,required=True)
    traffic_rule = fields.Char(string=u'运输条款',required=True)
    delivery_time = fields.Char(string=u'货期',placeholder="填写格式如(1-2周,1-2weeks,1-2天，1-2days)")
    product_state = fields.Selection([('new', '未到货'), ('part', '部分到货'), ('all', '全部到货'), ('cancel', '取消订单')], '产品到货状态', default='new')
    payment_state = fields.Selection([('partpay', '部分已付'), ('nopay', '未付'), ('allpay', '全部付清')], '付款状态', default='nopay')
    purchase_way = fields.Char(string=u'采购用途')
    pay_rate = fields.Float(string=u'本次付款比例(%)')
    paid_rate = fields.Float(string=u'已付款比例(%)')
    is_excipients = fields.Boolean(string='辅料采购',readonly=True)
    purchase_company = fields.Many2one('acc.company',string=u'采购公司',required=True)
    # purchase_company = fields.Many2one('res.company',string=u'采购公司')
    quality_state = fields.Selection([('waitcheck', '待检'), ('qualified', '合格'), ('unqualified', '不合格')], '质检状态', default='qualified')
    payment_rule = fields.Char(string=u'支付条款',required=True)
    end_date = fields.Date(string=u'截止日期')
    forcast_date = fields.Date(string='预计到货日期',required=True)
    gen_date = fields.Datetime(string=u'生成日期',default=lambda self: fields.Datetime.now(),readonly=True)
    demand_purchase = fields.Many2one('demand.purchase',string='关联请购单',readonly=True)
    before_purchase_id = fields.Many2one('before.purchase',string='源待确认询价单',readonly=True)
    delivery_address = fields.Many2one('delivery.address',string='交货地址')
    discount_type = fields.Selection([('nodiscount', '无折扣'), ('discount', '折扣(%价格)'), ('minusprice', '直接降价')],'折扣',default='nodiscount')
    discount_rate = fields.Float('折扣比例')
    minus_amount = fields.Float('降价金额')
    ship_fee = fields.Float('运输费用')
    discount_amount = fields.Monetary('折扣总额',store=True, readonly=True, compute='_amount_discount')
    contact_id = fields.Many2one('res.partner',string='联系人')
    en_name = fields.Char(string='负责人英文名')
    purchase_type = fields.Selection([('trade', '贸易'), ('office', '办公用品'), ('manufacture', '生产'),('accessories', '辅料'),('boss', '需管理部审核')],'采购类型',default='trade')
    merge_info = fields.Char(string='合并信息',readonly=True)
    origin_order = fields.Many2one('sale.order',string='关联销售订单',readonly=True)
    purchase_payrecord_line = fields.One2many('purchase.payrecord.line', 'purchase_payrecord_id','Payrecord line')


    def search(self, args, offset=0, limit=None, order=None, count=False):
        args = args or []
        if self._uid == 2:
            return super(CFTemplateCategory, self).search(args, offset, limit, order, count)
        elif self.env.user.has_group('acct_base.unovo_it_info_group'):
            return super(CFTemplateCategory, self).search(args, offset, limit, order, count)
        elif self.env.user.has_group('acct_base.acc_commerce_manager_group'):
            users = self.get_users()
            args.extend([('charge_person', 'in', users)])
            return super(CFTemplateCategory, self).search(args, offset, limit, order, count)
        # 普通员工
        else:
            args.extend([('charge_person', '=', self._uid)])
        return super(CFTemplateCategory, self).search(args, offset, limit, order, count)

    def get_users(self):
        commerce_group = self.env['res.groups'].search([('name', '=', '商务部员工')])
        gid = commerce_group.id
        cr = self.env.cr
        sql = """
                select * from res_groups_users_rel where gid = %s
        """%(gid)
        cr.execute(sql)
        result = cr.dictfetchall()
        uids = [m['uid'] for m in result]
        # lists = [1,2]
        return uids

    @api.depends('order_line.price_total')
    def _amount_all(self):
        res = super(CFTemplateCategory, self)._amount_all()
        self.amount_total = self.amount_untaxed + self.amount_tax - self.discount_amount
        return res


    @api.multi
    def pre_userids(self,logins):
        user_ids = []
        for login in logins:
            login_user = self.env['res.users'].search([('login', '=', login)])
            user_ids.append(login_user.id)
        return user_ids

    
    @api.multi
    def boss_accept(self):
        self.filtered(lambda r: r.state == 'pomanager').write({'state': 'boss'})
        activity_addrs = ['luna.zhang@neotel-technology.com','cissy.shen@neotel-technology.com']
        # "张晓茹"<luna.zhang@neotel-technology.com>;
        toaddrs = ['luna.zhang@neotel-technology.com']
        toaddrs.append(self.charge_person.login)
        # toaddrs = ['jie.dong@acctronics.cn','yapeng.dai@acctronics.cn']
        subjects = "采购单{}管理部已审批完成,请及时确认".format(self.name)
        message = "采购单{}<br><br>标题：{}<br><br>供应商：{}<br><br>支付条款：{}<br><br>总价：{}<br><br><br>管理部审批完成,请及时处理<br><br><br>谢谢".format(self.name,self.title,self.partner_id.name,self.payment_rule,self.amount_total)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        self.activity_unlink()
        user_ids = self.pre_userids(activity_addrs)
        self.send_mailactivity(user_ids)
        return True

    @api.multi
    def button_approve(self):
        res = super(CFTemplateCategory, self).button_approve()
        self.activity_unlink()
        return res

    @api.multi
    def button_draft(self):
        res = super(CFTemplateCategory, self).button_draft()
        toaddrs = []
        toaddrs.append(self.charge_person.login)
        # toaddrs = ['jie.dong@acctronics.cn','cissy.shen@acctronics.cn']
        # toaddrs = ['jie.dong@acctronics.cn','yapeng.dai@acctronics.cn']
        subjects = "采购单{}已被拒绝,请修改后重新提交".format(self.name)
        message = "采购单{}<br><br>标题：{}<br><br>供应商：{}<br><br>支付条款：{}<br><br>总价：{}<br><br><br>已被拒绝,请及时处理<br><br><br>谢谢".format(self.name,self.title,self.partner_id.name,self.payment_rule,self.amount_total)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        self.activity_unlink()
        user_ids = self.pre_userids(toaddrs)
        self.send_mailactivity(user_ids)
        return res

    @api.multi
    def confirm(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'confirm'})
        # toaddrs = []
        # toaddrs.append(self.manage_user.login)
        toaddrs = ['cissy.shen@neotel-technology.com']
        # toaddrs = ['jie.dong@acctronics.cn']
        subjects = "采购单{}需要您审批,请及时处理".format(self.name)
        message = "采购单{}<br><br>标题：{}<br><br>供应商：{}<br><br>支付条款：{}<br><br>总价：{}<br><br><br>需要您审批,请及时处理<br><br><br>谢谢".format(self.name,self.title,self.partner_id.name,self.payment_rule,self.amount_total)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        # self.activity_update()
        # ms = '测试消息'
        # self.send_notification(ms)
        self.activity_unlink()
        user_ids = self.pre_userids(toaddrs)
        self.send_mailactivity(user_ids)
        return True

    @api.multi
    def pomanager(self):
        if self.purchase_type == 'boss':
            self.filtered(lambda r: r.state == 'confirm').write({'state': 'pomanager'})
            # toaddrs = []
            # toaddrs.append(self.manage_user.login)
            # toaddrs = ['al@neotel-technology.com','luna.zhang@acctronics.cn']
            toaddrs = ['al@neotel-technology.com']
            # toaddrs = ['jie.dong@acctronics.cn']
            subjects = "采购单{}需要您审批,请及时处理".format(self.name)
            message = "采购单{}<br><br>标题：{}<br><br>供应商：{}<br><br>支付条款：{}<br><br>总价：{}<br><br><br>需要您审批,请及时处理<br><br><br>谢谢".format(self.name,self.title,self.partner_id.name,self.payment_rule,self.amount_total)
            self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
            self.activity_unlink()
            user_ids = self.pre_userids(toaddrs)
            self.send_mailactivity(user_ids)
        else:
            self.write({'state': 'boss'})
            activity_addrs = ['luna.zhang@neotel-technology.com','cissy.shen@neotel-technology.com']
            toaddrs = ['luna.zhang@neotel-technology.com']
            toaddrs.append(self.charge_person.login)
            # toaddrs = ['jie.dong@acctronics.cn','yapeng.dai@acctronics.cn']
            subjects = "采购单{}已审批完成,请及时确认".format(self.name)
            message = "采购单{}<br><br>标题：{}<br><br>供应商：{}<br><br>支付条款：{}<br><br>总价：{}<br><br><br>管理部审批完成,请及时处理<br><br><br>谢谢".format(self.name,self.title,self.partner_id.name,self.payment_rule,self.amount_total)
            self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
            self.activity_unlink()
            user_ids = self.pre_userids(activity_addrs)
            self.send_mailactivity(user_ids)
        return True

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

    # @api.onchange('delivery_time')
    # def onchange_delivery_time(self):
    #     if self.delivery_time:
    #         delivery_time = self.delivery_time
    #         length = len(str(delivery_time))
    #         if length == 4:
    #             delivery_num = int(delivery_time[2])
    #             unit = delivery_time[3]
    #             if unit == '周':
    #                 days = delivery_num * 7
    #             elif unit == '天':
    #                 days = delivery_num
    #             else:
    #                 raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
    #         elif length == 8:
    #             delivery_num = int(delivery_time[2])
    #             unit = delivery_time[3:]
    #             if unit == 'weeks':
    #                 days = delivery_num * 7
    #             else:
    #                 raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
    #         elif length == 7:
    #             delivery_num = int(delivery_time[2])
    #             unit = delivery_time[3:]
    #             if unit == 'days':
    #                 days = delivery_num
    #             else:
    #                 raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
    #         else:
    #             raise ValidationError("请填写格式正确的货期,如(1-2周,1-2weeks,1-2天，1-2days)")
    #         forcast_date = datetime.now().date()
    #         date = forcast_date + dt.timedelta(days=days)
    #         self.forcast_date = date

    @api.onchange('charge_person')
    def onchange_en_name(self):
        if self.charge_person:
            login_en_name = 0
            login = self.charge_person.login
            login_index = login.index('@')
            login_en_name = login[0:login_index]
            self.en_name = login_en_name

    @api.onchange('forcast_date')
    def onchange_forcast_date(self):
        if self.forcast_date:
            for line in self.order_line:
                line.update({'forcast_date':self.forcast_date})


    @api.multi
    def _fresh_po_state(self):
        # purchase_orders = self.env['purchase.order'].search([('state', '=', 'purchase'),('payment_state', '!=', 'allpay'),('product_state', '!=', 'all')])
        purchase_orders = self.env['purchase.order'].search([('state', '=', 'purchase'),('date_order', '>', '2018-12-20 00:00:00')])
        for order in purchase_orders:
            invoices = order.mapped('invoice_ids')
            if not invoices:
                order.write({'payment_state':'nopay'})
            else:
                invoices_total = 0.0
                for invoice in invoices:
                    if invoice.state == 'paid':
                        invoices_total += invoice.amount_total
                if invoices_total == 0:
                    order.write({'payment_state':'nopay'})
                if invoices_total < order.amount_total:
                    order.write({'payment_state':'partpay'})
                if invoices_total == order.amount_total:
                    order.write({'payment_state':'allpay'})
            cr = self.env.cr
            # location_ids = []
            receive_qty_sql = """ SELECT
                                SUM (product_qty) AS product_qty,
                                sum (qty_received) as qty_received,
                                sum (product_qty-qty_received) as compare
                            FROM
                                purchase_order_line
                            WHERE
                                order_id = %s"""%(order.id)
            # now_qty = cr.execute(now_qty_sql, (location_id,p_id))
            cr.execute(receive_qty_sql)
            result = request.cr.dictfetchall()
            if not result[0]['qty_received']:
                order.write({'product_state':'new'})
            if result[0]['qty_received'] and result[0]['compare'] > 0:
                order.write({'product_state':'part'})
            if result[0]['compare'] == 0:
                order.write({'product_state':'all'})
            # if result[0]['qty_received'] == 0 and result[0]['compare'] > 0:
            #     order.write({'product_state':'new'})
            # if result[0]['qty_received'] != 0 and not result[0]['compare']:
            #     order.write({'product_state':'all'})
            # if result[0]['qty_received'] != 0 and result[0]['compare'] > 0:
            #     order.write({'product_state':'part'})
            # onway_qty = line.onway_qty()
            # line.write({'now_qty':now_qty,'purchase_qty':onway_qty})
        return True


    # @api.onchange('charge_person')
    # def onchange_en_name(self):
    #     if self.charge_person:
    #         login_en_name = 0
    #         login = self.charge_person.login
    #         login_index = login.index('@')
    #         login_en_name = login[0:login_index]
    #         self.en_name = login_en_name
    #         
    # @api.multi
    # def check_office_price(self,vals):
    #     raise_tips = ""
    #     if vals.get('purchase_type') == 'office':
    #         order_line = vals.get('order_line')
    #         for line in order_line:
    #             product_id = line[2]['product_id']
    #             product_object = self.env['product.product'].search([('id', '=', product_id)])
    #             product_tmpl_obj = self.env['product.template'].search([('id', '=', product_object.product_tmpl_id.id)])
    #             product_price = product_tmpl_obj.acc_purchase_price
    #             # product_price = line.product_id.product_tmpl_id.acc_purchase_price
    #             product_name = product_tmpl_obj.name
    #             actual_price = line[2]['price_unit']
    #             if actual_price > product_price:
    #                 raise_tips = "所填产品名称 {}，填写价格{} 产品采购定价{},所填价格高于定价，请检查".format(product_name, actual_price,product_price)
    #                 # raise ValidationError("所填产品价格高于产品定价，请检查")
    #                 raise ValidationError(raise_tips)
        # if self.purchase_type == 'office' and vals.get('order_line'):
        #     order_line = vals.get('order_line')
        #     for line in order_line:
        #         product_id = line[2]['product_id']
        #         product_object = self.env['product.product'].search([('id', '=', product_id)])
        #         product_tmpl_obj = self.env['product.template'].search([('id', '=', product_object.product_tmpl_id.id)])
        #         product_price = product_tmpl_obj.acc_purchase_price
        #         # product_price = line.product_id.product_tmpl_id.acc_purchase_price
        #         product_name = product_tmpl_obj.name
        #         actual_price = line[2]['price_unit']
        #         if actual_price > product_price:
        #             raise_tips = "所填产品名称 {}，填写价格{} 产品采购定价{},所填价格高于定价，请检查".format(product_name, actual_price,product_price)
        #             # raise ValidationError("所填产品价格高于产品定价，请检查")
        #             raise ValidationError(raise_tips)
    @api.model
    def create(self,vals):
        # if vals.get('order_line'):
        #     self.check_office_price(vals)
        amount = vals.get('amount_total',0) + vals.get('ship_fee',0) - vals.get('discount_amount',0)
        vals.update({
                "amount_total": amount
            })
        res = super(CFTemplateCategory, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        # if self.purchase_type == 'office':
        #     self.check_office_price(vals)
        if vals.get('minus_amount'):
            amount = self.amount_untaxed + self.amount_tax - vals.get('minus_amount', 0)
            vals.update({
                    "amount_total": amount
                })
        if vals.get('discount_rate'):
            rate_amount = self.amount_untaxed * vals.get('discount_rate')/100
            amount = self.amount_untaxed + self.amount_tax - rate_amount
            vals.update({
                    "amount_total": amount
                })  
        res = super(CFTemplateCategory, self).write(vals)
        return res

    @api.multi
    def button_confirm(self):
        if self.origin_order:
            so = self.env['sale.order'].search([('id', '=', self.origin_order.id)])
            so.write({'send_date':fields.Datetime.now(),'is_send':True})
        res = super(CFTemplateCategory,self).button_confirm()
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

    def save_exel(self, header, body, file_name):
        wbk = xlwt.Workbook(encoding='utf-8', style_compression=0)
        # wbk.write(codecs.BOM_UTF8)
        style1 = xlwt.easyxf('font: bold True;''alignment: horz center,vert center')
        sheet = wbk.add_sheet('sheet1', cell_overwrite_ok=True)
        # sheet.write(codecs.BOM_UTF8) 

        sheet.write(0, 0, 'some text')
        sheet.write(0, 0, 'this should overwrite')  ##重新设置，需要cell_overwrite_ok=True
        n = 0
        for i in range(len(header)):
            sheet.write(n, i, header[i])
        for i in range(len(body)):
            n += 1
            for j in range(len(body[i])):
                # sheet.write(n, j, body[i][j], self.set_style())
                sheet.write(n, j, body[i][j])
        wbk.save(file_name)  ##该文件名必须存在

    def export_record(self,file_name):
        """
        导出采购单信息
        :return:
        """
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/work/files_export?file=%s' % (file_name),
            'target': 'self'
        }

    def export_purchase_record(self):
        cr = self.env.cr
        # if not product_state and not payment_state:
        all_total = """ SELECT
                            ru. LOGIN AS apply_person,
                            po. NAME AS apply_code,
                            po.title AS project_name,
                            pt.brand AS brand,
                            pt. NAME AS product_name,
                            pt.acc_code AS acc_code,
                            pt.partner_code AS partner_code,
                            pt.product_model AS product_model,
                            pol.product_qty AS qty,
                            rp. NAME AS supplier,
                            pol.forcast_date AS forcast_date
                        FROM
                            purchase_order_line pol
                        LEFT JOIN purchase_order po ON po. ID = pol.order_id
                        LEFT JOIN product_product pp ON pp. ID = pol.product_id
                        LEFT JOIN res_partner rp ON rp. ID = po.partner_id
                        LEFT JOIN product_template pt ON pt. ID = pp.product_tmpl_id
                        LEFT JOIN res_users ru ON ru. ID = po.charge_person
                        WHERE
                          order_id = %s """%(self.id)
        cr.execute(all_total)
        result = cr.dictfetchall()
        detail_list_all=[]

        # print result
        # strftime("%Y%m%d_%H%M%S")
        i= 0
        for line in result:
            detail_list_first = []
            i += 1
            # print ((line.get('create_date').strftime("%Y-%m-%d %H:%M:%S"))[0:11])
            detail_list_first.append(i)
            detail_list_first.append(line.get('apply_person'))
            detail_list_first.append(line.get('apply_code'))
            detail_list_first.append(line.get('project_name'))
            detail_list_first.append(line.get('brand'))
            detail_list_first.append(line.get('product_name'))
            detail_list_first.append(line.get('acc_code'))
            detail_list_first.append(line.get('partner_code'))
            detail_list_first.append(line.get('product_model'))
            detail_list_first.append(line.get('qty'))
            detail_list_first.append(line.get('supplier'))
            if line.get('forcast_date'):
                detail_list_first.append(line.get('forcast_date').strftime("%Y-%m-%d"))
            else:
                detail_list_first.append(line.get('forcast_date'))
            detail_list_all.append(detail_list_first)

        dir_path = os.path.join(file_url, 'Administrator')
        filename = "{}.xls".format('询价单明细表')
        file_path = os.path.join(dir_path, filename)
        check_path(file_path)
        head = ['序号', '负责人','单号','标题','品牌','产品名称','产品编码','供应商编码','产品型号','数量','供应商','预计到货日期']
        self.save_exel(head, detail_list_all, file_path)
        return self.export_record(file_path)

    def update_newinfo(self):
        cr = self.env.cr
        # if not product_state and not payment_state:
        sql = """ UPDATE purchase_order_line
                        SET partner_code = (
                            SELECT
                                product_product.partner_code
                            FROM
                                product_product
                            WHERE
                                product_product. ID = purchase_order_line.product_id
                        ),
                            name = (
                            SELECT
                                product_product.product_model
                            FROM
                                product_product
                            WHERE
                                product_product. ID = purchase_order_line.product_id
                        ),
                            price_unit = (
                            SELECT
                                product_product.acc_purchase_price
                            FROM
                                product_product
                            WHERE
                                product_product. ID = purchase_order_line.product_id
                        ),
                            acc_code = (
                            SELECT
                                product_product.acc_code
                            FROM
                                product_product
                            WHERE
                                product_product. ID = purchase_order_line.product_id
                        )
                        where order_id = %s """%(self.id)
        cr.execute(sql)
        for p in self.order_line:
            p._compute_amount()

    # def _get_responsible_for_approval(self):
    #     if self.user_id:
    #         return self.user_id
    #     elif self.employee_id.parent_id.user_id:
    #         return self.employee_id.parent_id.user_id
    #     elif self.employee_id.department_id.manager_id.user_id:
    #         return self.employee_id.department_id.manager_id.user_id
    #     return self.env.user


    # def activity_update(self):
    #     self.activity_schedule(
    #         'acct_purchase.mail_act_purchase_order_approve',
    #         user_id=10)

    def send_notification(self, message,activity):
        # self.env['mail.message'].create({'message_type': "notification",
        #                                  "subtype": self.env.ref("mail.mt_comment").id,
        #                                  # "model":self._name,
        #                                  # "res_id":self.id, 
        #                                  'body': message,
        #                                  'subject': "采购单通知",
        #                                  'needaction_partner_ids': [(4,38650)],
        #                                  # partner to whom you send notification
        #                                  })
        self.message_post(
            subject='PO',
            body=message,
            partner_ids=activity.user_id.partner_id.ids
        )

    def send_mailactivity(self,user_ids):
        date_deadline = fields.Date.context_today(self)
        model_id = self.env['ir.model']._get(self._name).id
        message = '采购审批通知'
        for user_id in user_ids:
            create_vals = {
                'activity_type_id': 15,
                'summary': '采购审批',
                'automated': True,
                'note': '<p>采购审批</p>',
                'date_deadline': date_deadline,
                'res_model_id': model_id,
                'res_id': self.id,
                'user_id':user_id,
                'res_name':self.name,
            }
            activities = self.env['mail.activity'].create(create_vals)
            self.send_notification(message,activities)
        return True

    def activity_unlink(self):
        """ Unlink activities, limiting to some activity types and optionally
        to a given user. """
        # if self.env.context.get('mail_activity_automation_skip'):
        #     return False

        # Data = self.env['ir.model.data'].sudo()
        # activity_types_ids = [Data.xmlid_to_res_id(xmlid) for xmlid in act_type_xmlids]
        domain = [
            '&', '&', '&',
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('automated', '=', True),
            ('activity_type_id', '=', 15)
            # ('user_id', '=', unlinkuser_id)
        ]
        # if user_id:
        #     domain = ['&'] + domain + [('user_id', '=', user_id)]
        self.env['mail.activity'].search(domain).unlink()
        return True


class AccPurchaseLine(models.Model):
    """
    采购单继承
    """
    _inherit = "purchase.order.line"

    acc_code = fields.Char(string='产品编码')
    partner_code = fields.Char(string='供应商编码')
    # forcast_date = fields.Date(string='预计到货时间',compute='_compute_date',inverse="_inverse_compute_date",store=True)
    # f_date = fields.Date(string='预计到货时间')
    forcast_date = fields.Date(string='预计到货时间')
    # forcast_date = fields.Date(string='预计到货时间')

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        res = super(AccPurchaseLine, self)._onchange_quantity()
        # your logic here
        for rec in self:
            rec.price_unit = self.product_id.product_tmpl_id.acc_purchase_price
            rec.name = self.product_id.product_tmpl_id.product_model
            rec.acc_code = self.product_id.product_tmpl_id.acc_code
            rec.partner_code = self.product_id.product_tmpl_id.partner_code
        return res

    # @api.depends('order_id.forcast_date')
    # def _compute_date(self):
    #     for line in self:
    #         date = line.order_id.forcast_date
    #         line.update({'forcast_date':date})

    # @api.one
    # def _inverse_compute_date(self):
    #     self.f_date = self.forcast_date

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

class PurchasePayrecordLine(models.Model):
    """
    付款记录
    """
    _name = 'purchase.payrecord.line'
    # _inherit = ['mail.thread']
    _description = "付款记录"

    purchase_payrecord_id = fields.Many2one('purchase.order', 'account Reference')
    pay_amount = fields.Float(u'金额')
    pay_datetime = fields.Datetime(string='时间')
    pay_user = fields.Many2one('res.users',string='操作人')




