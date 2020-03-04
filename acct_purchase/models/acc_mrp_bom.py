# -*- coding: utf-8 -*-
import logging
import xlrd
import xlwt
import pytz
import sys,os
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
file_url = 'my_addons/acct_purchase'
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

class AccMrpBom(models.Model):
    """
    bom继承
    """
    _inherit = "mrp.bom"


    merge_info = fields.Char(string='合并信息',readonly=True)
    acc_type = fields.Selection([('change', '可变'), ('base', '基础'),('standard','标准')], '内部类型', default='base')
    # is_active = fields.Boolean(string='有效',default=True,readonly=True)
    # version_no = fields.Integer(string='版本号',readonly=True,default=1)
    version_date = fields.Datetime(string='创建时间',default=lambda self: fields.Datetime.now(),readonly=True)
    @api.model
    def create(self,vals):
        # if vals.get('product_tmpl_id'):
        #     id_list = []
        #     new_id = vals.get('product_tmpl_id','')
        #     request.cr.execute("""select product_tmpl_id from mrp_bom""")
        #     lists = request.cr.dictfetchall()
        #     for p_id in lists:
        #         id_list.append(int(p_id['product_tmpl_id']))
        #     if new_id in id_list:
        #         raise ValidationError('物料清单重复！！')
        res = super(AccMrpBom, self).create(vals)
        # group_name = '商务部员工'
        # create_user_id = self._uid
        # luna.zhang@neotel-technology.com
        toaddrs = ['coco.ma@neotel-technology.com','jie.dong@neotel-technology.com','yi.wang@neotel-technology.com','cissy.shen@neotel-technology.com']
        # toaddrs = ['jie.dong@neotel-technology.com']
        subjects = "物料清单{}{}已创建".format(res.product_tmpl_id.name,res.code)
        message = "物料清单{}{}已创建请及时查看".format(res.product_tmpl_id.name,res.code)
        self.env['acc.tools'].send_report_email(subjects,message,toaddrs)
        # self.env['acc.tools'].send_report_email(group_name,create_user_id,subject,msg)
        return res

    @api.multi
    def unlink(self):
        for mrp in self:
            if mrp.active == True:
                raise ValidationError('不能删除该物料清单.')
        return super(AccMrpBom,self).unlink()

    def import_bom_charge(self, fileName=None, content=None):
        import_tips = ""
        # card_number_repeated = False
        try:
            if content:
                workbook = xlrd.open_workbook(file_contents=content)
            else:
                raise ValidationError(u'请选择正确的文档')
            book_sheet = workbook.sheet_by_index(0)
            all_data = []
            all_card_number = []
            for row in range(1, book_sheet.nrows):
                row_data = []
                for col in range(book_sheet.ncols):
                    cel = book_sheet.cell(row, col)
                    val = cel.value
                    row_data.append(val)
                if type(row_data[2]).__name__ == 'float':
                    row_data[2] = int(row_data[2])
                all_data.append(row_data)
            cr = self.env.cr
            error_product_name = []
            success_num = 0
            # all_data,repeat_name = self.check_repeat(all_data)
            for import_line in all_data:
                # res_partner = self.env['res.partner'].search([('name', '=', str(import_line[4]))])
                
                uom = self.env['uom.uom'].search([('name', '=', str(import_line[6]))])
                if uom:
                    uom_id = uom.id
                new_product_template = self.check_product(import_line,uom_id)
                new_product = self.env['product.product'].search([('product_tmpl_id', '=', new_product_template.id)])
                # else:
                #     uom_id = 38
                    # uom_id = 2
                # product_category = self.env['product.category'].search([('name', '=', str(import_line[3]))])
                # if product_category:
                #     categ_id = product_category.id
                # else:
                #     categ_id = 1
                active_id = self.env.context.get('active_id')
                try:
                    vals = {
                        "bom_id":active_id,
                        "product_id":new_product.id,
                        "acc_code":new_product.acc_code,
                        "product_model":new_product.product_model,
                        "brand":new_product.brand,
                        "product_qty":import_line[10],
                        "number":new_product.internal_des
                    }
                    # employee_id = self.with_context(user_type='employee').create(vals)
                    self.env['mrp.bom.line'].create(vals)
                    cr.commit()
                    success_num += 1
                    # print (import_line[0],import_line[1])
                    _logger.debug('===========%s===============%s', import_line[0], import_line[1])
                except Exception as e:
                    logging.error(e)
                    error_product_name.append(import_line[0])
            import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败名称{},如果明细行未显示请关闭该窗口，刷新页面即可".format(len(all_data), success_num,error_product_name)
        except Exception as e:
            logging.error(e)
        else:
            raise ValidationError(import_tips)

    def update_newinfo(self):
        cr = self.env.cr
        # if not product_state and not payment_state:
        sql = """ UPDATE mrp_bom_line
                        SET brand = (
                            SELECT
                                product_product.brand
                            FROM
                                product_product
                            WHERE
                                product_product. ID = mrp_bom_line.product_id
                        ),
                            product_model = (
                            SELECT
                                product_product.product_model
                            FROM
                                product_product
                            WHERE
                                product_product. ID = mrp_bom_line.product_id
                        ),
                            acc_code = (
                            SELECT
                                product_product.acc_code
                            FROM
                                product_product
                            WHERE
                                product_product. ID = mrp_bom_line.product_id
                        )
                        where bom_id = %s """%(self.id)
        cr.execute(sql)


    # def check_repeat(self,all_data):
    #     repeat_name = []
    #     # repeat_code = []
    #     for i in range(len(all_data)-1,-1,-1):
            # pt = self.env['product.template'].search([('product_model', '=', all_data[i][2]),('brand', '=', all_data[i][5])])
    #         if pt:
    #             # print (pt[0].name,pt[0].acc_code)
    #             repeat_name.append(pt[0].name)
    #             # repeat_code.append(pt[0].acc_code)
    #             all_data.remove(all_data[i])
    #     return all_data,repeat_name
    #     
    
    def check_product(self,import_line,uom_id):
        brand = import_line[4]
        product_model = import_line[2]
        product_name = import_line[0]
        pt = self.env['product.template'].search([('product_model', '=', product_model),('brand', '=', brand),('name', '=', product_name),('active', '=', True)])
        if pt:
            if len(pt) == 1:
                return pt
            if len(pt) > 1:
                for i in pt[1:]:
                    i.write({'active': False})
                return pt[0]
        if not pt:
            p_vals = {
                        "type":'product',
                        "name":import_line[0],
                        # "acc_code":import_line[1],
                        "product_model":import_line[2],
                        "brand":import_line[4],
                        "list_price":float(import_line[5]),
                        "acc_purchase_price":float(import_line[5]),
                        "sale_ok":True,
                        "purchase_ok":True,
                        'uom_id':uom_id,
                        'uom_po_id':uom_id,#采购计量单位
                        "product_describe_cn":import_line[7],
                        "product_describe_en":import_line[8],
                        "internal_des":import_line[11],
                        "en_name":import_line[12],
                        "partner_code":import_line[13],
                        "description":import_line[9]
                    }
            new_product = self.env['product.template'].create(p_vals)
            return new_product

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

    def export_bom_record(self):
        cr = self.env.cr
        # if not product_state and not payment_state:
        all_total = """ SELECT
                            pt. NAME AS pname,
                            pt.acc_code AS acc_code,
                            pt.product_model AS product_model,
                            pt.brand AS brand,
                            pt.acc_purchase_price AS acc_purchase_price,
                            uu. NAME AS uname,
                            pt.product_describe_cn AS product_describe_cn,
                            pt.product_describe_en AS product_describe_en,
                            pt.description AS description,
                            b.product_qty AS product_qty,
                            pt.internal_des AS internal_des,
                            pt.en_name AS en_name,
                            pt.partner_code AS partner_code,
                            b.id as bid
                        FROM
                            mrp_bom_line b
                        LEFT JOIN product_product pp ON b.product_id = pp. ID
                        LEFT JOIN product_template pt ON pt. ID = pp.product_tmpl_id
                        LEFT JOIN uom_uom uu ON uu. ID = pt.uom_id
                        WHERE
                            bom_id = %s 
                        ORDER BY bid """%(self.id)

        cr.execute(all_total)
        result = cr.dictfetchall()
        detail_list_all=[]

        # print result
        # strftime("%Y%m%d_%H%M%S")
        i= 0
        for line in result:
            detail_list_first = []
            i += 1
            detail_list_first.append(i)
            detail_list_first.append(line.get('pname'))
            detail_list_first.append(line.get('acc_code'))
            detail_list_first.append(line.get('product_model'))
            detail_list_first.append(line.get('brand'))
            detail_list_first.append(line.get('acc_purchase_price'))
            detail_list_first.append(line.get('uname'))
            detail_list_first.append(line.get('product_describe_cn'))
            detail_list_first.append(line.get('product_describe_en'))
            detail_list_first.append(line.get('description'))
            detail_list_first.append(line.get('product_qty'))
            detail_list_first.append(line.get('internal_des'))
            detail_list_first.append(line.get('en_name'))
            detail_list_first.append(line.get('partner_code'))
            detail_list_all.append(detail_list_first)

        dir_path = os.path.join(file_url, 'Administrator')
        filename = "{}.xls".format('物料清单明细表')
        file_path = os.path.join(dir_path, filename)
        check_path(file_path)
        head = ['序号', '物料名称','产品编码','产品型号','品牌','单价','单位','描述','英文描述','备注','数量','内部描述','产品英文名称','供应商编码']
        self.save_exel(head, detail_list_all, file_path)
        return self.export_record(file_path)


