# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
from odoo.http import request
import logging
import xlrd
from collections import Counter
import re
import datetime as dt
import xlrd
import xlwt
import pytz
import sys,os
file_url = 'my_addons/acct_expense'
file_url = os.path.join(sys.path[0],file_url)
import logging

from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
# from ..controllers.common import localizeStrTime
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def check_path(image_path):
    try:
        dir_path = os.path.dirname(image_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    except OSError as e:
        logging.debug("file cant be created!{}".format(e))
    return True

class AccHrExpenseSheet(models.Model):
    """
     库存移动继承
    """
    _inherit = "hr.expense.sheet"

    expense_line_ids = fields.One2many('hr.expense', 'sheet_id', string='Expense Lines', states={'approve': [('readonly', True)], 'done': [('readonly', True)], 'post': [('readonly', True)],'teller': [('readonly', True)],'boss': [('readonly', True)]}, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submitted'),
        ('approve', 'Approved'),
        ('teller', '出纳已审核'),
        ('boss', '管理部已审核'),
        ('post', 'Posted'),
        ('done', 'Paid'),
        ('cancel', 'Refused')
    ], string='Status', index=True, readonly=True, track_visibility='onchange', copy=False, default='draft', required=True, help='Expense Report State')


    @api.multi
    def action_sheet_move_create(self):
        res = super(AccHrExpenseSheet,self).action_sheet_move_create()
        process_state = self.state
        if process_state == 'teller':
            raise ValidationError("需由出纳审批完成才可进行此操作")
        if process_state == 'boss':
            raise ValidationError("需由管理部门审批完成才可进行此操作")
        return res

    @api.multi
    def teller_accept(self):
        self.filtered(lambda r: r.state == 'approve').write({'state': 'teller'})
        return True

    @api.multi
    def boss_accept(self):
        self.filtered(lambda r: r.state == 'teller').write({'state': 'boss'})
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

    def export_expense_record(self):
        cr = self.env.cr
        # if not product_state and not payment_state:
        all_total = """ SELECT
                          h.NAME AS name,
                          h.description as description,
                          h.date as edate,
                          h.total_amount as amount,
                            pt.name as pname
                        FROM
                            hr_expense h
                        LEFT JOIN product_product pp on h.product_id = pp.id
                        LEFT JOIN product_template pt on pt.id = pp.product_tmpl_id

                        WHERE
                            sheet_id = %s """%(self.id)
        cr.execute(all_total)
        result = cr.dictfetchall()
        detail_list_all=[]

        # print result
        # strftime("%Y%m%d_%H%M%S")
        i= 0
        for line in result:
            detail_list_first = []
            i += 1
            # print ((line.get('create_date').strftime("%Y-%m-%d %H:%M:%S"))[0:11])
            detail_list_first.append(i)
            detail_list_first.append(line.get('edate').strftime("%Y-%m-%d"))
            # if line.get('edate'):
            #     detail_list_first.append(line.get('forcast_date').strftime("%Y-%m-%d"))
            # else:
            #     detail_list_first.append(line.get('forcast_date'))
            detail_list_first.append(line.get('name'))
            detail_list_first.append(line.get('pname'))
            detail_list_first.append(line.get('description'))
            detail_list_first.append(line.get('amount'))
            detail_list_all.append(detail_list_first)

        dir_path = os.path.join(file_url, 'Administrator')
        filename = "{}.xls".format('费用报告明细表')
        file_path = os.path.join(dir_path, filename)
        check_path(file_path)
        head = ['序号', '日期','说明','报销产品名称','备注','金额']
        self.save_exel(head, detail_list_all, file_path)
        return self.export_record(file_path)

class AccHrExpense(models.Model):
    """
     
    """
    _inherit = "hr.expense"

    # state = fields.Selection([
    #     ('draft', 'To Submit'),
    #     ('reported', 'Submitted'),
    #     ('approved', 'Approved'),
    #     ('done', 'Paid'),
    #     ('refused', 'Refused')
    # ], compute='_compute_state', string='Status', copy=False, index=True, readonly=True, store=True, help="Status of the expense.")

    @api.depends('sheet_id', 'sheet_id.account_move_id', 'sheet_id.state')
    def _compute_state(self):
        res = super(AccHrExpense, self)._compute_state()
        for rec in self:
            # if not expense.sheet_id or expense.sheet_id.state == 'draft':
            #     expense.state = "draft"
            # elif expense.sheet_id.state == "cancel":
            #     expense.state = "refused"
            # elif expense.sheet_id.state == "approve" or expense.sheet_id.state == "post":
            #     expense.state = "approved"
            # elif not expense.sheet_id.account_move_id:
            #     expense.state = "reported"
            # else:
            #     expense.state = "done"
            if rec.sheet_id.state == 'teller' or rec.sheet_id.state == 'boss':
                rec.state = "approved"

