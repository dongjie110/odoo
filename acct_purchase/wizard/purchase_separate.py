#coding=utf-8
from odoo import models,fields,api, _
import datetime
import logging
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)

class PurchaseSeparate(models.TransientModel):
    _name = "purchase.separate"


    # product_tmpl_id = fields.Many2one('product.template',string='合并为')
    pay_rate = fields.Float(string=u'付款比例(%)',required=True)
    pay_amount = fields.Float(string=u'付款金额')
    # bom_ids = fields.Many2many('mrp.bom','bom_merge_rel',string=u"物料清单")
    # partner_id = fields.Many2one('res.partner',string='选择供应商',required=True)

    @api.multi
    def create_bill(self):
        pay_rate = self.pay_rate
        # partner_id = self.partner_id
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        if active_id:
            active_model = self.env['purchase.order'].browse(active_id)
            if active_model.paid_rate + pay_rate > 100:
                raise ValidationError("已付款比例和本次付款比例之和超过100%，请核对后重新输入！")
            paid_rate = active_model.paid_rate + pay_rate
            active_model.write({'pay_rate':pay_rate})
            result = active_model.action_view_invoice()
            active_model.write({'paid_rate':paid_rate})
        return result

    @api.onchange('pay_amount')
    def onchange_pay_amount(self):
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        active_model = self.env['purchase.order'].browse(active_id)
        order_amount = active_model.amount_total
        if self.pay_amount:
            pay_rate = 0.0
            if self.pay_amount <= 0:
                raise ValidationError("付款金额只能填入大于0的金额")
            pay_rate = (self.pay_amount/order_amount)*100
            self.pay_rate = pay_rate
