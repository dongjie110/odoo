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








    

