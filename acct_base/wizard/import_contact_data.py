#coding=utf-8
# from odoo import http,fields,models
import base64
# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
import smtplib
import logging
import time
_logger = logging.getLogger(__name__)

class ImportContactWizard(models.TransientModel):
    _name = 'import.contact.wizard'

    file_name = fields.Char(u'文件名')
    data = fields.Binary(u'导入文件')
    selected = fields.Integer(u'当前已选')
    exported = fields.Integer(u'之前导出')

    def import_data_all(self):
        context = self.env.context or {}
        type = context.get('type',None)
        data = self.data
        if data:
            data = base64.b64decode(data)
            if data:
                # print data
                # if type == 'hr_employee':
                self.env['res.partner'].import_contact(content=data)
            #     elif type == 'attendance':
            #         self.env['resource.calendar.attendance'].import_attendance_list(content=data)

       
    def send(self):
        """
        @subject:邮件主题
        @msg:邮件内容
        @toaddrs:收信人的邮箱地址
        @fromaddr:发信人的邮箱地址
        @smtpaddr:smtp服务地址，可以在邮箱看，比如163邮箱为smtp.163.com
        @password:发信人的邮箱密码
        """
        fromaddr = "notreply@acctronics.cn"
        smtpaddr = "smtp.exmail.qq.com"
        toaddrs = ['jie.dong@acctronics.cn','yapeng.dai@acctronics.cn']
        subject = "最新消息"
        password = "Acc@acc123"
        msg = "测试"
        mail_msg = MIMEMultipart()
        # if not isinstance(subject, unicode):
        #     subject = unicode(subject, 'utf-8')
        mail_msg['Subject'] = subject
        mail_msg['From'] = fromaddr
        mail_msg['To'] = ','.join(toaddrs)
        mail_msg.attach(MIMEText(msg, 'html', 'utf-8'))
        try:
            # smtplib.SMTP_SSL(host='smtp.gmail.com').connect(host='smtp.gmail.com', port=465)
            s = smtplib.SMTP_SSL(smtpaddr)
            s.connect(smtpaddr,465)  # 连接smtp服务器
            s.login(fromaddr, password)  # 登录邮箱
            s.sendmail(fromaddr, toaddrs, mail_msg.as_string())  # 发送邮件
            s.quit()
        except Exception as e:
            print ("Error: unable to send email")
            # print (traceback.format_exc())