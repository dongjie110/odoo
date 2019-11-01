#coding=utf-8
from odoo import models,fields,api, _
import datetime
import logging
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)

class MergePurchaseWizard(models.TransientModel):
    _name = "merge.purchase.wizard"


    title = fields.Char(string=u'标题', required=True)
    charge_person = fields.Many2one('res.users',string=u'负责人',default=lambda self: self.env.user.id,required=True)
    purchase_type = fields.Selection([('trade', '贸易'), ('office', '办公用品'), ('manufacture', '生产'),('accessories', '辅料')],'采购类型',default='trade')
    traffic_rule = fields.Char(string=u'运输条款',required=True)
    payment_rule = fields.Char(string=u'支付条款',required=True)
    delivery_address = fields.Many2one('delivery.address',string='交货地址')
    purchase_company = fields.Many2one('acc.company',string='采购公司',required=True)
    purchase_ids = fields.Many2many('purchase.order','purchase_merge_rel',domain=[('state', '=', 'draft')],string=u"采购单")
    purchase_order_id = fields.Many2one('purchase.order',readonly=True,string='合并询价单')

    def merge_purchase_order(self):
        merge_tips = ""
        purchase_order = self.purchase_ids
        list_ids,po_name = self.compare_partners(purchase_order)
        merge_info = self.get_merge_info(purchase_order)
        cr = self.env.cr
        cr.execute("""
                    SELECT
                        product_id AS pid,
                        sum(product_qty) AS qty,
                        name,
                        price_unit,
                        product_uom,
                        acc_code,
                        partner_code
                    FROM
                        purchase_order_line
                    WHERE
                        order_id IN %s
                    GROUP BY
                        product_id,
                        name,
                        price_unit,
                        acc_code,
                        partner_code,
                        product_uom
                        """% (tuple(list_ids),)
                        )
        result = cr.dictfetchall()
        self.create_po(result,purchase_order,merge_info,po_name)
            # merge_tips = "被合并单号为{},生成新单号为{}".format(po_name,po_obj.name)
        # raise ValidationError(merge_tips)
        # except Exception as e:
        #     logging.error(e)
        # else:
        #     raise ValidationError(merge_tips)

    @api.multi
    def create_po(self,result,order,merge_info,po_name):
        res_line = []
        for line in result:
            line_vals = {
                  'product_id':line['pid'],
                  'name':line['name'],
                  'product_qty':line['qty'],
                  'price_unit':line['price_unit'],
                  'acc_code':line['acc_code'],
                  'partner_code':line['partner_code'],
                  'date_planned':fields.Datetime.now(),
                  'product_uom':line['product_uom']
                    }
            # res_line = [(0,0,line_vals)]
            res_line.append((0,0,line_vals))
        po_vals = {
                'partner_id':order[0].partner_id.id,
                'title':self.title,
                'purchase_company':self.purchase_company.id,
                'charge_person':self.charge_person.id,
                'forcast_date':fields.Datetime.now(),
                'date_planned':fields.Datetime.now(),
                'traffic_rule':self.traffic_rule,
                'payment_rule':self.payment_rule,
                # 'demand_purchase':self.demand_purchase_id.id,
                'merge_info':merge_info,
                'order_line':res_line
        }
        po_obj = self.env['purchase.order'].create(po_vals)
        # subject = '提醒信息'
        # merge_tips = "被合并单号为{},生成新单号为{}".format(po_name,po_obj.name)
        self.write({'purchase_order_id':po_obj.id})
        # return self.message_post(body=merge_tips, subject=subject)          
        return True


    def compare_partners(self,purchase_order):
        partner_list = []
        list_ids = []
        po_name = []
        for order in purchase_order:
            partner_list.append(order.partner_id.id)
            list_ids.append(order.id)
            po_name.append(order.name)
        if len(set(partner_list)) > 1:
            raise ValidationError(u'所选询价单供应商不一致,不能合并！！！')
        if len(list_ids) <= 1:
            raise ValidationError(u'合并时至少选择两个询价单！！！')
        else:
            return list_ids,po_name

    def get_merge_info(self,order):
        merge_info = ""
        so_name = []
        de_name = []
        po_name = []
        for line in order:
            so_name.append(line.origin_order.name)
            de_name.append(line.demand_purchase.name)
            po_name.append(line.name)
            line.button_cancel()
        merge_info = "被合并单号{}被合并询价单源请购单号{},被合并询价单源销售订单号{}".format(po_name,de_name,so_name)
        return merge_info
