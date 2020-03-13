# -*- coding: utf-8 -*-
import logging
import xlrd
import xlwt
import pytz
import sys,os
import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
file_url = 'my_addons/acct_stock'
file_url = os.path.join(sys.path[0],file_url)


_logger = logging.getLogger(__name__)

def check_path(image_path):
    try:
        dir_path = os.path.dirname(image_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    except OSError as e:
        logging.debug("file cant be created!{}".format(e))
    return True

class AccStockMove(models.Model):
    """
     库存移动继承
    """
    _inherit = "stock.move"

    product_model = fields.Char(string=u'规格型号',related='product_id.product_model',store=True)
    acc_code = fields.Char(string=u'产品编码',related='product_id.acc_code',store=True)
    brand = fields.Char(string=u'品牌',related='product_id.brand',store=True)
    forcast_date = fields.Date(string='预计到货日期',readonly=True)

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

    # @api.multi
    # def button_validate(self):
    #     res = super(AccStockPicking,self).button_validate()
    #     po_name = self.origin
    #     po_obj = self.env['purchase.order'].search([('name', '=', po_name)])
    #     qty_received = []
    #     product_qty = []
    #     if po_obj:
    #         for line in po_obj.order_line:
    #             qty_received.append(line.qty_received)
    #             product_qty.append(line.product_qty)
    #             _logger.debug('===========%s===============', qty_received)
    #             _logger.debug('===========%s===============', product_qty)
    #         if sum(qty_received) == 0:
    #             po_obj.write({'product_state':'new'})
    #         elif sum(qty_received) < sum(product_qty) and sum(qty_received) != 0:
    #             po_obj.write({'product_state':'part'})
    #         else:
    #             po_obj.write({'product_state':'all'})
    #     return res

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
            if move_ids:
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

    # @api.multi
    # def action_validate(self):
    #     res = super(AccStockInventory,self).action_validate()
    #     process_state = self.process_state
    #     if process_state == 'noaccept':
    #         raise ValidationError("需由领导审批后才可进行验证库存操作")
    #     return res

    @api.multi
    def draft_accept(self):
        self.filtered(lambda r: r.process_state == 'noaccept').write({'process_state': 'accept'})
        return True

    def save_exel(self, header, body, file_name):
        wbk = xlwt.Workbook(encoding='utf-8', style_compression=0)
        # wbk.write(codecs.BOM_UTF8)
        style1 = xlwt.easyxf('font: bold True;''alignment: horz center,vert center')
        sheet = wbk.add_sheet('sheet1', cell_overwrite_ok=True)
        # sheet.write(codecs.BOM_UTF8) 

        sheet.write(0, 0, 'some text')
        sheet.write(0, 0, 'this should overwrite')  ##重新设置，需要cell_overwrite_ok=True
        n = 0
        for i in range(len(header)):
            sheet.write(n, i, header[i])
        for i in range(len(body)):
            n += 1
            for j in range(len(body[i])):
                # sheet.write(n, j, body[i][j], self.set_style())
                sheet.write(n, j, body[i][j])
        wbk.save(file_name)  ##该文件名必须存在

    def export_record(self,file_name):
        """
        导出采购单信息
        :return:
        """
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/work/files_export?file=%s' % (file_name),
            'target': 'self'
        }

    def export_inventory_record(self):
        cr = self.env.cr
        # if not product_state and not payment_state:
        all_total = """ SELECT
                            pt.name as product_name,
                            sl.name as location_name,
                            pt.product_model as product_model,
                            pt.acc_code as acc_code,
                            u."name" as u_name,
                            a.theoretical_qty as theoretical_qty,
                            a.product_qty as product_qty
                        FROM
                            stock_inventory_line A
                        LEFT JOIN product_product pp ON pp. ID = A .product_id
                        LEFT JOIN product_template pt on pt.id = pp.product_tmpl_id
                        LEFT JOIN stock_location sl on sl.id = a.location_id
                        left JOIN uom_uom u on u.id = a.product_uom_id
                        WHERE inventory_id = %s """ %(self.id)
        cr.execute(all_total)
        result = cr.dictfetchall()
        detail_list_all=[]
        i= 0
        for line in result:
            detail_list_first = []
            i += 1
            detail_list_first.append(i)
            detail_list_first.append(line.get('product_name'))
            detail_list_first.append(line.get('location_name'))
            detail_list_first.append(line.get('product_model'))
            detail_list_first.append(line.get('acc_code'))
            detail_list_first.append(line.get('u_name'))
            detail_list_first.append(line.get('theoretical_qty'))
            detail_list_first.append(line.get('product_qty'))
            detail_list_all.append(detail_list_first)

        dir_path = os.path.join(file_url, 'Administrator')
        filename = "{}.xls".format('库存盘点表')
        file_path = os.path.join(dir_path, filename)
        check_path(file_path)
        head = ['序号', '物料名称','库位','产品型号','产品编码','单位','理论数量','实际数量']
        self.save_exel(head, detail_list_all, file_path)
        return self.export_record(file_path)

