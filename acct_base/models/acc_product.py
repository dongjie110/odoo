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

    brand = fields.Char(string='品牌',required=True)
    product_describe_cn = fields.Text(string='产品中文描述')
    product_describe_en = fields.Text(string='产品英文描述')
    product_model = fields.Char(string='产品型号',required=True)
    acc_code = fields.Char(string='产品编码')
    template_currency_id = fields.Many2one('res.currency',string='币种')
    acc_purchase_price = fields.Float(string='采购价格',default=0.0)
    partner_id = fields.Many2one('res.partner',string='供应商')
    image_code = fields.Char(string='图号')
    part_code = fields.Char(string='编号')


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
            for import_line in all_data:
                # if import_line[0] in exist_cards:
                    # error_card_number.append(import_line[0])
                # else:
                # res_country_state = self.env['res.country.state'].search([('name', '=', str(import_line[7]))])
                # product_category = self.env['product.category'].search([('name', '=', str(import_line[3]))])
                res_partner = self.env['res.partner'].search([('name', '=', str(import_line[4]))])
                uom = self.env['uom.uom'].search([('name', '=', str(import_line[7]))])
                if uom:
                    uom_id = uom.id
                else:
                    uom_id = 1
                product_category = self.env['product.category'].search([('name', '=', str(import_line[3]))])
                if product_category:
                    categ_id = product_category.id
                else:
                    categ_id = 1
                # if not res_partner or not product_category:
                #     error_product_name.append(import_line[0])
                # else:
                # partner_id = res_partner.id
                # # category_id = product_category.id
                # uom_id = uom.id
                try:
                    vals = {
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
                        "product_describe_en":import_line[9]
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
            import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败产品名称{}".format(len(all_data), success_num,error_product_name)
        except Exception as e:
            logging.error(e)
            # if card_number_repeated:
            #     raise ValidationError(import_tips)
            # elif card_id_repeated:
            #     raise ValidationError(import_id_tips)
            # else:
            #     raise ValidationError('请使用正确的模板进行导入操作！')
        else:
            raise ValidationError(import_tips)

class product_product_acc(models.Model):
    _inherit = 'product.product'

    product_model = fields.Char(string='产品型号',related='product_tmpl_id.product_model', readonly=True)
    brand = fields.Char(string='品牌',related='product_tmpl_id.product_model', readonly=True)
    product_describe_cn = fields.Text(string='产品中文描述',related='product_tmpl_id.product_describe_cn')
    product_describe_en = fields.Text(string='产品英文描述',related='product_tmpl_id.product_describe_en')
    acc_purchase_price = fields.Float(string='采购价格',default=0.0,related='product_tmpl_id.acc_purchase_price')
    partner_id = fields.Many2one('res.partner',related='product_tmpl_id.partner_id',string='供应商')