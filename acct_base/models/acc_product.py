# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.http import request
import logging
import xlrd
from collections import Counter
import re

import pytz

from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
# from ..controllers.common import localizeStrTime
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class product_templ_acc(models.Model):
    _inherit = 'product.template'

    @api.model
    def create(self,vals):
        if not vals.get('acc_code',''):
            last_name = self.env['ir.sequence'].get('product.template') or ''
            vals['acc_code'] = "%s"%(last_name)
        if vals.get('product_model') and vals.get('brand'):
            self.check_products(vals)
        result = super(product_templ_acc,self).create(vals)
        return result

    en_name = fields.Char(string='产品英文名称')
    partner_code = fields.Char(string='供应商编码')
    brand = fields.Char(string='品牌',required=True)
    internal_des = fields.Char(string='内部描述')
    product_describe_cn = fields.Text(string='产品中文描述')
    product_describe_en = fields.Text(string='产品英文描述')
    product_model = fields.Char(string='产品型号',required=True)
    acc_code = fields.Char(string='产品编码',readonly=True)
    template_currency_id = fields.Many2one('res.currency',string='币种')
    acc_purchase_price = fields.Float(string='采购价格',default=0.0)
    partner_id = fields.Many2one('res.partner',string='供应商')
    image_code = fields.Char(string='图号')
    part_code = fields.Char(string='编号')
    # type = fields.Selection([
    #     ('consu', 'Consumable'),
    #     ('service', 'Service')], string='Product Type', default='product', required=True,
    #     help='A storable product is a product for which you manage stock. The Inventory app has to be installed.\n'
    #          'A consumable product is a product for which stock is not managed.\n'
    #          'A service is a non-material product you provide.')

    # _sql_constraints = [
    #     ('products_uniq', 'UNIQUE(product_model,brand)', '产品重复(系统存在该型号品牌的产品)！')
    # ]
    
    # @api.multi
    # def write(self, vals):
    #     # if self.purchase_type == 'office':
    #     #     self.check_office_price(vals)
    #     if vals.get('name'):
    #         p_name = vals.get('name')
    #         print (p_name)  
    #     res = super(product_templ_acc, self).write(vals)
    #     return res

    def check_products(self,vals):
        product_model = vals.get('product_model')
        brand = vals.get('brand')
        product_name = vals.get('name')
        pt = self.env['product.template'].search([('product_model', '=', product_model),('brand', '=', brand),('name', '=', product_name),('active', '=', True)])
        if pt:
            raise ValidationError("产品重复(系统存在该型号品牌的产品)！") 

    @api.multi
    def action_see_attachments(self):
        product = self.env['product.product'].search([('product_tmpl_id', '=', self.id)])
        domain = [
            '|',
            '&', ('res_model', '=', 'product.product'), ('res_id', '=', product.id),
            '&', ('res_model', '=', 'product.template'), ('res_id', '=', self.id)]
        attachment_view = self.env.ref('acct_base.view_document_file_kanban_acct')
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'mrp.document',
            'type': 'ir.actions.act_window',
            'view_id': attachment_view.id,
            'views': [(attachment_view.id, 'kanban'), (False, 'form')],
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Upload files to your product
                    </p><p>
                        Use this feature to store any files, like drawings or specifications.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % ('product.template', self.id)
        }

    @api.multi
    def make_acccode(self):
        pt = self.env['product.template'].search([('acc_code', 'like', 'ACC-PRO-')])
        for i in pt:
            i.write({'active':False})
            _logger.debug('===========%s===============', i.name)


    def import_product_data(self, fileName=None, content=None):
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
            all_data,repeat_name = self.check_repeat(all_data)
            for import_line in all_data:
                res_partner = self.env['res.partner'].search([('name', '=', str(import_line[4]))])
                uom = self.env['uom.uom'].search([('name', '=', str(import_line[7]))])
                if uom:
                    uom_id = uom.id
                else:
                    uom_id = 38
                    # uom_id = 21
                product_category = self.env['product.category'].search([('name', '=', str(import_line[3]))])
                if product_category:
                    categ_id = product_category.id
                else:
                    categ_id = 1
                try:
                    vals = {
                        "type":'product',
                        "name":import_line[0],
                        "acc_code":import_line[1],
                        "product_model":import_line[2],
                        'categ_id':categ_id,
                        "partner_id":res_partner.id,
                        "brand":import_line[5],
                        "list_price":float(import_line[6]),
                        "acc_purchase_price":float(import_line[6]),
                        "sale_ok":True,
                        "purchase_ok":True,
                        'uom_id':uom_id,
                        "product_describe_cn":import_line[8],
                        "product_describe_en":import_line[9],
                        "internal_des":import_line[12],
                        "en_name":import_line[13],
                        "partner_code":import_line[14],
                        "description":import_line[10]
                    }
                    # employee_id = self.with_context(user_type='employee').create(vals)
                    self.env['product.template'].create(vals)
                    cr.commit()
                    success_num += 1
                    # print (import_line[0],import_line[1])
                    _logger.debug('===========%s===============%s', import_line[0], import_line[1])
                except Exception as e:
                    logging.error(e)
                    error_product_name.append(import_line[0])
            import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败产品名称{} 系统中已存在{}".format(len(all_data), success_num,error_product_name,repeat_name)
            # import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败产品名称{}".format(len(all_data), success_num,error_product_name)
        except Exception as e:
            logging.error(e)
        else:
            raise ValidationError(import_tips)
            
    


    # def import_product_data(self, fileName=None, content=None):
    #     if content:
    #         workbook = xlrd.open_workbook(file_contents=content)
    #     else:
    #         raise ValidationError(u'请选择正确的文档')
    #     book_sheet = workbook.sheet_by_index(0)
    #     all_data = []
    #     all_card_number = []
    #     for row in range(1, book_sheet.nrows):
    #         row_data = []
    #         for col in range(book_sheet.ncols):
    #             cel = book_sheet.cell(row, col)
    #             val = cel.value
    #             row_data.append(val)
    #         all_data.append(row_data)
    #     cr = self.env.cr
    #     for import_line in all_data:
    #         # cr=self.env.cr
    #         cr.execute(
    #                     """UPDATE product_template
    #                         SET acc_code = '%s'
    #                         WHERE
    #                             NAME = '%s'
    #                         AND product_model = '%s'
    #                         AND brand = '%s'
    #                         AND product_describe_cn = '%s'
    #                     """%(import_line[1],import_line[0],import_line[2],import_line[5],import_line[8]))
    #         print (import_line[0],import_line[1])
    #         _logger.debug('===========%s===============%s', import_line[0], import_line[1])
    #         
    
    def check_repeat(self,all_data):
        repeat_name = []
        # repeat_code = []
        for i in range(len(all_data)-1,-1,-1):
            # pt = self.env['product.template'].search([('name', '=', all_data[i][0]),('product_model', '=', all_data[i][2]),('brand', '=', all_data[i][5]),('product_describe_cn', '=', all_data[i][8])])
            pt = self.env['product.template'].search([('product_model', '=', all_data[i][2]),('brand', '=', all_data[i][5]),('active', '=', True)])
            if pt:
                # print (pt[0].name,pt[0].acc_code)
                repeat_name.append(pt[0].name)
                # repeat_code.append(pt[0].acc_code)
                all_data.remove(all_data[i])
        return all_data,repeat_name






