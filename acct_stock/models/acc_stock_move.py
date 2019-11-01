# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
from odoo.http import request
import logging
import xlrd
from collections import Counter
import re
import datetime

import pytz

from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
# from datetime import datetime
# from ..controllers.common import localizeStrTime
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class AccStockMove(models.Model):
    """
     库存移动继承
    """
    _inherit = "stock.move"

    product_model = fields.Char(string=u'规格型号',related='product_id.product_model')
    acc_code = fields.Char(string=u'产品编码',related='product_id.acc_code')

class AccStockQuant(models.Model):
    """
     库存quant继承
    """
    _inherit = "stock.quant"

    product_model = fields.Char(string=u'规格型号',related='product_id.product_model')
    acc_code = fields.Char(string=u'产品编码',related='product_id.acc_code')

class AccStockPicking(models.Model):
    """
     库存移动继承
    """
    _inherit = "stock.picking"

    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        default=lambda self: self.env['stock.picking.type'].browse(self._context.get('default_picking_type_id')).default_location_dest_id, required=True,readonly=False,
        states={'done': [('readonly', True)]})
    # location_dest_id = fields.Many2one(
    #     'stock.location', "Destination Location",
    #     default=lambda self: self.env['stock.picking.type'].browse(self._context.get('default_picking_type_id')).default_location_dest_id,
    #     readonly=True, required=True,
    #     states={'draft': [('readonly', False)]})
    title = fields.Char(string='项目号')
    # actual_location_id = fields.Many2one('stock.location',string='实际存放库位')

    @api.multi
    def button_validate(self):
        res = super(AccStockPicking,self).button_validate()
        po_name = self.origin
        po_obj = self.env['purchase.order'].search([('name', '=', po_name)])
        qty_received = []
        product_qty = []
        if po_obj:
            for line in po_obj.order_line:
                qty_received.append(line.qty_received)
                product_qty.append(line.product_qty)
            if sum(qty_received) == 0:
                po_obj.write({'product_state':'new'})
            elif sum(qty_received) < sum(product_qty) and sum(qty_received) != 0:
                po_obj.write({'product_state':'part'})
            else:
                po_obj.write({'product_state':'all'})
        return res

    @api.one
    @api.depends('move_lines.date_expected')
    def _compute_scheduled_date(self):
        res = super(AccStockPicking,self)._compute_scheduled_date()
        pobj = self.env['purchase.order'].search([('name', '=', self.origin)])
        # 2019-07-25 08:49:17
        if pobj:
            forcast_date = str(pobj.forcast_date) + ' ' + '00:00:00'
            # date_time = datetime.datetime.strptime(forcast_date,'%Y-%m-%d') 
            f_date = datetime.datetime.strptime(forcast_date, "%Y-%m-%d %H:%M:%S")
            title = pobj.title
            self.scheduled_date = f_date
            self.write({'title':title})
            # self._compute_title()
        return res

    @api.onchange('location_dest_id')
    def onchange_location_dest_id(self):
        if self.location_dest_id:
            move_ids = []
            for line in self.move_ids_without_package:
                line.update({'location_dest_id':self.location_dest_id})
                move_ids.append(line.id)
            cr = self.env.cr
            change_sql = """ UPDATE stock_move_line
                            SET location_dest_id = %s
                            WHERE
                                move_id in %s """
            # cr.execute(all_total)
            cr.execute(change_sql, (self.location_dest_id.id,tuple(move_ids)))
    # def deal_update_add(self,product_id,mos,qty):
    #     cr = self.env.cr
    #     add_sql = """ UPDATE stock_move
    #                     SET product_uom_qty = product_uom_qty + %s
    #                     WHERE
    #                         raw_material_production_id = %s
    #                     AND product_id = %s """
    #     # cr.execute(all_total)
    #     cr.execute(add_sql, (qty,mos.id,product_id))

    @api.multi
    def get_potitle(self):
        pobj = self.env['purchase.order'].sudo().search([('name', '=', self.origin)])
        # 2019-07-25 08:49:17
        if pobj:
            title = pobj.title
            self.write({'title':title})
        else:
            raise ValidationError('此单据没有关联的采购单,无法获取项目号.')

class AccStockInventory(models.Model):
    """
     库存盘点继承
    """
    _inherit = "stock.inventory"


    process_state = fields.Selection([('accept', '已审批'), ('noaccept', '未审批')], default='noaccept',string='审批状态',readonly=True)

    @api.multi
    def action_validate(self):
        res = super(AccStockInventory,self).action_validate()
        process_state = self.process_state
        if process_state == 'noaccept':
            raise ValidationError("需由领导审批后才可进行验证库存操作")
        return res

    @api.multi
    def draft_accept(self):
        self.filtered(lambda r: r.process_state == 'noaccept').write({'process_state': 'accept'})
        return True

class AccStockInventoryLine(models.Model):
    """
     库存盘点明细继承
    """
    _inherit = "stock.inventory.line"

    
    product_model = fields.Char(string=u'规格型号',related='product_id.product_model')
    acc_code = fields.Char(string=u'产品编码',related='product_id.acc_code')



# # -*- coding: utf-8 -*-
# from datetime import datetime
# from odoo import fields, models, api, http, _
# from odoo.addons import decimal_precision as dp
# from odoo.http import request
# from odoo.exceptions import UserError, ValidationError

class ExcipientsProduct(models.Model):
    """
    辅料清单
    """
    _name = 'excipients.product'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "辅料清单"
    _order = 'gen_datetime desc'

    # @api.model
    # def create(self,vals):
    #     if not vals.get('name',''):
    #         last_name = self.env['ir.sequence'].get('before.purchase') or ''
    #         vals['name'] = "%s"%(last_name)
    #     result = super(BeforePurchase,self).create(vals)
    #     return result


    # name = fields.Char(string='名称')
    product_id = fields.Many2one('product.product',string='物料产品')
    gen_datetime = fields.Datetime(string='创建时间',default=lambda self: fields.Datetime.now(),readonly=True)
    partner_code = fields.Char(string='供应商编码',readonly=True)
    brand = fields.Char(string='品牌',readonly=True)
    internal_des = fields.Char(string='内部描述',readonly=True)
    # product_describe_cn = fields.Text(string='产品中文描述')
    # product_describe_en = fields.Text(string='产品英文描述')
    product_model = fields.Char(string='产品型号',readonly=True)
    acc_code = fields.Char(string='产品编码',readonly=True)
    now_qty = fields.Float(string='当前数量')
    min_qty = fields.Float(string='最低库存')
    max_qty = fields.Float(string='最大库存')
    active = fields.Boolean(string='有效')


    