class AccMrpBomLine(models.Model):
    """
    bomline继承
    """
    _inherit = "mrp.bom.line"

    product_model = fields.Char(string='产品型号')
    number = fields.Char(string='内部描述')
    acc_code = fields.Char(string='产品编码')
    partner_id = fields.Many2one('res.partner',string='供应商')
    brand = fields.Char(string='品牌')
    internal_des = fields.Char(string='内部描述')

    @api.onchange('product_id')
    def onchange_product_id(self):
        res = super(AccMrpBomLine, self).onchange_product_id()
        # your logic here
        for rec in self:
            rec.number = self.product_id.product_tmpl_id.internal_des
            rec.product_model = self.product_id.product_tmpl_id.product_model
            rec.acc_code = self.product_id.product_tmpl_id.acc_code
            rec.brand = self.product_id.product_tmpl_id.brand

        return res


class AccMrpProduction(models.Model):
    """
    bom继承
    """
    _inherit = "mrp.production"

    @api.model
    def _get_default_location_src_id(self):
        location = False
        if self._context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_src_id
        if not location:
            location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        return location and location.id or False

    @api.model
    def _get_default_location_dest_id(self):
        location = False
        if self._context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_dest_id
        if not location:
            location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
        return location and location.id or False


    acc_start_date = fields.Date(string=u'开始日期')
    plan_date = fields.Date(string=u'预计结束日期')
    done_date = fields.Date(string=u'实际完成日期')
    plan_send_date = fields.Date(string=u'计划发货日期')
    code = fields.Char(related='bom_id.code',readonly=True, store=True,string='设备描述')
    location_src_id = fields.Many2one(
        'stock.location', '原料库位',
        default=_get_default_location_src_id,required=True,
        help="Location where the system will look for components.")
    location_dest_id = fields.Many2one(
        'stock.location', '成品库位',   
        default=_get_default_location_dest_id,required=True,
        help="Location where the system will stock the finished products.")


    @api.onchange('location_src_id')
    def onchange_location_src_id(self):
        if self.location_src_id:
            move_ids = []
            # print (self.location_src_id)
            for line in self.move_raw_ids:
                if line.raw_material_production_id:
                    move_ids.append(line.id)
                    # line.update({'location_id':self.location_src_id})
            if move_ids:
                cr = self.env.cr
                change_sql = """ UPDATE stock_move
                                SET location_id = %s
                                WHERE
                                    id in %s """
                # cr.execute(all_total)
                cr.execute(change_sql, (self.location_src_id.id,tuple(move_ids)))

    # @api.onchange('location_dest_id')
    # def onchange_location_dest_id(self):
    #     if self.location_dest_id:
    #         move_ids = []
    #         for line in self.move_raw_ids:
    #             if line.production_id:
    #                 move_ids.append(line.id)
    #                 # line.update({'location_dest_id':self.location_dest_id})
    #         cr = self.env.cr
    #         change_sql = """ UPDATE stock_move
    #                         SET location_dest_id = %s
    #                         WHERE
    #                             reference = %s """
    #         # cr.execute(all_total)
    #         cr.execute(change_sql, (self.location_dest_id.id,tuple(move_ids)))



