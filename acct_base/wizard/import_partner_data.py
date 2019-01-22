#coding=utf-8
from odoo import http,fields,models
import base64

class ImportPartnerWizard(models.TransientModel):
    _name = 'import.partner.wizard'

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
                self.env['res.partner'].import_supply(content=data)
            #     elif type == 'attendance':
            #         self.env['resource.calendar.attendance'].import_attendance_list(content=data)

