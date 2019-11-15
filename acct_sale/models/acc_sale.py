# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
from odoo.http import request
import logging
import xlrd
from collections import Counter
import re
import xlwt
import sys,os
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

    @api.depends('quotation_line.price_subtotal')
    def _amount_quo_all(self):
        for order in self:
            if order.tax_id:
                tax_rate = order.tax_id.amount/100
            else:
                tax_rate = 1
            quo_amount_total = 0.0
            quo_amount_untaxed = 0.0
            quo_amount_tax = 0.0
            for line in order.quotation_line:
                quo_amount_untaxed += line.price_subtotal
                quo_amount_tax += line.price_subtotal * tax_rate
            order.update({
                'quo_amount_untaxed':quo_amount_untaxed,
                'quo_amount_tax':quo_amount_tax,
                'quo_amount_total': quo_amount_untaxed + quo_amount_tax,
            })

    title = fields.Char(string=u'标题', required=True)
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('confirm', '已提交审批'),
        ('sent', 'Quotation Sent'),
        # ('boss', '管理部已审核'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', track_sequence=3, default='draft')
    crm_sonumber = fields.Char(string=u'老销售单号',readonly=True)
    bomupdate_time = fields.Datetime(string=u'物料变更最新操作时间',readonly=True)
    partner_ponumber = fields.Char(string=u'客户po号')
    charge_person = fields.Many2one('res.users',string=u'负责人',default=lambda self: self.env.user.id,required=True)
    contact_id = fields.Many2one('res.partner',string='联系人')
    transfer = fields.Char(string='承运人')
    delivery_time = fields.Char(string=u'货期',placeholder="填写格式如(1周,1weeks,1天，1days)")
    origin_country = fields.Char(string="货物原产国及厂家")
    port_shipment = fields.Char(string="发货机场")
    destination_port = fields.Char(string="目的机场")
    destination_address = fields.Char(string="交货地址")
    shipping_method = fields.Char(string="运输方式")
    sale_commission = fields.Float(string='销售佣金')
    in_country = fields.Boolean(string='是否为国内订单')
    is_invoice = fields.Boolean(string='是否开票',readonly=True)
    is_makepo = fields.Boolean(string='是否生成采购单',default=True)
    purchase_charge_person = fields.Many2one('res.users',string='采购负责人',required=True)
    is_purchasing = fields.Boolean(string='是否开始采购',readonly=True)
    purchase_date = fields.Datetime(string='开始采购时间',readonly=True)
    is_send = fields.Boolean(string='是否发货',readonly=True)
    send_date = fields.Datetime(string='发货时间',readonly=True)
    is_pay = fields.Boolean(string='是否收款',readonly=True)
    wait_change = fields.Selection([('no', '需变更'), ('yes', '无需变更')],default='yes', string='物料变更',readonly=True)
    send_status = fields.Selection([('no', '未发货'), ('yes', '已发货'), ('part', '部分发货')], '发货情况')
    transaction_mode = fields.Many2one('transaction.rule',string='交易方式')
    transaction_rule = fields.Char(string='交易条款')
    tax_id = fields.Many2one('account.tax', string='税', domain=['|', ('active', '=', False), ('active', '=', True)])
    # validity_date = fields.Date(string='有效期至')
    sale_company = fields.Many2one('acc.company',string = '卖方公司')
    po_number = fields.Char(string='关联的采购单',readonly=True,copy=False)
    before_purchase_id = fields.Many2one('before.purchase',string='待确认生成询价单',copy=False)
    origin_sale_order_id = fields.Many2one('sale.order',string='源销售单',copy=False)
    acc_quotation_id = fields.Many2one('acc.quotation',string='关联报价单',copy=False)
    quo_amount_untaxed = fields.Float(string='未含税金额', store=True, readonly=True, compute='_amount_quo_all', track_visibility='always')
    quo_amount_tax = fields.Float(string='税', store=True, readonly=True, compute='_amount_quo_all')
    quo_amount_total = fields.Float(string='总计', store=True, readonly=True, compute='_amount_quo_all')
    # quo_amount_untaxed = fields.Float(string='未含税金额')
    # quo_amount_tax = fields.Float(string='税')
    # quo_amount_total = fields.Float(string='总计')
    bom_line = fields.One2many('sale.bom.line', 'salebom_id', 'Bom Lines',readonly=True)
    quotation_line = fields.One2many('quotation.line', 'quotation_id','Quotation Lines')



    def search(self, args, offset=0, limit=None, order=None, count=False):
        args = args or []
        if self._uid == 2:
            return super(AccSaleOrder, self).search(args, offset, limit, order, count)
        # 管理部门
        elif self.env.user.has_group('acct_base.acc_manage_level1_group'):
            return super(AccSaleOrder, self).search(args, offset, limit, order, count)
        # 销售部经理
        elif self.env.user.has_group('acct_base.unovo_it_info_group'):
            uids = self.get_department(self._uid)
            args.extend([('user_id', 'in', uids)])
            return super(AccSaleOrder, self).search(args, offset, limit, order, count)
        # 普通员工
        else:
            args.extend([('user_id', '=', self._uid)])
        return super(AccSaleOrder, self).search(args, offset, limit, order, count)

    @api.multi
    def get_department(self,user_id):
        department_ids = []
        employee_id = self.env['hr.employee'].search([('user_id', '=', user_id)])
        department_id = self.env['hr.department'].search([('manager_id', '=', employee_id.id)])
        if department_id:
            for did in department_id:
                department_ids.append(did.id)
            # department_name = department_id.name
            # if department_name in ['销售一部','销售二部','销售三部']:
            uids = self.make_sale_uid(department_ids,user_id)
            return uids


    @api.multi
    def make_sale_uid(self,department_ids,user_id):
        all_ids = []
        cr = self.env.cr
        all_total = """ SELECT
                            ru.id as uid
                        FROM
                            hr_employee he
                        LEFT JOIN res_users ru ON he.user_id = ru. ID
                        WHERE
                            department_id in %s """
        # cr.execute(all_total)
        cr.execute(all_total, (tuple(department_ids),))
        result = cr.dictfetchall()
        for line in result:
            all_ids.append(line['uid'])
        all_ids.append(user_id)
        return tuple(all_ids)

    @api.multi
    def bom_record(self,mrp_bom,qty):
        vals = {
                    'salebom_id':self.id,
                    'mrp_bom_id':mrp_bom.id,
                    'gen_date':fields.Datetime.now(),
                    'code':mrp_bom.code,
                    'product_qty':qty,
                    'acc_type':mrp_bom.acc_type,
                    # 'is_active':mrp_bom.active,
            }
        bom_line = self.env['sale.bom.line'].create(vals)
        return True

    @api.multi
    def check_eco_products(self):
        res_line = []
        mrp_ecos = []
        # add_ids = []
        remove_ids = []
        if self.bom_line:
            for bom in self.bom_line:
                mrp_eco = self.env['mrp.eco'].search([('bom_id', '=', bom.mrp_bom_id.id),('state', '=', 'done')])
                if mrp_eco:
                    mrp_eco.write({'is_use':'on'})
                    mrp_ecos.append(mrp_eco.id)
                    for change in mrp_eco.bom_change_ids:
                        if change.change_type == 'add':
                            # add_ids.append(change.product_id.id)
                            line_vals = {
                              'order_id':self.before_purchase_id.id,
                              'product_id':change.product_id.id,
                              'product_model':change.product_id.product_tmpl_id.product_model,
                              'qty':change.new_product_qty * bom.product_qty,
                              'acc_purchase_price':change.product_id.product_tmpl_id.acc_purchase_price,
                              'brand':change.product_id.product_tmpl_id.brand,
                              'acc_code':change.product_id.product_tmpl_id.acc_code,
                              'partner_code':change.product_id.product_tmpl_id.partner_code
                            }
                            res_line.append(line_vals)
                        if change.change_type == 'update' and change.upd_product_qty > 0:
                            # add_ids.append(change.product_id.id)
                            line_vals = {
                              'order_id':self.before_purchase_id.id,
                              'product_id':change.product_id.id,
                              'product_model':change.product_id.product_tmpl_id.product_model,
                              'qty':change.upd_product_qty * bom.product_qty,
                              'acc_purchase_price':change.product_id.product_tmpl_id.acc_purchase_price,
                              'brand':change.product_id.product_tmpl_id.brand,
                              'acc_code':change.product_id.product_tmpl_id.acc_code,
                              'partner_code':change.product_id.product_tmpl_id.partner_code
                            }
                            res_line.append(line_vals)
                        if change.change_type == 'remove':
                            remove_vals = {
                              'p_id':change.product_id.id,
                              'product_id':change.product_id.product_tmpl_id.name,
                              'product_model':change.product_id.product_tmpl_id.product_model,
                              'qty':change.upd_product_qty * bom.product_qty,
                              'brand':change.product_id.product_tmpl_id.brand,
                              'acc_code':change.product_id.product_tmpl_id.acc_code}
                            remove_ids.append(remove_vals)
                        if change.change_type == 'update' and change.upd_product_qty < 0:
                            remove_vals = {
                              'p_id':change.product_id.id,
                              'product_id':change.product_id.product_tmpl_id.name,
                              'product_model':change.product_id.product_tmpl_id.product_model,
                              'qty':change.upd_product_qty * bom.product_qty,
                              'brand':change.product_id.product_tmpl_id.brand,
                              'acc_code':change.product_id.product_tmpl_id.acc_code}
                            remove_ids.append(remove_vals)
                    # if not res_line[0]:
                    #     raise ValidationError('没有需要增补的物料！！！')
        if not self.bom_line:
            raise ValidationError('因之前版本(6.28号之前的单据)未做bom记录,无法进行自动增补！！!')


        # products["add"] = res_line
        # products["remove"] = remove_ids
        return res_line,remove_ids,mrp_ecos

    @api.multi
    def add_new_bom(self):
        before_purchase = self.env['before.purchase'].search([('id', '=', self.before_purchase_id.id)])
        res_line,remove_ids,mrp_ecos = self.check_eco_products()
        if remove_ids:
            remove_products = []
            for p in remove_ids:
                po_name = self.get_poname(p)
                p_str = '物料名称:' + p['product_id'] + '  ' + '型号:' + p['product_model'] + '  ' + '品牌:' + p['brand'] + '  ' + '编码:' +  p['acc_code'] + ' ' + '移除数量:' + str(p['qty']) + '采购单号:' + po_name + '<br>'
                remove_products.append(p_str)
            toaddrs = []
            toaddrs.append(self.purchase_charge_person.login)
            # toaddrs = ['jie.dong@acctronics.cn']
            subjects = "源单据{}所申请物料清单有变动,请及时处理".format(self.name)
            message = "源单据{}所申请物料清单,有以下物料从物料清单中移除<br><br>{}".format(self.name,remove_products)
            self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        # self.check_res(res_line)
        if res_line:
            if before_purchase and before_purchase.state == 'draft':
                raise ValidationError('该销售订单所关联待确认询价单尚未完成，请完成后再进行物料清单变动操作')
            if before_purchase and before_purchase.state == 'done':
                new_res_line = []
                for line in res_line:
                    new_line_vals = {
                                'product_id':line['product_id'],
                                'product_model':line['product_model'],
                                'qty':line['qty'],
                                'acc_purchase_price':line['acc_purchase_price'],
                                'brand':line['brand'],
                                'acc_code':line['acc_code'],
                                'partner_code':line['partner_code'], 
                    }
                    new_res_line.append((0,0,new_line_vals))
                vals = {
                    'sale_order_id':self.id,
                    'purchase_company':self.sale_company.id,
                    # 'delivery_address':self.delivery_address.id,
                    'order_line':new_res_line
                }
                bp_obj = self.env['before.purchase'].create(vals)
                if mrp_ecos:
                    for ecoid in mrp_ecos:
                        eco_obj = self.env['mrp.eco'].browse(ecoid)
                        eco_obj.write({'before_purchase_id':bp_obj.id})
            # for remove_id in remove_ids:
            # 删除的东西怎么处理？
        self.change_bom_record()
            # self.write({'before_purchase_id':bp_obj.id})
            # 
            # 
    @api.multi
    def check_res(self,res_line):
        line = res_line
        if not line:
            raise ValidationError('没有需要增补的物料！！！')

    @api.multi
    def get_poname(self,p):
        product_id = p['p_id']
        purchase_orders = self.env['purchase.order'].search([('origin_order', '=', self.id)])
        po_ids = [tmp.id for tmp in purchase_orders]
        po_line = self.env['purchase.order.line'].search([('order_id', 'in', po_ids),('product_id', '=', product_id)])
        if po_line:
            # taget_order = self.env['purchase.order'].search([('id', '=', po_line.order_id)])
            taget_order = self.env['purchase.order'].browse(po_line[0].order_id.id)
            taget_poname = taget_order.name
        else:
            taget_poname = '无'
        return taget_poname




    @api.multi
    def change_bom_record(self):
        for bom_line in self.bom_line:
            bom_line.unlink()
        for line in self.order_line:
            product_tmpl_id = line.product_id.product_tmpl_id.id
            qty = line.product_uom_qty
            mrp_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', product_tmpl_id),('active', '=', True)])
            if mrp_bom:
                self.bom_record(mrp_bom,qty)
        now_time = fields.Datetime.now()
        self.write({'bomupdate_time':now_time,'wait_change':'yes'})

    @api.multi        
    def check_bom(self,line):
        product_tmpl_id = line.product_id.product_tmpl_id.id
        mrp_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', product_tmpl_id),('active', '=', True)])
        return mrp_bom
        
    def make_mrp_vals(self,mrp_bom,qty):       
        res_line = []
        for bom_line in mrp_bom.bom_line_ids:
            bom_line_vals = {
              'product_id':bom_line.product_id.id,
              'product_model':bom_line.product_id.product_tmpl_id.product_model,
              'qty':bom_line.product_qty * qty,
              'acc_purchase_price':bom_line.product_id.product_tmpl_id.acc_purchase_price,
              'brand':bom_line.product_id.product_tmpl_id.brand,
              'acc_code':bom_line.product_id.product_tmpl_id.acc_code,
              'partner_code':bom_line.product_id.product_tmpl_id.partner_code,
            }
        # res_line = [(0,0,bom_line_vals)]
            res_line.append((0,0,bom_line_vals))
        return res_line

    @api.multi        
    def create_before_po(self):
        res_line = []
        for line in self.order_line:
            mrp_bom = self.check_bom(line)
            if mrp_bom:
                qty = line.product_uom_qty
                self.bom_record(mrp_bom,qty)
                mrp_vals = self.make_mrp_vals(mrp_bom,qty)
                res_line += mrp_vals
            else:
                line_vals = {
                          'product_id':line.product_id.id,
                          'product_model':line.product_id.product_tmpl_id.product_model,
                          'qty':line.product_uom_qty,
                          'acc_purchase_price':line.product_id.product_tmpl_id.acc_purchase_price,
                          'brand':line.product_id.product_tmpl_id.brand,
                          'acc_code':line.product_id.product_tmpl_id.acc_code,
                          'partner_code':line.product_id.product_tmpl_id.partner_code
                }
                res_line.append((0,0,line_vals))
        vals = {
            'sale_order_id':self.id,
            'charge_person':self.purchase_charge_person.id,
            'purchase_company':self.sale_company.id,
            'order_line':res_line
        }
        bp_obj = self.env['before.purchase'].create(vals)
        self.write({'before_purchase_id':bp_obj.id})
        # toaddrs = ['jie.dong@acctronics.cn','cissy.shen@acctronics.cn','yuanyuan.lu@acctronics.cn']
        # toaddrs = []
        # toaddrs.append(bp_obj.charge_person.login)
        toaddrs = []
        toaddrs.append(bp_obj.charge_person.login)
        subjects = "待确认询价单{}".format(bp_obj.name)
        message = "待确认询价单{}已生成,请及时处理".format(bp_obj.name)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        return True
        
    
    @api.multi
    def action_confirm(self):
        res = super(AccSaleOrder, self).action_confirm()
        if self.is_makepo == True:
            self.create_before_po()
        return res

    @api.multi
    def confirm(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'confirm'})
        # toaddrs = []
        # toaddrs.append(self.manage_user.login)
        toaddrs = ['yuanyuan.lu@neotel-technology.com']
        # toaddrs = ['jie.dong@acctronics.cn','yapeng.dai@acctronics.cn']
        subjects = "销售单{}已提交需要您确认,请及时处理".format(self.name)
        message = "销售单{}已提交需要您确认,请及时处理".format(self.name)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        return True

    # @api.multi
    # def boss_accept(self):
    #     self.filtered(lambda r: r.state == 'confirm').write({'state': 'boss'})
    #     toaddrs = ['yuanyuan.lu@neotel-technology.com']
    #     # toaddrs = ['jie.dong@acctronics.cn','yapeng.dai@acctronics.cn']
    #     subjects = "销售单{}管理部已审批完成,请及时确认".format(self.name)
    #     message = "销售单{}管理部已审批完成,请及时确认".format(self.name)
    #     self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
    #     return True


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