class AccMrpEco(models.Model):
    """
    plm继承
    """
    _inherit = "mrp.eco"

    is_use = fields.Selection([('on', '已应用'), ('off', '未应用')], '应用状态', default='off')
    before_purchase_id = fields.Many2one('before.purchase',string='关联待确认询价单',readonly=True)
    change_reason = fields.Char(string='变更原因')

    @api.model
    def create(self,vals):
        if vals.get('product_tmpl_id'):
            self.check_ecos(vals)
        result = super(AccMrpEco,self).create(vals)
        return result

    def check_ecos(self,vals):
        product_tmpl_id = vals.get('product_tmpl_id')
        # brand = vals.get('brand')
        eco = self.env['mrp.eco'].search([('product_tmpl_id', '=', product_tmpl_id),('is_use', '=', 'off')])
        if eco:
            raise ValidationError("该物料清单存在未应用到采购变更单,请先完成未应用！")

    @api.multi
    def action_apply(self):
        res = super(AccMrpEco, self).action_apply()
        mos = self.env['mrp.production'].search([
            ('bom_id', '=', self.bom_id.id),
            ('state', 'in', ['confirmed','progress'])
        ]) 
        if mos:
            for m in mos:
                mrp_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', self.product_tmpl_id.id),('active', '=', True)])
                state_args,remove_ids = self.check_eco_products(m)
                self.sign_so(m)
                cr = self.env.cr
                cr.executemany("insert into stock_move(name,date,date_expected,picking_type_id,product_id,product_uom,product_uom_qty,location_id,location_dest_id,company_id,raw_material_production_id,warehouse_id,origin,group_id,propagate,sequence,state,unit_factor,procure_method,priority,create_date,scrapped,additional,reference,is_done,to_refund,product_qty,price_unit,bom_line_id) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"  , state_args)
                if remove_ids:
                    self.deal_remove(remove_ids,m)
                m.write({'bom_id':mrp_bom.id})
        return res

    @api.multi
    def deal_remove(self,remove_ids,mos):
        cr = self.env.cr
        all_total = """ delete from stock_move WHERE product_id in %s and raw_material_production_id = %s and state <> 'done' """
        # cr.execute(all_total)
        cr.execute(all_total, (tuple(remove_ids),mos.id))
        # cr.execute(all_total, (tuple(department_ids),))
        # 
    @api.multi
    def deal_update_add(self,product_id,mos,qty,unit_qty):
        cr = self.env.cr
        add_sql = """ UPDATE stock_move
                        SET product_uom_qty = product_uom_qty + %s,product_qty = product_qty + %s,unit_factor = unit_factor + %s,state = 'confirmed'
                        WHERE
                            raw_material_production_id = %s
                        AND product_id = %s
                        AND state <> 'done' """
        # cr.execute(all_total)
        cr.execute(add_sql, (qty,qty,unit_qty,mos.id,product_id))

    @api.multi
    def deal_update_minus(self,product_id,mos,qty,unit_qty):
        cr = self.env.cr
        minus_sql = """ UPDATE stock_move
                        SET product_uom_qty = product_uom_qty - %s,product_qty = product_qty - %s,unit_factor = unit_factor - %s
                        WHERE
                            raw_material_production_id = %s
                        AND product_id = %s
                        AND state <> 'done' """
        # cr.execute(all_total)
        cr.execute(minus_sql, (qty,qty,unit_qty,mos.id,product_id))


    @api.multi
    def check_eco_products(self,mos):
        remove_ids = []
        state_args = []
        mrp_bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', self.product_tmpl_id.id),('active', '=', True)])
        for change in self.bom_change_ids:
            bom_line_id = self.env['mrp.bom.line'].search([('bom_id', '=', mrp_bom.id),('product_id', '=', change.product_id.id)])
            old_lines = self.env['stock.move'].search([('raw_material_production_id', '=', mos.id),('state', '!=', 'done')])
            if old_lines:
                old_line = old_lines[0]
            # old_line = mos.move_raw_ids[0]  #需处理
            todo_qty = self.get_todo_qty(mos)  #获取待生产数量
            if change.change_type == 'add':
                s_tuple = mos.name,mos.date_planned_start,mos.date_planned_start,old_line.picking_type_id.id,change.product_id.id,change.new_uom_id.id,change.new_product_qty * todo_qty,old_line.location_id.id,old_line.location_dest_id.id,mos.company_id.id,mos.id,old_line.warehouse_id.id,mos.name,mos.procurement_group_id.id,mos.propagate,old_line.sequence,'confirmed',change.new_product_qty,old_line.procure_method,old_line.priority,old_line.create_date,old_line.scrapped,old_line.additional,old_line.reference,old_line.is_done,old_line.to_refund,change.new_product_qty * todo_qty,0,bom_line_id.id
                state_args.append(s_tuple)
            if change.change_type == 'remove':
                remove_ids.append(change.product_id.id)
            if change.change_type == 'update' and change.upd_product_qty > 0:
                # add_ids.append(change.product_id.id)
                qty = change.upd_product_qty * todo_qty
                unit_qty = change.upd_product_qty
                product_id = change.product_id.id
                self.deal_update_add(product_id,mos,qty,unit_qty)
            if change.change_type == 'update' and change.upd_product_qty < 0:
                qty = abs(change.upd_product_qty * todo_qty)
                unit_qty = abs(change.upd_product_qty)
                product_id = change.product_id.id
                self.deal_update_minus(product_id,mos,qty,unit_qty)
        return state_args,remove_ids

    @api.multi
    def get_todo_qty(self,production):
        # production = mos
        serial_finished = (production.product_id.tracking == 'serial')
        # todo_uom = production.product_uom_id.id
        if serial_finished:
            todo_quantity = 1.0
            # if production.product_uom_id.uom_type != 'reference':
            #     todo_uom = self.env['uom.uom'].search([('category_id', '=', production.product_uom_id.category_id.id), ('uom_type', '=', 'reference')]).id
        else:
            main_product_moves = production.move_finished_ids.filtered(lambda x: x.product_id.id == production.product_id.id)
            todo_quantity = production.product_qty - sum(main_product_moves.mapped('quantity_done'))
            todo_quantity = todo_quantity if (todo_quantity > 0) else 0
        return todo_quantity

    @api.multi
    def sign_so(self,mos):
        origin = mos.origin
        so = self.env['sale.order'].search([('name', '=', origin)])
        if so:
            so.write({'wait_change':'no'})

class AccMrpEcoBomChange(models.Model):
    """
    plm继承
    """
    _inherit = "mrp.eco.bom.change"

    acc_code = fields.Char(related='product_id.acc_code',readonly=True, store=True,string='物料编码')
    product_model = fields.Char(related='product_id.product_model',readonly=True, store=True,string='型号')
    brand = fields.Char(related='product_id.brand',readonly=True, store=True,string='品牌')

    