class AccStockInventoryLine(models.Model):
    """
     库存盘点明细继承
    """
    _inherit = "stock.inventory.line"

    
    product_model = fields.Char(string=u'规格型号',related='product_id.product_model')
    acc_code = fields.Char(string=u'产品编码',related='product_id.acc_code')



class ExcipientsProduct(models.Model):
    """
    辅料清单
    """
    _name = 'excipients.product'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "辅料清单"
    _order = 'gen_datetime desc'


    product_id = fields.Many2one('product.product',string='物料产品')
    gen_datetime = fields.Datetime(string='创建时间',default=lambda self: fields.Datetime.now(),readonly=True)
    partner_code = fields.Char(string='供应商编码')
    brand = fields.Char(string='品牌')
    internal_des = fields.Char(string='内部描述')
    # product_describe_cn = fields.Text(string='产品中文描述')
    before_purchase_id = fields.Many2one('before.purchase',string='最新关联待确认询价单',readonly=True)
    product_model = fields.Char(string='产品型号')
    location_id = fields.Many2one('stock.location',string='位置')
    acc_code = fields.Char(string='产品编码')
    uom_id = fields.Many2one('uom.uom',string='单位')
    purchase_qty = fields.Float(string='在途数量')
    now_qty = fields.Float(string='当前数量')
    min_qty = fields.Float(string='最低库存')
    max_qty = fields.Float(string='最大库存')
    is_active = fields.Boolean(string='有效',default=True)


    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.partner_code = self.product_id.product_tmpl_id.partner_code
            self.brand = self.product_id.product_tmpl_id.brand
            self.internal_des = self.product_id.product_tmpl_id.internal_des
            self.acc_code = self.product_id.product_tmpl_id.acc_code
            self.product_model = self.product_id.product_tmpl_id.product_model
            self.uom_id = self.product_id.product_tmpl_id.uom_po_id


    @api.multi
    def compute_now_qty(self):
        # location_ids = self.get_location_ids()
        p_id = self.product_id.id
        location_id = self.location_id.id
        cr = self.env.cr
        # location_ids = []
        now_qty_sql = """ SELECT
                            SUM (quantity-reserved_quantity) AS theory_qty
                        FROM
                            stock_quant
                        WHERE
                            location_id = %s
                        AND product_id = %s """%(location_id, p_id)
        # now_qty = cr.execute(now_qty_sql, (location_id,p_id))
        cr.execute(now_qty_sql)
        result = request.cr.dictfetchall()
        if result[0]['theory_qty']:
            now_qty = result[0]['theory_qty']
        else:
            now_qty = 0.00
        self.write({'now_qty':now_qty})
        return now_qty

    @api.multi
    def compute_now_purchase(self):
        before_purchase_id = self.before_purchase_id
        if not before_purchase_id:
            return 'needpurchase'
        if before_purchase_id.state == 'draft':
            return 'nopurchase'
        if before_purchase_id.state == 'cancel':
            return 'needpurchase'
        product_id = self.product_id.id
        purchase_models = self.env['purchase.order'].search([('before_purchase_id','=',before_purchase_id.id),('state','!=','cancel'),('is_excipients','=',True)])
        po_ids = [tmp.id for tmp in purchase_models]
        po_line = self.env['purchase.order.line'].search([('order_id', 'in', po_ids),('product_id', '=', product_id)])
        if po_line:
            qty_r = 0.0
            q_qty = 0.0
            for line in po_line:
                qty_r += line.qty_received
                q_qty += line.product_qty
            # if po_line.qty_received < po_line.product_qty:
            if qty_r < q_qty:
                return 'nopurchase'
            else:
                return 'needpurchase'
        else:
            return 'needpurchase'



    @api.multi
    def _fresh_now_qty(self):
        excipients = self.env['excipients.product'].search([('is_active', '=', True)])
        for line in excipients:
            p_id = line.product_id.id
            location_id = line.location_id.id
            cr = self.env.cr
            # location_ids = []
            now_qty_sql = """ SELECT
                                SUM (quantity-reserved_quantity) AS theory_qty
                            FROM
                                stock_quant
                            WHERE
                                location_id = %s
                            AND product_id = %s """%(location_id, p_id)
            # now_qty = cr.execute(now_qty_sql, (location_id,p_id))
            cr.execute(now_qty_sql)
            result = request.cr.dictfetchall()
            if result[0]['theory_qty']:
                now_qty = result[0]['theory_qty']
            else:
                now_qty = 0.00
            onway_qty = line.onway_qty()
            line.write({'now_qty':now_qty,'purchase_qty':onway_qty})
        return True

    @api.multi
    def onway_qty(self):
        onway_qty = 0.0
        before_purchase_id = self.before_purchase_id
        if not before_purchase_id:
            return onway_qty
        if before_purchase_id.state == 'draft' or before_purchase_id.state == 'cancel':
            return onway_qty
        # if before_purchase_id.state == 'cancel':
        #     return onway_qty
        product_id = self.product_id.id
        purchase_models = self.env['purchase.order'].search([('before_purchase_id','=',before_purchase_id.id),('state','!=','cancel'),('is_excipients','=',True)])
        po_ids = [tmp.id for tmp in purchase_models]
        po_line = self.env['purchase.order.line'].search([('order_id', 'in', po_ids),('product_id', '=', product_id)])
        if po_line:
            qty_r = 0.0
            q_qty = 0.0
            for line in po_line:
                qty_r += line.qty_received
                q_qty += line.product_qty
            onway_qty = q_qty - qty_r
            return onway_qty
        else:
            return onway_qty


    @api.model
    def _check_need_purchase(self):
        excipients = self.env['excipients.product'].search([('is_active', '=', True)])
        res_line = []
        excipient_ids = []
        for ex in excipients:
            purchase_state = ex.compute_now_purchase()
            _logger.debug('===========%s===============%s', purchase_state, ex.product_id)
            if purchase_state == 'needpurchase':
                now_qty = ex.compute_now_qty()
                if now_qty < ex.min_qty:
                    line_vals = {
                      # 'order_id':self.before_purchase_id.id,
                      'product_id':ex.product_id.id,
                      'product_model':ex.product_id.product_tmpl_id.product_model,
                      'qty':ex.max_qty - now_qty,
                      'acc_purchase_price':ex.product_id.product_tmpl_id.acc_purchase_price,
                      'brand':ex.product_id.product_tmpl_id.brand,
                      'acc_code':ex.product_id.product_tmpl_id.acc_code,
                      'partner_code':ex.product_id.product_tmpl_id.partner_code
                    }
                    res_line.append(line_vals)
                    excipient_ids.append(ex.id)
        if res_line:
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
                # 'demand_purchase_id':self.id,
                'purchase_company':2,
                'is_excipients':True,
                'charge_person':10,
                'order_line':new_res_line
            }
            bp_obj = self.env['before.purchase'].create(vals)
            if excipient_ids:
                for excipient_id in excipient_ids:
                    excipient_model=self.env['excipients.product'].search([('id', '=', excipient_id)])
                    excipient_model.write({'before_purchase_id':bp_obj.id})








    

