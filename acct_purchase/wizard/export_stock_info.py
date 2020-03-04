#coding=utf-8
from odoo import models,fields,api
import datetime,time
import xlwt
from datetime import datetime,timedelta
# import pandas as pd
import sys,os
file_url = 'my_addons/acct_purchase'
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

class ExportStockWizard(models.TransientModel):
    _name = "export.accstock.wizard"

    # date_start = fields.Datetime(string='起始日期',default=lambda self:fields.Datetime.now())
    origin = fields.Char(string='项目号')
    # charge_person = fields.Many2one('res.users',string=u'负责人')



    def save_exel(self, header, body, file_name):
        wbk = xlwt.Workbook(encoding='utf-8', style_compression=0)
        # wbk.write(codecs.BOM_UTF8)
        style1 = xlwt.easyxf('font: bold True;''alignment: horz center,vert center')
        sheet = wbk.add_sheet('项目未到货物料表', cell_overwrite_ok=True)
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
        导出未到货物料表
        :return:
        """
        return {
            'type': 'ir.actions.act_url',
            'url': '/download/work/files_export?file=%s' % (file_name),
            'target': 'self'
        }
    def export_stock_info_record(self):
        origin = self.origin
        today = time.strftime("%Y-%m-%d")
        cr = self.env.cr
        # if self.charge_person and not self.purchase_company:
        file_name_str = origin + '-' + '未到货物料' + today
        sql = """   SELECT
                        b. NAME AS rname,
                        d. NAME AS pname,
                        A . NAME AS product_model,
                        A .product_qty AS product_qty,
                        A .qty_received AS qty_received,
                        e. NAME AS po_number,
                        A .forcast_date AS forcast_date,
                        e.title AS ptitle
                    FROM
                        purchase_order_line A
                    LEFT JOIN purchase_order e ON A .order_id = e.id
                    LEFT JOIN res_partner b ON b. ID = A .partner_id
                    LEFT JOIN product_product C ON C . ID = A .product_id
                    LEFT JOIN product_template d ON d. ID = C .product_tmpl_id
                    WHERE
                       (a.qty_received IS NULL or a.qty_received < a.product_qty)
                    and e.title = '%s'
                    and e.state = 'purchase' """%(origin)
        cr.execute(sql)
        result = cr.dictfetchall()
        detail_list_all=[]

        # print result
        # strftime("%Y%m%d_%H%M%S")
        i= 0
        for line in result:
            detail_list_first = []
            i += 1
            detail_list_first.append(i)
            detail_list_first.append(line.get('rname'))
            detail_list_first.append(line.get('pname'))
            detail_list_first.append(line.get('product_model'))
            detail_list_first.append(line.get('product_qty'))
            if line.get('qty_received'):
                detail_list_first.append(line.get('qty_received'))
            else:
                detail_list_first.append(0)
            detail_list_first.append(line.get('po_number'))
            if line.get('forcast_date'):
                detail_list_first.append(line.get('forcast_date').strftime("%Y-%m-%d"))
            else:
                detail_list_first.append(line.get('forcast_date'))
            # detail_list_first.append(line.get('forcast_date'))
            detail_list_first.append(line.get('ptitle'))
            # detail_list_first.append(str(line.get('amount_total')))
            # detail_list_first.append(str(line.get('residual')))
            # detail_list_first.append(line.get('symbol')+str(line.get('amount_total')))
            # detail_list_first.append(line.get('symbol')+str(line.get('residual')))
            detail_list_all.append(detail_list_first)

        dir_path = os.path.join(file_url, 'Administrator')
        filename = "{}.xls".format(file_name_str)
        file_path = os.path.join(dir_path, filename)
        check_path(file_path)
        # encode('utf-8')

        head = ['序号','供应商', '品名', '型号', '采购数量','已接收数量','订单号','预计到货日期','项目号']
        self.save_exel(head, detail_list_all, file_path)

        return self.export_record(file_path)









