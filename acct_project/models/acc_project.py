# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID, fields, models, _
from odoo.http import request
import logging
import xlrd
from collections import Counter
import re
import datetime

import pytz

from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
# from datetime import datetime
# from ..controllers.common import localizeStrTime
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class AccProjectTask(models.Model):
    """
     库存移动继承
    """
    _inherit = "project.task"

    task_start = fields.Date(string=u'开始日期')

class AccProjectProject(models.Model):
    """
     库存移动继承
    """
    _inherit = "project.project"

    project_code = fields.Char(string=u'项目号')
    equipment = fields.Char(string=u'需求设备名称&数量')
    delivery_time = fields.Date(string='交货期')
    priority_level = fields.Selection([('commonly', '一般'), ('urgent', '紧急')], '优先级', default='commonly')
    machine_design = fields.Char(string='机械设计人员')
    electrical_design = fields.Char(string='电气设计人员')
    software_design = fields.Char(string='软件设计人员')
    # design_sdate = fields.Date(string='设计开始日期')
    # design_edate = fields.Date(string='设计结束日期')
    # purchase_sdate = fields.Date(string='采购开始日期')
    # purchase_edate = fields.Date(string='采购结束日期')
    design_date = fields.Char(string='设计起止日期')
    purchase_date = fields.Char(string='采购起止日期')
    assembling_date = fields.Char(string='装配起止日期')
    send_date = fields.Date(string='发货日期')
    debugging_date = fields.Char(string='调试起止日期')
    note = fields.Char(string='备注')









    