class QuotationLine(models.Model):
    """
    报价单明细
    """
    _name = 'quotation.line'
    # _inherit = ['mail.thread']
    _description = "报价单明细"

    quotation_id = fields.Many2one('sale.order', 'Order Reference')
    product_qty = fields.Float(u'数量', required=True)
    product_id = fields.Many2one('product.product',u'物料名称',required=True)
    product_model = fields.Char(string='规格型号')
    acc_code = fields.Char(string='产品编码')
    description = fields.Char(string='产品描述')
    # 'default_code': fields.char(u'参考编号'),
    product_uom = fields.Many2one('uom.uom', string='单位')
    price_unit = fields.Float(u'单价')
    price_subtotal = fields.Float(compute='_compute_amount',string='小计',store=True)
    # price_total = fields.Monetary(compute='_compute_amount', string='总计', store=True)
    # 
    @api.onchange('product_id')
    def onchange_product_id(self):
        result = {}
        if not self.product_id:
            return result
        self.price_unit = self.product_qty = 0.0
        self.product_model = self.product_id.product_tmpl_id.product_model
        self.description = self.product_id.product_tmpl_id.product_describe_cn
        self.acc_code = self.product_id.product_tmpl_id.acc_code
        self.product_uom = self.product_id.product_tmpl_id.uom_id
        return result

    @api.depends('product_qty', 'price_unit')
    def _compute_amount(self):
        price_subtotal = 0.00
        for line in self:
            price_subtotal = line.price_unit * line.product_qty
            line.update({
                'price_subtotal': price_subtotal,
            })

