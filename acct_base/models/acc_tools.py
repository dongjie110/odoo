# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.addons import decimal_precision as dp
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
import datetime as dt
import smtplib
import logging
import time
import requests
import json
import hashlib
_logger = logging.getLogger(__name__)


class AccTools(models.Model):
    _name = 'acc.tools'
    _description = u"锐驰邮件工具"
    name = fields.Char(string=u"名称")

    @api.model
    def send_report_email(self,subjects,message,toaddrs):
        '''''
        @subject:邮件主题
        @msg:邮件内容
        @toaddrs:收信人的邮箱地址
        @fromaddr:发信人的邮箱地址
        @smtpaddr:smtp服务地址，可以在邮箱看，比如163邮箱为smtp.163.com
        @password:发信人的邮箱密码
        '''
        fromaddr = "notreply@acctronics.cn"
        smtpaddr = "smtp.exmail.qq.com"
        # toaddrs = ['jie.dong@acctronics.cn']
        toaddrs = toaddrs
        # subject = "最新消息"
        subject = subjects
        password = "Neotel@12345"
        # msg = "测试"
        msg = message
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
            _logger.info("邮件发送成功")
        except Exception as e:
            print ("Error: unable to send email")
            _logger.info("邮件发送失败")

    def get_users(self,group_name):
        commerce_group = self.env['res.groups'].search([('name', '=', group_name)])
        gid = commerce_group.id
        cr = self.env.cr
        sql = """
                select * from res_groups_users_rel where gid = %s
        """%(gid)
        cr.execute(sql)
        result = cr.dictfetchall()
        uids = [m['uid'] for m in result]
        # lists = [1,2]
        to_addr = []
        for user in uids:
        	user_obj = self.env['res.users'].search(['id','=', user])
        	to_addr.append(user_obj.login)
        return to_addr

    @api.multi
    def make_acccode(self):
        pt = self.env['product.template'].search([])
        n = 1
        for i in pt:  
            s = "%05d" % n
            code = 'ACC-PRO-' + s 
            i.write({'acc_code':code})
            n += 1
            print (i.name)
            _logger.debug('===========%s===============', i.name)
        i.write({'active': False})

    @api.multi
    def make_acccode(self):
        pt = self.env['product.template'].search(['name', 'like', 'ACC-PRO-'])
        for i in pt:
            i.write({'acc_code':code})
            _logger.debug('===========%s===============', i.name)

class AccMessageInterface(models.Model):
    _name = 'acc.message.interface'
    _description = u"短信接口"
    _order = "id desc"

    phone = fields.Char(string='手机号码',required=True,)
    user_name = fields.Char(string='姓名',required=True,) 
    create_date = fields.Datetime(string="创建时间",readonly = True,default=time.strftime('%Y-%m-%d %H:%M:%S'),)
    write_date = fields.Datetime(string="最后发送时间",readonly = True)
    topic = fields.Text(string="标题",)
    name = fields.Text(string="短信内容",)
    note = fields.Text(string="失败原因",)
    state = fields.Selection([('draft',u'待发送'), ('done', u'已发送'),('error', u'发送失败'),],string=u'发送状态',default='draft',required=True, readonly = True)

    # def sms_send(self, cr, uid, ids, context=None):
        # sms = self.read(cr, uid, ids, ['phone', 'name', 'topic', 'user_name'], context=context)
        # for sms in self.browse(cr, uid, ids, context=context):
        #     text = sms.name
        #     phones = sms.phone
        #     topic = sms.topic
        #     if not phones:
        #         _logger.warning(u"%s手机号不存在!"%sms.user_name, )
        #         return False
        #     try:
        #         import requests
        #         import json
        #         url = 'http://121.43.62.168/messagecenter/api/20150927/system/messagecenter/send'
        #         args = {"channel": 102, "targets": json.dumps([phones]), 'topic': topic, 'content': text}
        #         respon = requests.post(url, data=args)
        #         result = json.loads(respon.text)
        #         if result.get('errorCode',False) == 0:
        #             self.write(cr, uid, sms.id, {'state': 'done','write_date':time.strftime('%Y-%m-%d %H:%M:%S'),}, context=context)
        #         else :
        #             note = result.get('message',False)
        #             self.write(cr, uid, sms.id, {'state': 'error','note':note,'write_date':time.strftime('%Y-%m-%d %H:%M:%S'),}, context=context)
        #     except Exception as e:
        #         self.write(cr, uid, sms.id, {'state': 'error'}, context=context)
        #         continue
        # return True
  
    @api.multi
    def sms_send(self):
        # sms = self.read(['phone', 'name', 'topic', 'user_name'], context=context)
        for sms in self:
            text = sms.name
            phones = sms.phone
            topic = sms.topic
            if not phones:
                _logger.warning(u"%s手机号不存在!"%sms.user_name, )
                return False
            try:
                url="http://sms3.mobset.com/SDK2/Sms_Send.asp"
                # str_time = "2019-11-12 10:23:10"
                # time_array = time.strptime(str_time, "%m%d%H%M%S")
                # fields.Datetime.now()
                now_date = fields.Datetime.now() + dt.timedelta(hours=8)
                time_array = (now_date.strftime('%m%d%H%M%S'))
                # hashs = '300238' + 'Rk135802' + time_array
                # str_md5 = hashlib.md5(hashs).hexdigest()
                m=hashlib.md5()
                strs='300238' + 'Rk135802' + time_array
                m.update(strs.encode("utf8"))
                str_md5 = m.hexdigest()
                # print(m.hexdigest())
                args = {"CorpID": "300238", "LoginName": "Admin", "TimeStamp": time_array, "send_no": phones,
                        "msg": text, "Passwd": str_md5}
                respons = requests.post(url, data=args)
                # result = response.json()
                result = json.loads(respons.text)
            except Exception as e:
                self.write({'state': 'error'})
                continue
        return True
        # hashs = '300238' + 'Rk135802' + '1111172309'
        # SecretKey = hashlib.md5()
        # SecretKey.update(hashs.encode("utf-8"))
        # # b = str.encode(encoding='utf-8')
        # # m.update(b)
        # # str_md5 = m.hexdigest()
        # # Passwd = "300238Rk1358020517171100"
        # # ts = datetime.now().timestamp()
        # str_md5 = hashlib.md5(b'300238Rk1358021111172309').hexdigest()
        # url="http://sms3.mobset.com/SDK2/Sms_Send.asp"
        # args = {"CorpID":"300238", "LoginName":"Admin","TimeStamp":"1111172309" ,"send_no":"17621827400","msg":"test message","Passwd":str_md5}
        # respons = requests.post(url, data=args)
        # print (respons)
        # result = json.loads(respons.text)
        # return result

    # def schedule_send(self, cr, uid, ids=False,context=None):
    #     self.sms_send(cr, uid, ids, context=None)
        

