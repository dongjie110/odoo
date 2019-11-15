# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
import odoo.tools.config as config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
import smtplib
import logging
import time
_logger = logging.getLogger(__name__)

class DemandPurchase(models.Model):
    """
    请购单
    """
    _name = 'demand.purchase'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "请购单"
    _order = 'apply_date desc'


    @api.model
    def create(self,vals):
        if not vals.get('name',''):
            last_name = self.env['ir.sequence'].get('demand.purchase') or ''
            vals['name'] = "%s"%(last_name)
        result = super(DemandPurchase,self).create(vals)
        return result


    @api.depends('order_line.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

    name = fields.Char(string=u'名称',readonly=True)
    # purchase_order_id = fields.Many2one('purchase.order',string='相关采购单',readonly=True)
    po_number = fields.Char(string='关联采购单',readonly=True)
    charge_person = fields.Many2one('res.users',string='采购负责人',required=True)
    create_user = fields.Many2one('res.users', u'申请人', readonly=True,default=lambda self: self.env.user.id)
    manage_user = fields.Many2one('res.users', u'部门主管')
    apply_date = fields.Datetime(string=u'申请日期',default=lambda self: fields.Datetime.now(),readonly=True)
    bomupdate_time = fields.Datetime(string=u'物料变更最新操作时间',readonly=True)
    need_date = fields.Date(string=u'需求日期')
    partner_id = fields.Many2one('res.partner',string=u'供应商')
    purchase_type = fields.Selection([('new', '未到货'), ('part', '部分到货'), ('all', '全部到货'), ('cancel', '取消订单')], '产品到货状态', default='new')
    web_address = fields.Char(string=u'链接地址')
    purchase_company = fields.Many2one('acc.company',string='采购公司')
    note = fields.Text(string=u'备注')
    internal_note = fields.Char(string=u'内部备注')
    state = fields.Selection([('draft', '草稿'), ('confirmed', '审批中'), ('done', '完成'),('cancel', '取消')], '状态', default='draft',track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', '币种', required=True,
        default=lambda self: self.env.user.company_id.currency_id.id)
    delivery_address = fields.Many2one('delivery.address',string='交货地址')
    before_purchase_id = fields.Many2one('before.purchase',string='待确认生成询价单')
    amount_untaxed = fields.Monetary(string='未含税金额', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    amount_tax = fields.Monetary(string='税', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='总计', store=True, readonly=True, compute='_amount_all')
    order_line = fields.One2many('demand.purchase.line', 'order_id', 'Order Lines')
    bom_line = fields.One2many('demand.bom.line', 'demand_id', 'Bom Lines',readonly=True)


    def search(self, args, offset=0, limit=None, order=None, count=False):
        args = args or []
        if self._uid == 2:
            return super(DemandPurchase, self).search(args, offset, limit, order, count)
        # 管理部门
        elif self.env.user.has_group('acct_base.acc_manage_level1_group'):
            return super(DemandPurchase, self).search(args, offset, limit, order, count)
        # 销售部经理
        # elif self.env.user.has_group('acct_base.unovo_it_info_group'):
        #     uids = self.get_department(self._uid)
        #     args.extend([('user_id', 'in', uids)])
        #     return super(DemandPurchase, self).search(args, offset, limit, order, count)
        # 普通员工
        else:
            uids = self.get_department(self._uid)
            args.extend([('create_user', 'in', uids)])
        return super(DemandPurchase, self).search(args, offset, limit, order, count)

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
            uids = self.make_uid(department_ids,user_id)
        else:
            uids = (self._uid,)
        return uids


    @api.multi
    def make_uid(self,department_ids,user_id):
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
    def draft_button(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'confirmed'})
        toaddrs = []
        toaddrs.append(self.manage_user.login)
        # toaddrs = ['jie.dong@acctronics.cn','cissy.shen@acctronics.cn']
        # toaddrs = ['jie.dong@acctronics.cn','yapeng.dai@acctronics.cn']
        subjects = "请购单{}需要您审批,请及时处理".format(self.name)
        message = "请购单{}需要您审批,请及时处理".format(self.name)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        return True

    @api.multi
    def cancel(self):
        self.filtered(lambda r: r.state == 'confirmed').write({'state': 'cancel'})
        return True

    @api.multi
    def reject(self):
        self.filtered(lambda r: r.state == 'confirmed').write({'state': 'cancel'})
        return True

    @api.multi
    def cancel_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        return True

    @api.onchange('create_user')
    def _onchange_manage_user(self):
        # self.address_id = self.employee_id.sudo().address_home_id
        employee_id = self.env['hr.employee'].search([('user_id', '=', self.create_user.id)])
        self.manage_user = employee_id.expense_manager_id or employee_id.parent_id.user_id

    @api.multi
    def unlink(self):
        for demand in self:
            if demand.state == 'done':
                raise ValidationError('不能删除已完成的请购单.')
        return super(DemandPurchase,self).unlink()

    @api.multi
    def make_acccode(self):
        pt = self.env['product.template'].search([])
        n = 1
        for i in pt:  
            s = "%05d" % n
            code = 'ACC-PRO-' + s 
            i.write({'acc_code':code})
            n += 1
            print (i.name)
            _logger.debug('===========%s===============', i.name)


    # @api.onchange('note')
    # def onchange_delivery_time(self):
    #     if self.note:
    #         note = self.note
    #         # for i in delivery_time:
    #         #     nums = int(i[2])
    #         # if self.internal_type == 'liquidity':
    #         self.web_address = note
    #     # return True

    @api.multi
    def approve(self):
        self.create_before_po()
        self.filtered(lambda r: r.state == 'confirmed').write({'state': 'done'})
        # self.bom_record()
        return True

    @api.multi
    def bom_record(self,mrp_bom,qty):
        vals = {
                    'demand_id':self.id,
                    'mrp_bom_id':mrp_bom.id,
                    'gen_date':fields.Datetime.now(),
                    'code':mrp_bom.code,
                    'product_qty':qty,
                    'acc_type':mrp_bom.acc_type,
                    # 'is_active':mrp_bom.active,
            }
        bom_line = self.env['demand.bom.line'].create(vals)
        return True

    @api.multi
    def check_eco_products(self):
        res_line = []
        # products = {}
        # add_ids = []
        remove_ids = []
        # minus_upd_product = []
        if self.bom_line:
            for bom in self.bom_line:
                mrp_eco = self.env['mrp.eco'].search([('bom_id', '=', bom.mrp_bom_id.id),('state', '=', 'done')])
                if mrp_eco:
                    mrp_eco.write({'is_use':'on'})
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
                # 更新物料增补操作时间
        if not self.bom_line:
            raise ValidationError('因之前版本(6.28号之前的单据)未做bom记录,无法进行自动增补！！!')
        return res_line,remove_ids

    @api.multi
    def add_new_bom(self):
        before_purchase = self.env['before.purchase'].search([('id', '=', self.before_purchase_id.id)])
        res_line,remove_ids = self.check_eco_products()
        if remove_ids:
            remove_products = []
            for p in remove_ids:
                # product_obj = self.env['product.product'].browse(p)
                # p_str = '物料名称:' + product_obj.product_tmpl_id.name + '  ' + '型号:' + product_obj.product_tmpl_id.product_model + '  ' + '品牌:' + product_obj.product_tmpl_id.brand + '  ' + '编码:' +  product_obj.product_tmpl_id.acc_code
                p_str = '物料名称:' + p['product_id'] + '  ' + '型号:' + p['product_model'] + '  ' + '品牌:' + p['brand'] + '  ' + '编码:' +  p['acc_code'] + ' ' + '移除数量:' + str(p['qty']) + '<br>'
                remove_products.append(p_str)
            toaddrs = []
            toaddrs.append(self.charge_person.login)
            # toaddrs = ['jie.dong@acctronics.cn']
            subjects = "源单据{}所申请物料清单有变动,请及时处理".format(self.name)
            message = "源单据{}所申请物料清单,有以下物料从物料清单中移除<br><br>{}".format(self.name,remove_products)
            self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
            # self.change_bom_record()
        # self.check_res(res_line)
        if res_line:
            if before_purchase and before_purchase.state == 'draft':
                for new_vals in res_line:
                    self.env['before.purchase.line'].create(new_vals)
                for remove_id in remove_ids:
                    before_purchase_line = self.env['before.purchase.line'].search([('product_id', '=', remove_id['p_id']),('order_id', '=', before_purchase.id)])
                    if before_purchase_line:
                        before_purchase_line.unlink()
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
                    'demand_purchase_id':self.id,
                    'purchase_company':self.purchase_company.id,
                    'delivery_address':self.delivery_address.id,
                    'charge_person':self.charge_person.id,
                    'order_line':new_res_line
                }
                bp_obj = self.env['before.purchase'].create(vals)
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
    def change_bom_record(self):
        for bom_line in self.bom_line:
            bom_line.unlink()
        for line in self.order_line:
            product_tmpl_id = line.product_id.product_tmpl_id.id
            qty = line.product_qty
            mrp_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', product_tmpl_id),('active', '=', True)])
            if mrp_bom:
                self.bom_record(mrp_bom,qty)
        now_time = fields.Datetime.now()
        self.write({'bomupdate_time':now_time})

    @api.model
    def create(self, vals):
        if not vals.get('name',''):
            last_name = self.env['ir.sequence'].get('demand.purchase') or ''
            vals.update({'name':last_name})        
        result = super(DemandPurchase, self).create(vals)
        # toaddrs = []
        # toaddrs.append(result.charge_person.login)
        # subjects = "请购单{}已创建".format(result.name)
        # message = "请购单{}已创建请及时处理".format(result.name)
        # self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        return result

    @api.multi        
    def check_bom(self,line):
        product_tmpl_id = line.product_id.product_tmpl_id.id
        mrp_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', product_tmpl_id),('active', '=', True)])
        return mrp_bom
        
    def make_mrp_vals(self,mrp_bom,bom_qty):       
        res_line = []
        for bom_line in mrp_bom.bom_line_ids:
            bom_line_vals = {
              'product_id':bom_line.product_id.id,
              'product_model':bom_line.product_id.product_tmpl_id.product_model,
              'qty':bom_line.product_qty * bom_qty,
              'acc_purchase_price':bom_line.product_id.product_tmpl_id.acc_purchase_price,
              'brand':bom_line.product_id.product_tmpl_id.brand,
              'acc_code':bom_line.product_id.product_tmpl_id.acc_code,
              'partner_code':bom_line.product_id.product_tmpl_id.partner_code
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
                bom_qty = line.product_qty
                self.bom_record(mrp_bom,bom_qty)
                mrp_vals = self.make_mrp_vals(mrp_bom,bom_qty)
                res_line += mrp_vals
            else:
                line_vals = {
                          'product_id':line.product_id.id,
                          'product_model':line.product_id.product_tmpl_id.product_model,
                          'qty':line.product_qty,
                          'acc_purchase_price':line.product_id.product_tmpl_id.acc_purchase_price,
                          'brand':line.product_id.product_tmpl_id.brand,
                          'acc_code':line.product_id.product_tmpl_id.acc_code,
                          'partner_code':line.product_id.product_tmpl_id.partner_code
                }
                res_line.append((0,0,line_vals))
        vals = {
            'demand_purchase_id':self.id,
            'purchase_company':self.purchase_company.id,
            'delivery_address':self.delivery_address.id,
            'charge_person':self.charge_person.id,
            'order_line':res_line
        }
        bp_obj = self.env['before.purchase'].create(vals)
        self.write({'before_purchase_id':bp_obj.id})
        toaddrs = []
        toaddrs.append(bp_obj.charge_person.login)
        # toaddrs = []
        # toaddrs.append(bp_obj.charge_person.login)
        subjects = "待确认询价单{}".format(bp_obj.name)
        message = "待确认询价单{}已生成,请及时处理".format(bp_obj.name)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        return True


class DemandPurchaseLine(models.Model):
    _name = 'demand.purchase.line'
    _description = "请购单明细"
    _order = 'create_date desc, id desc'


    order_id = fields.Many2one('demand.purchase', 'Order Reference')
    name = fields.Char(u'规格描述')
    product_qty = fields.Float(u'需求数量',digits=dp.get_precision('Product Unit of Measure'), required=True)
    product_id = fields.Many2one('product.product',u'物料名称',domain=[('purchase_ok', '=', True)], required=True)
    # 'default_code': fields.char(u'参考编号'),
    product_uom = fields.Many2one('uom.uom', string='单位', required=True)
    price_unit = fields.Float(u'单价', digits_compute=dp.get_precision('Product Price'))
    partner_id = fields.Many2one('res.partner', related='order_id.partner_id', string='供应商', readonly=True, store=True)
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='币种', readonly=True)
    taxes_id = fields.Many2many('account.tax', string='税', domain=['|', ('active', '=', False), ('active', '=', True)])
    price_subtotal = fields.Monetary(compute='_compute_amount', string='小计', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='总计', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='税', store=True)

    @api.depends('product_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            vals = line._prepare_compute_all_values()
            taxes = line.taxes_id.compute_all(
                vals['price_unit'],
                vals['currency_id'],
                vals['product_qty'],
                vals['product'],
                vals['partner'])
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    def _prepare_compute_all_values(self):
        # Hook method to returns the different argument values for the
        # compute_all method, due to the fact that discounts mechanism
        # is not implemented yet on the purchase orders.
        # This method should disappear as soon as this feature is
        # also introduced like in the sales module.
        self.ensure_one()
        return {
            'price_unit': self.price_unit,
            'currency_id': self.order_id.currency_id,
            'product_qty': self.product_qty,
            'product': self.product_id,
            'partner': self.order_id.partner_id,
        }

    @api.onchange('product_id')
    def onchange_product_id(self):
        result = {}
        if not self.product_id:
            return result

        # Reset date, price and quantity since _onchange_quantity will provide default values
        # self.date_planned = datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.price_unit = self.product_qty = 0.0
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        product_lang = self.product_id.with_context(
            lang=self.partner_id.lang,
            partner_id=self.partner_id.id,
        )
        # self.name = product_lang.display_name
        self.name = self.product_id.product_tmpl_id.product_model
        if product_lang.description_purchase:
            self.name += '\n' + product_lang.description_purchase

        return result

class DemandBomLine(models.Model):
    _name = 'demand.bom.line'
    _description = "物料清单记录"

    demand_id = fields.Many2one('demand.purchase', '请购单')
    mrp_bom_id = fields.Many2one('mrp.bom',string='物料清单')
    code = fields.Char(string='参考')
    product_qty = fields.Float(string='数量')
    acc_type = fields.Selection([('change', '可变'), ('base', '基础'),('standard','标准')], '内部类型')
    gen_date = fields.Datetime(string='时间')
    is_active = fields.Boolean(string='有效')

# 交货地址
class DeliveryAddress(models.Model):
    """
    交货地址
    """
    _name = 'delivery.address'
    _inherit = ['mail.thread']
    _description = "交货地址"

    name = fields.Char(string='详细地址',required=True)
    charge = fields.Char(string='收货人',required=True)
    phone = fields.Char(string='联系电话',required=True)
    active = fields.Boolean(string='有效',default=True)

# 公司
class AccCompany(models.Model):
    """
    公司
    """
    _name = 'acc.company'
    _inherit = ['mail.thread']
    _description = "锐驰公司"

    name = fields.Char(string='公司名',required=True)
    logo = fields.Binary(string="中文Logo", required=True,readonly=False)
    en_logo = fields.Binary(string="英文Logo", required=True,readonly=False)
    qr_code = fields.Binary(string="二维码",required=True,readonly=False)
    vat = fields.Char(string="纳税人识别号")
    bank = fields.Char(string="开户行")
    bank_number = fields.Char(string='账号')
    active = fields.Boolean(string='有效',default=True)
