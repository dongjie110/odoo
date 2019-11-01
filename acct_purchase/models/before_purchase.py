# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request
from odoo.exceptions import UserError, ValidationError

class BeforePurchase(models.Model):
    """
    待确认供应商询价单
    """
    _name = 'before.purchase'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "待确认供应商询价单"
    _order = 'gen_datetime desc'

    @api.model
    def create(self,vals):
        if not vals.get('name',''):
            last_name = self.env['ir.sequence'].get('before.purchase') or ''
            vals['name'] = "%s"%(last_name)
        result = super(BeforePurchase,self).create(vals)
        return result


    name = fields.Char(string='名称')
    sale_order_id = fields.Many2one('sale.order',string='源销售单')
    demand_purchase_id = fields.Many2one('demand.purchase',string='源请购单')
    charge_person = fields.Many2one('res.users',string='采购负责人')
    gen_datetime = fields.Datetime(string='生成时间',default=lambda self: fields.Datetime.now(),)
    po_number = fields.Text(string='关联的采购单',readonly=True)
    purchase_company = fields.Many2one('acc.company',string='采购公司',required=True)
    delivery_address = fields.Many2one('delivery.address',string='交货地址')
    state = fields.Selection([('draft', '待确认'), ('done', '已确认'),('cancel', '已取消')], '状态', default='draft',track_visibility='onchange')
    order_line = fields.One2many('before.purchase.line', 'order_id', 'Order Lines')


    @api.multi
    def draft_button(self):
        self.create_po()
        self.filtered(lambda r: r.state == 'draft').write({'state': 'done'})
        return True

    @api.multi
    def draft_cancel(self):
        # self.create_po()
        self.filtered(lambda r: r.state == 'draft').write({'state': 'cancel'})
        return True

    @api.multi
    def unlink(self):
        for before in self:
            if before.state in ('draft','done'):
                raise ValidationError('不能删除该单据.')
        return super(BeforePurchase,self).unlink()

    @api.multi        
    def create_po(self):
        res_line = []
        for line in self.order_line:
            product_partner_id = line.partner_id.id
            if not product_partner_id:
                raise UserError(u'有产品未选择供应商供应商')
            exits_order = self.compare_partner_id(line)
            line_vals = {
                      'product_id':line.product_id.id,
                      'name':line.product_model,
                      'product_qty':line.qty,
                      'price_unit':line.acc_purchase_price,
                      'acc_code':line.acc_code,
                      'date_planned':fields.Datetime.now(),
                      'product_uom':line.product_id.uom_id.id,
                      'partner_code':line.partner_code
            }
            res_line = [(0,0,line_vals)]
            po_vals = {
                    'partner_id':line.partner_id.id,
                    'title':self.name,
                    'before_purchase_id':self.id,
                    'purchase_company':self.purchase_company.id,
                    'charge_person':self.charge_person.id,
                    'forcast_date':fields.Datetime.now(),
                    'date_planned':fields.Datetime.now(),
                    'delivery_address':self.delivery_address.id,
                    'traffic_rule':' ',
                    'payment_rule':' ',
                    'demand_purchase':self.demand_purchase_id.id,
                    'origin_order':self.sale_order_id.id,
                    'order_line':res_line
            }
            if not exits_order:
                po_obj = self.env['purchase.order'].create(po_vals)
                self.add_ponumber(po_obj)
            if exits_order:
                exits_order.write({'order_line':res_line})
            # self.write({'purchase_date':fields.Datetime.now(),'is_purchasing':True})
            # if exits_order:
        return True

    @api.multi
    def compare_partner_id(self,line):
        supply_partner_id = line.partner_id.id
        if self.demand_purchase_id:
            exits_order = self.env['purchase.order'].search([('partner_id', '=', supply_partner_id),('demand_purchase', '=', self.demand_purchase_id.id),('title', '=', self.name)])
        else:
            exits_order = self.env['purchase.order'].search([('partner_id', '=', supply_partner_id),('origin_order', '=', self.sale_order_id.id),('title', '=', self.name)])
        return exits_order

    @api.multi
    def add_ponumber(self,pobj):
        new_po_name = ''
        po_name = pobj.name
        if self.demand_purchase_id:
            po_number = self.demand_purchase_id.po_number
            if po_number:
                new_po_name = po_number + ',' + po_name
            else:
                new_po_name = po_name
            demand_purchase = self.env['demand.purchase'].search([('id', '=', self.demand_purchase_id.id)])
            demand_purchase.write({'po_number':new_po_name})
            self.write({'po_number':new_po_name})
        if self.sale_order_id:
            po_number = self.sale_order_id.po_number
            if po_number:
                new_po_name = po_number + ',' + po_name
            else:
                new_po_name = po_name
            sale_order = self.env['sale.order'].search([('id', '=', self.sale_order_id.id)])
            sale_order.write({'po_number':new_po_name})
            self.write({'po_number':new_po_name})


    def merge_before_line(self):
        order_id = self.id
        # list_ids = self.compare_partners(mrp_bom)
        # list_ids,merge_info = self.get_merge_info(mrp_bom)
        cr = self.env.cr
        cr.execute("""
                    SELECT
                        product_id AS product_id,
                        SUM (qty) AS qty,
                        partner_code,
                        product_model,
                        brand,
                        acc_code,
                        partner_id
                    FROM
                        before_purchase_line
                    WHERE
                        order_id = %s
                    GROUP BY
                        product_id,
                        partner_code,
                        product_model,
                        acc_code,
                        brand,
                        partner_id
                        """% (order_id)
                        )
        result = cr.dictfetchall()
        self.create_newline(result)

    @api.multi
    def create_newline(self,result):
        for move in self.order_line:
            move.unlink()
        # res_line = []
        for line in result:
            line_vals = {
                  'order_id':self.id,
                  'product_id':line['product_id'],
                  'partner_id':line['partner_id'],
                  'product_model':line['product_model'],
                  'qty':line['qty'],
                  'acc_code':line['acc_code'],
                  'brand':line['brand'],
                  'partner_code':line['partner_code']
                    }
            # res_line = [(0,0,line_vals)]
            # res_line.append((0,0,line_vals))
            self.env['before.purchase.line'].create(line_vals)
        # subject = '提醒信息'
        # merge_tips = "被合并单号为{},生成新单号为{}".format(po_name,po_obj.name)
        # self.write({'mrp_bom_id':mrp_obj.id})
        # return self.message_post(body=merge_tips, subject=subject)          
        return True

class BeforePurchaseLine(models.Model):
    _name = 'before.purchase.line'
    _description = " 待确认询价单明细"
    _order = 'create_date desc, id desc'

    order_id = fields.Many2one('before.purchase', 'Order Reference')
    product_id = fields.Many2one('product.product',u'物料名称', required=True)
    product_model = fields.Char(string='规格描述')
    brand = fields.Char(string='品牌')
    acc_code = fields.Char(string='产品编码')
    partner_code = fields.Char(string='供应商编码')
    acc_purchase_price= fields.Char(string='采购价格')
    qty = fields.Float(string='数量')
    partner_id = fields.Many2one('res.partner',string='供应商',domain=[('supplier', '=', True)])