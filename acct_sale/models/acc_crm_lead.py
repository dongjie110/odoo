# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
import logging
from datetime import datetime
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class AccCrmLead(models.Model):
    """
     库存移动继承
    """
    _inherit = "crm.lead"

    contact_id = fields.Many2one('res.partner',string='联系人')
    acc_quotation_id = fields.Many2one('acc.quotation',string='挚锦报价单',readonly=True)


    def search(self, args, offset=0, limit=None, order=None, count=False):
        args = args or []
        if self._uid == 2:
            return super(AccCrmLead, self).search(args, offset, limit, order, count)
        # 管理部门
        elif self.env.user.has_group('acct_base.acc_manage_level1_group'):
            return super(AccCrmLead, self).search(args, offset, limit, order, count)
        # 销售部经理
        elif self.env.user.has_group('acct_base.unovo_it_info_group'):
            uids = self.get_department(self._uid)
            args.extend([('user_id', 'in', uids)])
            return super(AccCrmLead, self).search(args, offset, limit, order, count)
        # 普通员工
        else:
            args.extend([('user_id', '=', self._uid)])
        return super(AccCrmLead, self).search(args, offset, limit, order, count)

    @api.multi
    def get_department(self,user_id):
        department_ids = []
        employee_id = self.env['hr.employee'].search([('user_id', '=', user_id)])
        department_id = self.env['hr.department'].search([('manager_id', '=', employee_id.id)])
        if department_id:
            for did in department_id:
                department_ids.append(did.id)
            # department_name = department_id.name
            # if department_name in ['销售一部','销售二部','销售三部']:
            uids = self.make_sale_uid(department_ids,user_id)
            return uids

    @api.multi
    def make_sale_uid(self,department_ids,user_id):
        all_ids = []
        cr = self.env.cr
        all_total = """ SELECT
                            ru.id as uid
                        FROM
                            hr_employee he
                        LEFT JOIN res_users ru ON he.user_id = ru. ID
                        WHERE
                            department_id in %s """
        # cr.execute(all_total)
        cr.execute(all_total, (tuple(department_ids),))
        result = cr.dictfetchall()
        for line in result:
            all_ids.append(line['uid'])
        all_ids.append(user_id)
        return tuple(all_ids)

    @api.multi
    def acc_quotation_list(self):
        domain = [('crm_lead_id', '=', self.id)]
        return {
            'name': _('挚锦报价单'),
            'domain': domain,
            'res_model': 'acc.quotation',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'limit': 80,
            'context': "{'crm_lead_id': %d}" % (self.id)
        }