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


class res_partner_acc(models.Model):
    _inherit = 'res.partner'

    charge_person = fields.Many2one('res.users',string="负责人",default=lambda self: self.env.user.id,required=True)
    traffic_level = fields.Selection([('0', '一般'), ('1', '低'), ('2', '高'), ('3', '非常高')], '运输时间评级', default='0')
    quality_level = fields.Selection([('0', '一般'), ('1', '低'), ('2', '高'), ('3', '非常高')], '质量评级', default='0')
    price_level = fields.Selection([('0', '一般'), ('1', '低'), ('2', '高'), ('3', '非常高')], '价格评级', default='0')
    acc_image = fields.Binary("营业执照", attachment=True)
    
    @api.model
    def create(self,vals):
        if vals.get('name') and not vals.get('parent_id'):
            name_list = []
            new_name = vals.get('name','')
            request.cr.execute("""select name from res_partner""")
            names = request.cr.dictfetchall()
            for name in names:
                name_list.append(name['name'])
            if new_name in name_list:
                raise ValidationError('供应商或客户名称重复！！')
        res = super(res_partner_acc, self).create(vals)
        return res

    #采购订单中根据所选供应商对联系人进行筛选
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        context = self.env.context
        if context.get('choose_contact') or context.get('sale_choose_contact'):
            domain = []
            contact = self.search(args, limit=limit)
            return contact.name_get()
        return super(res_partner_acc, self).name_search(name=name, args=args, operator=operator, limit=limit)


    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        context = self.env.context
        if context.get('choose_contact') or context.get('sale_choose_contact'):
            partner_id = context.get('partner_id','')
            # print company_id
            contact_ids = []
            if partner_id:
                # machines = machines_ids[0][2]
                # print machines_ids
                cr = self.env.cr
                sql = """
                        SELECT
                            ID
                        FROM
                            res_partner
                        WHERE
                            parent_id = %s
                      """ %(partner_id)
                cr.execute(sql)
                contact_ids = cr.fetchall()
                contact_ids = [contact[0] for contact in contact_ids]
                args.append(('id','in',contact_ids))
                order = 'name desc'

        return super(res_partner_acc, self).search(args, offset, limit, order, count)

    def import_supply(self, fileName=None, content=None):
        import_tips = ""
        card_number_repeated = False
        try:
            if content:
                workbook = xlrd.open_workbook(file_contents=content)
            else:
                raise ValidationError(u'请选择正确的文档')
            book_sheet = workbook.sheet_by_index(0)
            all_data = []
            all_card_number = []
            # all_card_id = []
            # re_pattern = re.compile(u'^[0-9a-zA-Z]+$')
            # re_pattern_id = re.compile(u'^[W]{1}[G]{1}[0-9]{6}')
            for row in range(1, book_sheet.nrows):
                row_data = []
                for col in range(book_sheet.ncols):
                    cel = book_sheet.cell(row, col)
                    val = cel.value
                    row_data.append(val)
                if type(row_data[2]).__name__ == 'float':
                    row_data[2] = int(row_data[2])
                if type(row_data[3]).__name__ == 'float':
                    row_data[3] = int(row_data[3])
                all_data.append(row_data)
                all_card_number.append(str(row_data[0]))
                # print (type(row_data[2]))
                # all_card_id.append(str(row_data[1]))
            card_counter = dict(Counter(all_card_number))
            # card_counter_id = dict(Counter(all_card_id))
            for key, value in card_counter.items():
                if value > 1:
                    import_tips = "供应商名称：%s 在导入表中出现多次，请处理"%( key )
                    card_number_repeated = True
                    raise ValidationError(import_tips)
            cr = self.env.cr
            exist_cards = []
            if all_card_number:
                sql = """select name from res_partner where name in %s"""
                cr.execute(sql,(tuple(all_card_number),))
                exist_cards_tmp = cr.fetchall()
                exist_cards = [tmp[0] for tmp in exist_cards_tmp]
            error_card_number = []
            success_num = 0
            for import_line in all_data:
                if import_line[0] in exist_cards:
                    error_card_number.append(import_line[0])
                else:
                    # search([('name', '=ilike', currency_code)], limit=1)
                    res_country_state = self.env['res.country.state'].search([('name', '=', import_line[7])], limit=1)
                    res_country = self.env['res.country'].search([('name', '=', import_line[8])],limit=1)
                    try:
                        vals = {
                            "name":str(import_line[0]),
                            "street":import_line[1],
                            "phone":str(import_line[2]),
                            "mobile":str(import_line[3]),
                            "website":import_line[4],
                            "email":import_line[5],
                            'city':import_line[6],
                            'state_id':res_country_state.id,
                            "country_id":res_country.id,
                            "company_type":'company',
                            "supplier":True,
                            "customer":False,
                        }
                        # employee_id = self.with_context(user_type='employee').create(vals)
                        self.env['res.partner'].create(vals)
                        cr.commit()
                        success_num += 1
                        # print (import_line[0])
                        _logger.debug('===========%s===============', import_line[0])
                    except Exception as e:
                        logging.error(e)
                        error_card_number.append(import_line[0])
            # exist_message = ""
            if exist_cards:
                exist_message = "导入名称在系统中存在的有 {} 条，不做导入处理，名称分别为 {}".format(len(exist_cards), ','.join(exist_cards))
            # exist_id_message = ""
            # if exist_card_ids:
            #     exist_message = "导入储值卡ID在系统中存在的有 {} 条，不做导入处理，储值卡ID分别为 {}".format(len(exist_card_ids), ','.join(exist_card_ids))
            # error_message = ""
            # if error_card_number:
            #     error_message = "由于卡号格式不正确导致导入失败 {} 条， 卡号分别为 {}".format(len(error_card_number), ','.join(error_card_number))
            # error_id_message = ""
            # if error_card_id:
            #     error_id_message = "由于储值卡ID格式不正确导致导入失败 {} 条， 卡号分别为 {}".format(len(error_card_id), ','.join(error_card_id))
            import_tips = "一共导入 {} 条数据，导入成功条数为{} ,重复数据{}".format(len(all_data), success_num,exist_cards)
        except Exception as e:
            logging.error(e)
            if card_number_repeated:
                raise ValidationError(import_tips)
            # elif card_id_repeated:
            #     raise ValidationError(import_id_tips)
            else:
                raise ValidationError('请使用正确的模板进行导入操作！')
        else:
            raise ValidationError(import_tips)


    def import_contact(self, fileName=None, content=None):
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
                if type(row_data[1]).__name__ == 'float':
                    row_data[1] = int(row_data[1])
                if type(row_data[2]).__name__ == 'float':
                    row_data[2] = int(row_data[2])
                all_data.append(row_data)
            cr = self.env.cr
            error_partner_name = []
            success_num = 0
            for import_line in all_data:
                # if import_line[0] in exist_cards:
                    # error_card_number.append(import_line[0])
                # else:
                # res_country_state = self.env['res.country.state'].search([('name', '=', str(import_line[7]))])
                res_partner = self.env['res.partner'].search([('name', '=', str(import_line[3]))],limit=1)
                # title = self.env['res.partner.title'].search([('name', '=', str(import_line[7]))])
                if not res_partner:
                    error_partner_name.append(import_line[0])
                else:
                    parent_id = res_partner.id
                    try:
                        vals = {
                            "name":import_line[0],
                            "phone":import_line[1],
                            "mobile":import_line[2],
                            "parent_id":parent_id,
                            "email":import_line[4],
                            'function':import_line[5],
                            'website':str(import_line[6]),
                            # 'title':import_line[7],
                            # 'city':str(import_line[5]),
                            # "country_id":int(import_line[6]),
                            "company_type":'person',
                            "supplier":True
                        }
                        # employee_id = self.with_context(user_type='employee').create(vals)
                        self.env['res.partner'].create(vals)
                        cr.commit()
                        success_num += 1
                        # print (import_line[0],import_line[1])
                        _logger.debug('===========%s===============%s', import_line[0],import_line[1])
                    except Exception as e:
                        logging.error(e)
                        error_partner_name.append(import_line[0])
            import_tips = "一共导入 {} 条数据，导入成功条数为{} 导入失败联系人名称{}".format(len(all_data), success_num,error_partner_name)
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