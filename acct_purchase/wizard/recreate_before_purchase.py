#coding=utf-8
from odoo import models,fields,api, _
import datetime
import logging
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)

class RecreateBeforePurchase(models.TransientModel):
    _name = "recreate.before.purchase"


    charge_person = fields.Many2one('res.users',string=u'负责人')
    # product_id = fields.Many2one('product.product',string=u'产品')
    partner_id = fields.Many2one('res.partner',string=u'供应商',required=True)
    order_line = fields.One2many('recreate.before.purchase.line', 'order_id', 'Order Lines')

    @api.multi
    def re_create(self):
        # product_id = self.product_id.id
        # partner_id = self.partner_id
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        active_model = self.env['before.purchase'].browse(active_id)
        # lines = self.env['before.purchase.line'].search([('order_id', '=', active_id),('product_id', '=', product_id)])
        # products = self.env['product.product'].browse(product_id)
        res_line = []
        update_line = []
        for line in self.order_line:
            # lines = self.env['before.purchase.line'].search([('order_id', '=', active_id),('product_id', '=', line.product_id.id)])
            line_vals = {
                      'product_id':line.product_id.id,
                      'name':line.product_id.product_model,
                      'product_qty':line.qty,
                      'price_unit':line.product_id.acc_purchase_price,
                      'acc_code':line.product_id.acc_code,
                      'date_planned':fields.Datetime.now(),
                      'product_uom':line.product_id.uom_id.id,
                      'partner_code':line.product_id.partner_code
            }
            log_line_vals = {
                      'product_id':line.product_id.id,
                      'product_model':line.product_id.product_model,
                      'qty':line.qty,
                      'partner_id':self.partner_id.id,
                      'acc_code':line.product_id.acc_code,
                      # 'date_planned':fields.Datetime.now(),
                      'brand':line.product_id.brand,
                      'partner_code':line.product_id.partner_code
            }
            # _logger.debug('===========%s===============', line.qty)
            res_line.append((0,0,line_vals))
            update_line.append((0,active_id,log_line_vals))
        po_vals = {
                'partner_id':self.partner_id.id,
                'title':active_model.name,
                'before_purchase_id':active_id,
                'purchase_company':active_model.purchase_company.id,
                'charge_person':active_model.charge_person.id,
                'forcast_date':fields.Datetime.now(),
                'date_planned':fields.Datetime.now(),
                'delivery_address':active_model.delivery_address.id,
                'traffic_rule':' ',
                'payment_rule':' ',
                'demand_purchase':active_model.demand_purchase_id.id,
                'origin_order':active_model.sale_order_id.id,
                'is_excipients':active_model.is_excipients,
                'order_line':res_line
        }
        po_obj = self.env['purchase.order'].create(po_vals)
        # recreate_vals = {
        #           'before_id':active_id,
        #           'product_id':product_id,
        #           'brand':products.brand,
        #           'product_model':products.product_model,
        #           'product_qty':lines.qty,
        #           'partner_id':self.partner_id.id,
        #           # 'price_unit':products.acc_purchase_price,
        #           'acc_code':products.acc_code,
        #           # 'date_planned':fields.Datetime.now(),
        #           'product_uom':products.uom_id.id,
        #           'partner_code':products.partner_code
        # }
        _logger.debug('===========%s===============', update_line)
        active_model.write({'recreate_line':update_line})
        return True

class RecreateBeforePurchaseLine(models.TransientModel):
    _name = 'recreate.before.purchase.line'
    _description = " 重新生成待确认明细行"
    _order = 'create_date desc, id desc'

    order_id = fields.Many2one('recreate.before.purchase', 'Order Reference')
    product_id = fields.Many2one('product.product',u'物料名称', required=True)
    product_model = fields.Char(string='规格描述')
    brand = fields.Char(string='品牌')
    acc_code = fields.Char(string='产品编码')
    partner_code = fields.Char(string='供应商编码')
    acc_purchase_price= fields.Float(string='采购价格')
    qty = fields.Float(string='数量')
    # partner_id = fields.Many2one('res.partner',string='供应商',domain=[('supplier', '=', True)])
    # 
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            context = dict(self.order_id._context or {})
            active_id = context.get('active_id', False)
            active_model = self.env['before.purchase'].browse(active_id)
            lines = self.env['before.purchase.line'].search([('order_id', '=', active_id),('product_id', '=', self.product_id.id)])
            if lines:
                self.qty = lines[0].qty
            if not lines:
                raise ValidationError('源待确认询价单中没有这个物料，请确认后再进行操作!')
            self.partner_code = self.product_id.product_tmpl_id.partner_code
            self.brand = self.product_id.product_tmpl_id.brand
            # self.internal_des = self.product_id.product_tmpl_id.internal_des
            self.acc_code = self.product_id.product_tmpl_id.acc_code
            self.product_model = self.product_id.product_tmpl_id.product_model
            # self.uom_id = self.product_id.product_tmpl_id.uom_po_id
