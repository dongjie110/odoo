#coding=utf-8
from odoo import models,fields,api
import datetime
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

class ExportPurchaseWizard(models.TransientModel):
    _name = "export.purchase.wizard"

    date_start = fields.Datetime(string='起始日期',default=lambda self:fields.Datetime.now())
    date_end = fields.Datetime(string='结束日期')
    product_state = fields.Selection([('new', '未到货'), ('part', '部分到货'), ('all', '全部到货'), ('cancel', '取消订单')], '产品到货状态')
    payment_state = fields.Selection([('partpay', '部分已付'), ('nopay', '未付'), ('allpay', '全部付清')], '付款状态')



    def save_exel(self, header, body, file_name):
        wbk = xlwt.Workbook(encoding='utf-8', style_compression=0)
        # wbk.write(codecs.BOM_UTF8)
        style1 = xlwt.easyxf('font: bold True;''alignment: horz center,vert center')
        sheet = wbk.add_sheet('支付方式表', cell_overwrite_ok=True)
        # sheet.write(codecs.BOM_UTF8) 

        sheet.write(0, 0, 'some text')
        sheet.write(0, 0, 'this should overwrite')  ##重新设置，需要cell_overwrite_ok=True
        n = 0
        for i in xrange(len(header)):
            sheet.write(n, i, header[i])

        # font0 = xlwt.Font()
        # font0.name = 'Times New Roman'
        # font0.colour_index = 2
        # font0.bold = True
        #
        # style0 = xlwt.XFStyle()
        # style0.font = font0

        for i in xrange(len(body)):
            n += 1
            for j in xrange(len(body[i])):
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
    def export_purchase_record(self):

        product_state = self.product_state
        payment_state = self.payment_state
        date_start = self.date_start
        cr = self.env.cr
        if not product_state and not payment_state:
            all_total = """ SELECT
                                po.create_date::timestamp + '8 hour' AS create_date,
                                ru.login AS apply_person,
                                po. NAME AS apply_code,
                                po.title AS project_name,
                                pt.brand AS brand,
                                pt. NAME AS product_name,
                                pt.product_model AS product_model,
                                pol.product_qty AS qty,
                                rp. NAME AS supplier,
                                pol.price_unit AS price,
                                pol.price_subtotal AS amount,
                                po.forcast_date AS forcast_date,
                                po.forcast_date AS actual_date,
                                CASE po.product_state
                                  WHEN 'new' THEN '未到货'
                                    WHEN 'part' THEN '部分到货'
                                    WHEN 'all'  THEN '全部到货'
                                    ELSE '取消订单' END AS product_state,
                                CASE po.payment_state
                                  WHEN 'partpay' THEN '部分已付'
                                    WHEN 'nopay' THEN '未付'
                                    ELSE '全部付清' END AS payment_state
                            FROM
                                purchase_order_line pol
                            LEFT JOIN purchase_order po ON po. ID = pol.order_id
                            LEFT JOIN product_product pp ON pp. ID = pol.product_id
                            LEFT JOIN res_partner rp ON rp. ID = po.partner_id
                            LEFT JOIN product_template pt ON pt. ID = pp.product_tmpl_id
                            LEFT JOIN res_users ru on ru.id = po.charge_person
                            WHERE
                                po.create_date >= '%s'
                            AND po.create_date <= '%s' """%(self.date_start,self.date_end)
        if not product_state and payment_state:
            all_total = """ SELECT
                                po.create_date::timestamp + '8 hour' AS create_date,
                                ru.login AS apply_person,
                                po. NAME AS apply_code,
                                po.title AS project_name,
                                pt.brand AS brand,
                                pt. NAME AS product_name,
                                pt.product_model AS product_model,
                                pol.product_qty AS qty,
                                rp. NAME AS supplier,
                                pol.price_unit AS price,
                                pol.price_subtotal AS amount,
                                po.forcast_date AS forcast_date,
                                po.forcast_date AS actual_date,
                                CASE po.product_state
                                  WHEN 'new' THEN '未到货'
                                    WHEN 'part' THEN '部分到货'
                                    WHEN 'all'  THEN '全部到货'
                                    ELSE '取消订单' END AS product_state,
                                CASE po.payment_state
                                  WHEN 'partpay' THEN '部分已付'
                                    WHEN 'nopay' THEN '未付'
                                    ELSE '全部付清' END AS payment_state
                            FROM
                                purchase_order_line pol
                            LEFT JOIN purchase_order po ON po. ID = pol.order_id
                            LEFT JOIN product_product pp ON pp. ID = pol.product_id
                            LEFT JOIN res_partner rp ON rp. ID = po.partner_id
                            LEFT JOIN product_template pt ON pt. ID = pp.product_tmpl_id
                            LEFT JOIN res_users ru on ru.id = po.charge_person
                            WHERE
                                po.create_date >= '%s'
                            AND po.create_date <= '%s'
                            AND PO.payment_state = '%s' """%(self.date_start,self.date_end,payment_state)
        if product_state and not payment_state:
            all_total = """ SELECT
                                po.create_date::timestamp + '8 hour' AS create_date,
                                ru.login AS apply_person,
                                po. NAME AS apply_code,
                                po.title AS project_name,
                                pt.brand AS brand,
                                pt. NAME AS product_name,
                                pt.product_model AS product_model,
                                pol.product_qty AS qty,
                                rp. NAME AS supplier,
                                pol.price_unit AS price,
                                pol.price_subtotal AS amount,
                                po.forcast_date AS forcast_date,
                                po.forcast_date AS actual_date,
                                CASE po.product_state
                                  WHEN 'new' THEN '未到货'
                                    WHEN 'part' THEN '部分到货'
                                    WHEN 'all'  THEN '全部到货'
                                    ELSE '取消订单' END AS product_state,
                                CASE po.payment_state
                                  WHEN 'partpay' THEN '部分已付'
                                    WHEN 'nopay' THEN '未付'
                                    ELSE '全部付清' END AS payment_state
                            FROM
                                purchase_order_line pol
                            LEFT JOIN purchase_order po ON po. ID = pol.order_id
                            LEFT JOIN product_product pp ON pp. ID = pol.product_id
                            LEFT JOIN res_partner rp ON rp. ID = po.partner_id
                            LEFT JOIN product_template pt ON pt. ID = pp.product_tmpl_id
                            LEFT JOIN res_users ru on ru.id = po.charge_person
                            WHERE
                                po.create_date >= '%s'
                            AND po.create_date <= '%s'
                            AND PO.product_state = '%s' """%(self.date_start,self.date_end,product_state)
        if product_state and payment_state:
            all_total = """ SELECT
                                po.create_date::timestamp + '8 hour' AS create_date,
                                ru.login AS apply_person,
                                po. NAME AS apply_code,
                                po.title AS project_name,
                                pt.brand AS brand,
                                pt. NAME AS product_name,
                                pt.product_model AS product_model,
                                pol.product_qty AS qty,
                                rp. NAME AS supplier,
                                pol.price_unit AS price,
                                pol.price_subtotal AS amount,
                                po.forcast_date AS forcast_date,
                                po.forcast_date AS actual_date,
                                CASE po.product_state
                                  WHEN 'new' THEN '未到货'
                                    WHEN 'part' THEN '部分到货'
                                    WHEN 'all'  THEN '全部到货'
                                    ELSE '取消订单' END AS product_state,
                                CASE po.payment_state
                                  WHEN 'partpay' THEN '部分已付'
                                    WHEN 'nopay' THEN '未付'
                                    ELSE '全部付清' END AS payment_state
                            FROM
                                purchase_order_line pol
                            LEFT JOIN purchase_order po ON po. ID = pol.order_id
                            LEFT JOIN product_product pp ON pp. ID = pol.product_id
                            LEFT JOIN res_partner rp ON rp. ID = po.partner_id
                            LEFT JOIN product_template pt ON pt. ID = pp.product_tmpl_id
                            LEFT JOIN res_users ru on ru.id = po.charge_person
                            WHERE
                                po.create_date >= '%s'
                            AND po.create_date <= '%s'
                            AND PO.product_state = '%s'
                            AND PO.payment_state = '%s' """%(self.date_start,self.date_end,product_state,payment_state)
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
            detail_list_first.append((line.get('create_date').strftime("%Y-%m-%d %H:%M:%S"))[0:11])
            detail_list_first.append(line.get('apply_person'))
            detail_list_first.append(line.get('apply_code'))
            detail_list_first.append(line.get('project_name'))
            detail_list_first.append(line.get('brand'))
            detail_list_first.append(line.get('product_name'))
            detail_list_first.append(line.get('product_model'))
            detail_list_first.append(line.get('qty'))
            detail_list_first.append(line.get('supplier'))
            detail_list_first.append(line.get('price'))
            detail_list_first.append(line.get('amount'))
            if line.get('forcast_date'):
                detail_list_first.append(line.get('forcast_date').strftime("%Y-%m-%d"))
            else:
                detail_list_first.append(line.get('forcast_date'))
            if line.get('actual_date'):
                detail_list_first.append(line.get('actual_date').strftime("%Y-%m-%d"))
            else:
                detail_list_first.append(line.get('actual_date'))
            detail_list_first.append(line.get('product_state'))
            detail_list_first.append(line.get('payment_state'))


            detail_list_all.append(detail_list_first)

        dir_path = os.path.join(file_url, 'Administrator')
        filename = "{}.xls".format('orderout')
        file_path = os.path.join(dir_path, filename)
        check_path(file_path)
        # encode('utf-8')

        head = ['序号', '申请日期', '申请人','申请编号','项目','品牌','申请名称','申请型号','数量','供应商','单价','总金额','预计到货时间','实际到货时间','是否到货','是否付款']
        self.save_exel(head, detail_list_all, file_path)
        return self.export_record(file_path)










