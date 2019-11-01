#coding=utf-8
from odoo import http,fields,models
import base64

class ImportBomWizard(models.TransientModel):
    _name = 'import.bom.wizard'

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
                self.env['mrp.bom'].import_bom_charge(content=data)

# class ImportPurchaseLineWizard(models.TransientModel):
#     _name = 'import.purchase.line.wizard'

#     file_name = fields.Char(u'文件名')
#     data = fields.Binary(u'导入文件')
#     selected = fields.Integer(u'当前已选')
#     exported = fields.Integer(u'之前导出')

#     def import_data_all(self):
#         context = self.env.context or {}
#         type = context.get('type',None)
#         data = self.data
#         if data:
#             data = base64.b64decode(data)
#             if data:
#                 self.env['purchase.order.line'].import_purchase_line_data(content=data)