class product_product_acc(models.Model):
    _inherit = 'product.product'

    # product_model = fields.Char(string='产品型号')
    # brand = fields.Char(string='品牌')
    # product_describe_cn = fields.Text(string='产品中文描述')
    # product_describe_en = fields.Text(string='产品英文描述')
    # acc_purchase_price = fields.Float(string='采购价格',default=0.0)
    # partner_id = fields.Many2one('res.partner',string='供应商')
    # acc_code = fields.Char(string='产品编码')
    # template_currency_id = fields.Many2one('res.currency',string='币种')
    # image_code = fields.Char(string='图号')
    # part_code = fields.Char(string='编号')

    product_model = fields.Char(related='product_tmpl_id.product_model',readonly=True, store=True,string='产品型号')
    brand = fields.Char(related='product_tmpl_id.brand',readonly=True, store=True,string='品牌')
    en_name = fields.Char(related='product_tmpl_id.en_name',readonly=True, store=True,string='产品英文名称')
    partner_code = fields.Char(related='product_tmpl_id.partner_code',readonly=True, store=True,string='供应商编码')
    internal_des = fields.Char(related='product_tmpl_id.internal_des',readonly=True, store=True,string='内部描述')
    product_describe_cn = fields.Text(related='product_tmpl_id.product_describe_cn',readonly=True, store=True,string='产品中文描述')
    product_describe_en = fields.Text(related='product_tmpl_id.product_describe_en',readonly=True, store=True,string='产品英文描述')
    acc_purchase_price = fields.Float(related='product_tmpl_id.acc_purchase_price',readonly=True, store=True,string='采购价格')
    partner_id = fields.Many2one('res.partner',related='product_tmpl_id.partner_id',readonly=True, store=True,string='供应商')
    acc_code = fields.Char(related='product_tmpl_id.acc_code',readonly=True, store=True,string='产品编码')
    template_currency_id = fields.Many2one('res.currency',related='product_tmpl_id.template_currency_id',readonly=True, store=True,string='币种')
    image_code = fields.Char(related='product_tmpl_id.image_code',readonly=True, store=True,string='图号')
    part_code = fields.Char(related='product_tmpl_id.part_code',readonly=True, store=True,string='编号')

    @api.multi
    def action_see_attachments(self):
        domain = [
            '|',
            '&', ('res_model', '=', 'product.template'), ('res_id', '=', self.product_tmpl_id.id),
            '&', ('res_model', '=', 'product.product'), ('res_id', '=', self.id)]
        attachment_view = self.env.ref('acct_base.view_document_file_kanban_acct')
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'mrp.document',
            'type': 'ir.actions.act_window',
            'view_id': attachment_view.id,
            'views': [(attachment_view.id, 'kanban'), (False, 'form')],
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Upload files to your product
                    </p><p>
                        Use this feature to store any files, like drawings or specifications.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % ('product.template', self.id)
        }

    
    