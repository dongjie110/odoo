#coding=utf-8
from odoo import models,fields,api, _
import datetime
import logging
from odoo.exceptions import UserError, ValidationError
_logger = logging.getLogger(__name__)

class RecreateBeforePurchase(models.TransientModel):
    _name = "recreate.before.purchase"


    charge_person = fields.Many2one('res.users',string=u'负责人')

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