class SaleBomLine(models.Model):
    _name = 'sale.bom.line'
    _description = "物料清单记录"

    salebom_id = fields.Many2one('sale.order', '销售单')
    mrp_bom_id = fields.Many2one('mrp.bom',string='物料清单')
    code = fields.Char(string='参考')
    product_qty = fields.Float(string='数量')
    acc_type = fields.Selection([('change', '可变'), ('base', '基础'),('standard','标准')], '内部类型')
    gen_date = fields.Datetime(string='时间')
    # is_active = fields.Boolean(string='有效')

class AccQuotation(models.Model):
    """
    挚锦报价单
    """
    _name = 'acc.quotation'
    _inherit = ['mail.thread']
    _description = "挚锦报价单"
    _order = 'gen_date desc'


    @api.multi
    def unlink(self):
        for quotation in self:
            if quotation.state == 'done':
                raise ValidationError('不能删除已完成的挚锦报价单.')
        return super(AccQuotation,self).unlink()

    @api.model
    def create(self,vals):
        if not vals.get('name',''):
            last_name = self.env['ir.sequence'].get('acc.quotation') or ''
            vals['name'] = "%s"%(last_name)
        result = super(AccQuotation,self).create(vals)
        return result


    @api.depends('accquotation_line.price_subtotal')
    def _amount_all(self):
        for order in self:
            if order.tax_id:
                tax_rate = order.tax_id.amount/100
            else:
                tax_rate = 1
            amount_total = 0.0
            amount_untaxed = 0.0
            amount_tax = 0.0
            for line in order.accquotation_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_subtotal * tax_rate
            order.update({
                'amount_untaxed':amount_untaxed,
                'amount_tax':amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })



    name = fields.Char(string=u'名称',readonly=True,index=True, copy=False, default='New')
    pricelist_id = fields.Many2one('product.pricelist',string='价格表',required=True)
    title = fields.Char(string=u'标题', required=True)
    gen_date = fields.Date(string=u'单据日期',default=lambda self: self._context.get('date', fields.Date.context_today(self)),readonly=True)
    last_date = fields.Date(string="最后修改日期",readonly = True)
    customer_state = fields.Selection([('nowcreate', '已创建'),('sent', '已发送'),('refuse', '已拒绝'),('cancel', '已取消')], '报价单状态', copy=False, default='nowcreate')
    user_id = fields.Many2one('res.users',string=u'负责人',default=lambda self: self.env.user.id,required=True)
    partner_id = fields.Many2one('res.partner',string='客户')
    contact_id = fields.Many2one('res.partner',string='联系人')
    transfer = fields.Char(string='承运人')
    sale_commission = fields.Float(string='销售佣金')
    delivery_time = fields.Char(string=u'货期',placeholder="填写格式如(1周,1weeks,1天，1days)")
    in_country = fields.Boolean(string='是否为国内订单')
    currency_id = fields.Many2one('res.currency', '币种', required=True,
        default=lambda self: self.env.user.company_id.currency_id.id)
    crm_lead_id = fields.Many2one('crm.lead',string='商机',readonly=True)
    # is_makepo = fields.Boolean(string='是否生成采购单',default=True)
    purchase_charge_person = fields.Many2one('res.users',string='采购负责人',required=True)
    # is_purchasing = fields.Boolean(string='是否开始采购',readonly=True)
    # purchase_date = fields.Datetime(string='开始采购时间',readonly=True)
    # is_send = fields.Boolean(string='是否发货',readonly=True)
    # send_date = fields.Datetime(string='发货时间',readonly=True)
    # is_pay = fields.Boolean(string='是否收款',readonly=True)
    discount = fields.Float(string='折扣',default=0.00)
    ship_fee = fields.Float(string='运费',default=0.00)
    state = fields.Selection([('draft', '草稿'),('sent', '已发送'),('done', '完成'),('cancel', '取消')], '状态', default='draft')
    transaction_mode = fields.Many2one('transaction.rule',string='交易方式')
    transaction_rule = fields.Char(string='交易条款')
    # validity_date = fields.Date(string='有效期至')
    sale_company = fields.Many2one('acc.company',string = '卖方公司')
    tax_id = fields.Many2one('account.tax', string='税', domain=['|', ('active', '=', False), ('active', '=', True)])
    amount_untaxed = fields.Float(string='未含税金额', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    amount_tax = fields.Float(string='税', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Float(string='总计', store=True, readonly=True, compute='_amount_all')
    sale_order = fields.Many2one('sale.order',string='关联的销售单',copy=False,readonly=True)
    # before_purchase_id = fields.Many2one('before.purchase',string='待确认生成询价单')
    accquotation_line = fields.One2many('accquotation.line', 'accquotation_id', 'Quotation Lines',copy=True)
    log_line = fields.One2many('log.line', 'log_id', 'Log Lines',readonly=True)


    @api.multi        
    def create_so(self):
        res_line = []
        for line in self.accquotation_line:
            # mrp_bom = self.check_bom(line)
            line_vals = {
                      'product_id':line.product_id.id,
                      'product_model':line.product_model,
                      'acc_code':line.acc_code,
                      'description':line.description,
                      'product_uom':line.product_uom.id,
                      'price_unit':line.price_unit,
                      'product_qty':line.product_qty
            }
            res_line.append((0,0,line_vals))
        vals = {
            'partner_id':self.partner_id.id,
            'acc_quotation_id':self.id,
            'contact_id':self.contact_id.id,
            'pricelist_id':self.pricelist_id.id,
            'title':self.title,
            'transfer':self.transfer,
            'sale_commission':self.sale_commission,
            'in_country':self.in_country,
            'purchase_charge_person':self.purchase_charge_person.id,
            'transaction_mode':self.transaction_mode.id,
            'transaction_rule':self.transaction_rule,
            'sale_company':self.sale_company.id,
            'tax_id':self.tax_id.id,
            # 'quo_amount_tax':self.amount_tax,
            # 'quo_amount_untaxed':self.amount_untaxed,
            # 'quo_amount_total':self.amount_total,
            'quotation_line':res_line
        }
        so_obj = self.env['sale.order'].create(vals)
        self.write({'sale_order':so_obj.id,'state':'done'})
        # toaddrs = ['jie.dong@acctronics.cn','cissy.shen@acctronics.cn']
        # # toaddrs = []
        # # toaddrs.append(bp_obj.charge_person.login)
        # subjects = "待确认询价单{}".format(so_obj.name)
        # message = "待确认询价单{}已生成,请及时处理".format(so_obj.name)
        # self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        return True

    @api.multi
    def cancel(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'cancel','customer_state': 'cancel'})
        return True

    @api.multi
    def draft_sent(self):
        self.filtered(lambda r: r.state == 'sent').write({'state': 'draft','customer_state': 'nowcreate'})
        return True
    @api.multi
    def cancel_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft','customer_state': 'nowcreate'})
        return True

    @api.multi
    def sent(self):
        contact_name = self.contact_id.name
        contact_mobile = self.contact_id.mobile
        contact_title = self.contact_id.title.name
        topic = self.title
        if not contact_mobile:
            raise ValidationError('联系人未填手机号，请填写联系人手机号')
        if not contact_title:
            raise ValidationError('联系人称呼未正确配置！')
        ret = re.match(r"^1[35678]\d{9}$", contact_mobile)
        if not ret:
            raise ValidationError('联系人手机号填写格式不正确！')
        text = contact_name + contact_title + '您好，' +'“' + topic + '”' + '报价单已发到您邮件，请注意查收，谢谢'
        vals = {
                'topic':topic,
                'user_name':contact_name,
                'phone':contact_mobile,
                'name':text
        }
        message = self.env['acc.message.interface'].create(vals)
        message.sms_send()
        self.filtered(lambda r: r.state == 'draft').write({'state': 'sent','customer_state': 'sent'})
        return True


    @api.multi
    def write(self, vals):
        vals['last_date'] = fields.Date.context_today(self)
        res = super(AccQuotation, self).write(vals)
        # self.last_date = fields.Date.context_today(self)
        if vals.get('accquotation_line'):
            q_vals = {
                    'log_id':self.id,
                    'user_id':self.user_id.id,
                    'gen_date':fields.Datetime.now(),
                    'amount_total':self.amount_total,
            }
            log = self.env['log.line'].create(q_vals)
        return res


class AccquotationLine(models.Model):
    """
    报价单明细
    """
    _name = 'accquotation.line'
    # _inherit = ['mail.thread']
    _description = "报价单明细"

    accquotation_id = fields.Many2one('acc.quotation', 'Order Reference')
    product_qty = fields.Float(u'数量', required=True)
    product_id = fields.Many2one('product.product',u'物料名称',required=True)
    product_model = fields.Char(string='规格型号')
    acc_code = fields.Char(string='产品编码')
    description = fields.Char(string='产品描述')
    # 'default_code': fields.char(u'参考编号'),
    product_uom = fields.Many2one('uom.uom', string='单位')
    price_unit = fields.Float(u'单价')
    price_subtotal = fields.Float(compute='_compute_amount',string='小计',store=True)
    # price_total = fields.Monetary(compute='_compute_amount', string='总计', store=True)
    # 
    @api.onchange('product_id')
    def onchange_product_id(self):
        result = {}
        if not self.product_id:
            return result
        self.price_unit = self.product_qty = 0.0
        self.product_model = self.product_id.product_tmpl_id.product_model
        self.description = self.product_id.product_tmpl_id.product_describe_cn
        self.acc_code = self.product_id.product_tmpl_id.acc_code
        self.product_uom = self.product_id.product_tmpl_id.uom_id
        return result

    @api.depends('product_qty', 'price_unit')
    def _compute_amount(self):
        price_subtotal = 0.00
        for line in self:
            price_subtotal = line.price_unit * line.product_qty
            line.update({
                'price_subtotal': price_subtotal,
            })

class LogLine(models.Model):
    """
    修改日志
    """
    _name = 'log.line'
    # _inherit = ['mail.thread']
    _description = "挚锦报价单明细"

    log_id = fields.Many2one('acc.quotation', 'Log')
    user_id = fields.Many2one('res.users',u'修改人',required=True)
    gen_date = fields.Datetime(string=u'修改日期',default=lambda self: fields.Datetime.now(),readonly=True)
    amount_total = fields.Float(string='修改金额')