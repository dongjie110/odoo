#coding=utf-8
from odoo import models,fields,api, _
import datetime
import logging
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)

class AddPartner(models.TransientModel):
    _name = "add.partner"


    # product_tmpl_id = fields.Many2one('product.template',string='合并为')
    brand = fields.Char(string=u'品牌',required=True)
    # bom_ids = fields.Many2many('mrp.bom','bom_merge_rel',string=u"物料清单")
    partner_id = fields.Many2one('res.partner',string='选择供应商',required=True)

    @api.multi
    def choose_partner(self):
        brand = self.brand
        partner_id = self.partner_id
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        # if active_id:
        #     before_model = self.env['before.purchase'].browse(active_id)
        #     for line in before_model.order_line:
        #         if line.brand == brand:
        #             line.write()
        if active_id:
            cr = self.env.cr
            cr.execute("""
                        UPDATE before_purchase_line
                        SET partner_id = %s
                        WHERE
                            brand = '%s'
                        AND order_id = %s
                            """% (partner_id.id,brand,active_id)
                            )
        return True
