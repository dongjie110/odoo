#coding=utf-8
from odoo import models,fields,api, _
import datetime
import logging
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)

class MergeBomWizard(models.TransientModel):
    _name = "merge.bom.wizard"


    product_tmpl_id = fields.Many2one('product.template',string='合并为')
    code = fields.Char(string=u'参考')
    bom_ids = fields.Many2many('mrp.bom','bom_merge_rel',string=u"物料清单")
    mrp_bom_id = fields.Many2one('mrp.bom',readonly=True,string='合并物料清单')

    def merge_bom_order(self):
        merge_tips = ""
        mrp_bom = self.bom_ids
        # list_ids = self.compare_partners(mrp_bom)
        list_ids,merge_info = self.get_merge_info(mrp_bom)
        cr = self.env.cr
        cr.execute("""
                    SELECT
                        product_id AS pid,
                        SUM (product_qty) AS qty,
                        product_uom_id,
                        product_model,
                        brand,
                        acc_code
                    FROM
                        mrp_bom_line
                    WHERE
                        bom_id IN %s
                    GROUP BY
                        product_id,
                        product_uom_id,
                        product_model,
                        acc_code,
                        brand
                        """% (tuple(list_ids),)
                        )
        result = cr.dictfetchall()
        self.create_bom(result,merge_info)
            # merge_tips = "被合并单号为{},生成新单号为{}".format(po_name,po_obj.name)
        # raise ValidationError(merge_tips)
        # except Exception as e:
        #     logging.error(e)
        # else:
        #     raise ValidationError(merge_tips)

    @api.multi
    def create_bom(self,result,merge_info):
        res_line = []
        for line in result:
            line_vals = {
                  'product_id':line['pid'],
                  'product_model':line['product_model'],
                  'product_qty':line['qty'],
                  'acc_code':line['acc_code'],
                  'brand':line['brand'],
                  'product_uom_id':line['product_uom_id']
                    }
            # res_line = [(0,0,line_vals)]
            res_line.append((0,0,line_vals))
        bom_vals = {
                'product_tmpl_id':self.product_tmpl_id.id,
                'code':self.code,
                'type':'normal',
                'product_qty':1,
                'merge_info':merge_info,
                'bom_line_ids':res_line
        }
        mrp_obj = self.env['mrp.bom'].create(bom_vals)
        # subject = '提醒信息'
        # merge_tips = "被合并单号为{},生成新单号为{}".format(po_name,po_obj.name)
        self.write({'mrp_bom_id':mrp_obj.id})
        # return self.message_post(body=merge_tips, subject=subject)          
        return True


    # def compare_partners(self,purchase_order):
    #     partner_list = []
    #     list_ids = []
    #     po_name = []
    #     for order in purchase_order:
    #         partner_list.append(order.partner_id.id)
    #         list_ids.append(order.id)
    #         po_name.append(order.name)
    #     if len(set(partner_list)) > 1:
    #         raise ValidationError(u'所选询价单供应商不一致,不能合并！！！')
        # if len(list_ids) <= 1:
        #     raise ValidationError(u'合并时至少选择两个询价单！！！')
    #     else:
    #         return list_ids,po_name

    def get_merge_info(self,order):
        merge_info = ""
        bom_name = []
        list_ids = []
        for line in order:
            bom_name.append(line.product_tmpl_id.name)
            list_ids.append(line.id)
        if len(list_ids) <= 1:
            raise ValidationError(u'合并时至少选择两个物料清单！！！')
        merge_info = "被合并物料清单{}".format(bom_name)
        return list_ids,merge_info
