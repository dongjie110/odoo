# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request

class DemandPurchase(models.Model):
    """
    请购单
    """
    _name = 'demand.purchase'
    _inherit = ['mail.thread']
    _description = "请购单"


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
    purchase_order_id = fields.Many2one('purchase.order',string='相关采购单',readonly=True)
    create_user = fields.Many2one('res.users', u'申请人', readonly=True,default=lambda self: self.env.user.id)
    apply_date = fields.Datetime(string=u'申请日期',default=lambda self: fields.Datetime.now(),readonly=True)
    need_date = fields.Date(string=u'需求日期')
    partner_id = fields.Many2one('res.partner',string=u'供应商')
    purchase_type = fields.Selection([('accessories', '辅料'), ('office', '办公'), ('other', '其他')], '产品到货状态', default='accessories')
    web_address = fields.Char(string=u'链接地址')
    note = fields.Text(string=u'备注')
    state = fields.Selection([('draft', '草稿'), ('confirmed', '审批中'), ('done', '完成')], '状态', default='draft')
    currency_id = fields.Many2one('res.currency', '币种', required=True,
        default=lambda self: self.env.user.company_id.currency_id.id)
    amount_untaxed = fields.Monetary(string='未含税金额', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    amount_tax = fields.Monetary(string='税', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='总计', store=True, readonly=True, compute='_amount_all')
    order_line = fields.One2many('demand.purchase.line', 'order_id', 'Order Lines')

    @api.multi
    def draft_button(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'confirmed'})
        return True

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
        self.create_po()
        self.filtered(lambda r: r.state == 'confirmed').write({'state': 'done'})
        return True

    def create_po(self):
        res = []
        for line in self.order_line:
            line_vals = {
                      'product_id':line.product_id.id,
                      'name':line.name,
                      'product_qty':line.product_qty,
                      'price_unit':line.price_unit,
                      'taxes_id':line.taxes_id,
                      'date_planned':fields.Datetime.now(),
                      'product_uom':line.product_id.uom_id.id
            }
            res.append((0,0,line_vals))
        po_vals = {
                'partner_id':self.partner_id.id,
                'title':self.name,
                'charge_person':self.create_user.id,
                'traffic_rule':' ',
                'payment_rule':' ',
                'demand_purchase':self.id,
                'order_line':res
        }
        po_obj = self.env['purchase.order'].create(po_vals)
        if po_obj:
            self.write({'purchase_order_id':po_obj.id})
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
        self.name = product_lang.display_name
        if product_lang.description_purchase:
            self.name += '\n' + product_lang.description_purchase

        return result

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
    logo = fields.Binary(string="Company Logo", readonly=False)
    active = fields.Boolean(string='有效',default=True)