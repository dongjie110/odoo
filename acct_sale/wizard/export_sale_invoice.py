#coding=utf-8
from odoo import models,fields,api
import datetime,time
import xlwt
from datetime import datetime,timedelta
# import pandas as pd
import sys,os
file_url = 'my_addons/acct_sale'
from odoo.http import request
file_url = os.path.join(sys.path[0],file_url)
import logging
import zipfile
import shutil
import base64
import logging
import codecs

_logger = logging.getLogger(__name__)


def check_path(image_path):
    try:
        dir_path = os.path.dirname(image_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    except OSError as e:
        logging.debug("file cant be created!{}".format(e))
    return True

def zip_dir(dirname, zipfilename):
    filelist = []
    if os.path.isfile(dirname):
        filelist.append(dirname)
    else:
        for root, dirs, files in os.walk(dirname):
            for name in files:
                filelist.append(os.path.join(root, name))

    zf = zipfile.ZipFile(zipfilename, "w", zipfile.zlib.DEFLATED)
    for tar in filelist:
        arcname = tar[len(dirname):]
        arcname = arcname.encode('GBK') #兼容windows平台，转为gbk,支持简体和繁体
        # print arcname
        zf.write(tar, arcname)
    zf.close()

class ExportSaleWizard(models.TransientModel):
    _name = "export.sale.wizard"

    # date_start = fields.Datetime(string='起始日期',default=lambda self:fields.Datetime.now())
    sale_company = fields.Many2one('acc.company',string='关联公司')
    charge_person = fields.Many2one('res.users',string=u'负责人')



    def save_exel(self, header, body, file_name):
        wbk = xlwt.Workbook(encoding='utf-8', style_compression=0)
        # wbk.write(codecs.BOM_UTF8)
        style1 = xlwt.easyxf('font: bold True;''alignment: horz center,vert center')
        sheet = wbk.add_sheet('应收款账单', cell_overwrite_ok=True)
        # sheet.write(codecs.BOM_UTF8) 

        sheet.write(0, 0, 'some text')
        sheet.write(0, 0, 'this should overwrite')  ##重新设置，需要cell_overwrite_ok=True
        n = 0
        for i in xrange(len(header)):
            sheet.write(n, i, header[i])
        for i in xrange(len(body)):
            n += 1
            for j in xrange(len(body[i])):
                # sheet.write(n, j, body[i][j], self.set_style())
                sheet.write(n, j, body[i][j])
        wbk.save(file_name)  ##该文件名必须存在

    def export_record(self,file_name):
        """
        导出应收款账单信息
        :return:
        """
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/work/files_export?file=%s' % (file_name),
            'target': 'self'
        }
    def export_sale_record(self):

        charge_person = self.charge_person.id
        user_name = self.charge_person.partner_id.name
        company_name = self.sale_company.name
        today = time.strftime("%Y-%m-%d")
        cr = self.env.cr
        if self.charge_person and not self.sale_company:
            file_name_str = user_name + '-' + '应收款账单' + today
            invoice_sql = """  SELECT
                                    A .date_invoice,
                                    A ."type",
                                    a.acct_note,
                                    d. NAME AS sname,
                                    d.partner_ponumber,
                                    b. NAME AS rname,
                                    e."name" as cname,
                                    e.symbol as symbol,
                                    A .amount_total,
                                    A .residual,
                                    CASE d.is_invoice
                                    WHEN 'part' THEN '部分开票'
                                    WHEN 'all' THEN '全部开票'
                                    ELSE '未开票' END AS is_invoice,
                                    CASE d.send_status
                                    WHEN 'yes' THEN '全部发货'
                                    WHEN 'no' THEN '未发货'
                                    ELSE '部分发货' END AS is_send
                                FROM
                                    account_invoice A
                                INNER JOIN res_partner b ON b. ID = A .partner_id
                                INNER JOIN sale_order d ON d."name" = A .origin
                                INNER JOIN res_currency e ON e.id = a.currency_id
                                WHERE
                                    A ."type" = 'out_invoice'
                                and a."state" = 'open'
                                and a.user_id = %s """%(charge_person)

        if self.sale_company and not self.charge_person:
            file_name_str = company_name + '-' + '应收款账单' + today
            invoice_sql = """  SELECT
                                    A .date_invoice,
                                    A ."type",
                                    a.acct_note,
                                    d. NAME AS sname,
                                    d.partner_ponumber,
                                    b. NAME AS rname,
                                    e."name" as cname,
                                    e.symbol as symbol,
                                    A .amount_total,
                                    A .residual,
                                    a.user_id as auid,
                                    CASE d.is_invoice
                                    WHEN 'part' THEN '部分开票'
                                    WHEN 'all' THEN '全部开票'
                                    ELSE '未开票' END AS is_invoice,
                                    CASE d.send_status
                                    WHEN 'yes' THEN '全部发货'
                                    WHEN 'no' THEN '未发货'
                                    ELSE '部分发货' END AS is_send
                                FROM
                                    account_invoice A
                                INNER JOIN res_partner b ON b. ID = A .partner_id
                                INNER JOIN sale_order d ON d."name" = A .origin and d.sale_company = %s
                                INNER JOIN res_currency e ON e.id = a.currency_id
                                WHERE
                                    A ."type" = 'out_invoice'
                                and a."state" = 'open' """%(self.sale_company.id)

        if not self.sale_company and not self.charge_person:
            file_name_str = '全部应收款账单' + today
            invoice_sql = """  SELECT
                                    A .date_invoice,
                                    A ."type",
                                    a.acct_note,
                                    d. NAME AS sname,
                                    d.partner_ponumber,
                                    b. NAME AS rname,
                                    e."name" as cname,
                                    e.symbol as symbol,
                                    A .amount_total,
                                    A .residual,
                                    a.user_id as auid,
                                    CASE d.is_invoice
                                    WHEN 'part' THEN '部分开票'
                                    WHEN 'all' THEN '全部开票'
                                    ELSE '未开票' END AS is_invoice,
                                    CASE d.send_status
                                    WHEN 'yes' THEN '全部发货'
                                    WHEN 'no' THEN '未发货'
                                    ELSE '部分发货' END AS is_send
                                FROM
                                    account_invoice A
                                INNER JOIN res_partner b ON b. ID = A .partner_id
                                INNER JOIN sale_order d ON d."name" = A .origin
                                INNER JOIN res_currency e ON e.id = a.currency_id
                                WHERE
                                    A ."type" = 'out_invoice'
                                and a."state" = 'open' """

        if self.sale_company and self.charge_person:
            file_name_str = company_name + '-' + user_name + '-' + '应收款账单' + today
            invoice_sql = """  SELECT
                                    A .date_invoice,
                                    A ."type",
                                    a.acct_note,
                                    d. NAME AS sname,
                                    d.partner_ponumber,
                                    b. NAME AS rname,
                                    e."name" as cname,
                                    e.symbol as symbol,
                                    A .amount_total,
                                    A .residual,
                                    CASE d.is_invoice
                                    WHEN 'part' THEN '部分开票'
                                    WHEN 'all' THEN '全部开票'
                                    ELSE '未开票' END AS is_invoice,
                                    CASE d.send_status
                                    WHEN 'yes' THEN '全部发货'
                                    WHEN 'no' THEN '未发货'
                                    ELSE '部分发货' END AS is_send
                                FROM
                                    account_invoice A
                                INNER JOIN res_partner b ON b. ID = A .partner_id
                                INNER JOIN sale_order d ON d."name" = A .origin and d.sale_company = %s
                                INNER JOIN res_currency e ON e.id = a.currency_id
                                WHERE
                                    A ."type" = 'out_invoice'
                                and a."state" = 'open'
                                and a.user_id = %s"""%(self.sale_company.id,charge_person)
        cr.execute(invoice_sql)
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
            detail_list_first.append((line.get('date_invoice').strftime("%Y-%m-%d")))
            # detail_list_first.append(line.get('date_invoice'))
            # _logger.debug('=============%s=============', line.get('auid'))
            if not user_name:
                user_obj = self.env['res.users'].search([('id', '=', int(line.get('auid')))])
                # _logger.debug('==========================%s', user_obj)
                ruser_name = user_obj.partner_id.name
                detail_list_first.append(ruser_name)
            else:
                detail_list_first.append(user_name)
            # detail_list_first.append(user_name)
            detail_list_first.append(line.get('sname'))
            detail_list_first.append(line.get('partner_ponumber'))
            detail_list_first.append(line.get('rname'))
            detail_list_first.append(line.get('symbol')+str(line.get('amount_total')))
            detail_list_first.append(line.get('symbol')+str(line.get('residual')))
            detail_list_first.append(line.get('cname'))
            detail_list_first.append(line.get('is_invoice'))
            detail_list_first.append(line.get('is_send'))
            detail_list_first.append(line.get('acct_note'))
            detail_list_all.append(detail_list_first)

        dir_path = os.path.join(file_url, 'Administrator')
        filename = "{}.xls".format(file_name_str)
        file_path = os.path.join(dir_path, filename)
        check_path(file_path)
        # encode('utf-8')

        head = ['序号','日期', '负责人', '合同号', '客户订单号','客户名称','总计','到期金额','币种','是否开票','是否发货','备注']
        self.save_exel(head, detail_list_all, file_path)

        return self.export_record(file_path)









