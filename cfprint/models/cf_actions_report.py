# -*- coding: utf-8 -*-
####################################################
#  康虎云报表模板存储
#  该表中以Base64格式存储康虎云报表，可以方便地取
#  出来嵌入到康虎云报表打印数据(json)中
#
#
####################################################

import logging
import base64
from datetime import datetime
from odoo import fields, models, api, http, _
from odoo.http import request
# from cStringIO import StringIO
from io import StringIO
from werkzeug.utils import redirect
import warnings
from decimal import Decimal

_logger = logging.getLogger(__name__)

def _get_cfprint_template(env, templ_id):
    """
    根据模板ID查询康虎云报表模板，用法如下：
    <t t-esc="cf_template(user.env, '12345')" />
    如果不使用这种方法，也可以在QWeb模板中按下面的方法取得模板内容：
    <t t-esc="user.env['cf.template'].search([('templ_id', '=', '12345')], limit=1).template" />
    取得模板
    :param env:         Env对象，在qweb模板中可以通过user.env或res_company.env取到
    :param templ_id:    模板唯一编号
    :return:
    """
    if (env is not None) and (templ_id is not None):
        templ = env['cf.template'].search([('templ_id', '=', templ_id)], limit=1)
        if len(templ)>0 :
            return templ.template.decode().replace('\n', '').replace(' ', '')   #去掉Base64中的换行符然后返回

    #条件无效或无相符记录，则返回空字符串
    return ''

def _convert_cn_currency(value, capital=True, prefix=u'人民币', postfix=u'元'):
    '''
    把金额转成中文大写
    用法：
    <t t-esc="_convert_cn_currency(1234.56, True, '￥', '圆')" />
    参数:
    capital:    True   大写汉字金额
                False  一般汉字金额
    prefix:     默认以'人民币'开头
    classical:  True   元
                False  圆
    '''
    # if not isinstance(value, (Decimal, str, int)):
    #     msg = u'由于浮点数精度问题，请考虑使用字符串，或者 decimal.Decimal 类。\
    #     因使用浮点数造成误差而带来的可能风险和损失作者概不负责。'
    #     warnings.warn(msg, UserWarning)

    # 金额前缀
    prefix = prefix if prefix else ''

    #金额后缀，默认是“元”
    postfix = postfix if postfix else u'元'

    # 汉字金额字符定义
    dunit = (u'角', u'分')
    if capital:
        num = (u'零', u'壹', u'贰', u'叁', u'肆', u'伍', u'陆', u'柒', u'捌', u'玖')
        iunit = [None, u'拾', u'佰', u'仟', u'万', u'拾', u'佰', u'仟', u'亿', u'拾', u'佰', u'仟', u'万', u'拾', u'佰', u'仟']
    else:
        num = (u'○', u'一', u'二', u'三', u'四', u'五', u'六', u'七', u'八', u'九')
        iunit = [None, u'十', u'百', u'千', u'万', u'十', u'百', u'千', u'亿', u'十', u'百', u'千', u'万', u'十', u'百', u'千']

    iunit[0] = postfix

    # 转换为Decimal，并截断多余小数
    if not isinstance(value, Decimal):
        value = Decimal(value).quantize(Decimal('0.01'))

    # 处理负数
    if value < 0:
        prefix += u'负'  # 输出前缀，加负
        value = - value  # 取正数部分，无须过多考虑正负数舍入
        # assert - value + value == 0
    # 转化为字符串
    s = str(value)
    if len(s) > 19:
        raise ValueError(u'金额太大了，不知道该怎么表达。')
    istr, dstr = s.split('.')  # 小数部分和整数部分分别处理
    istr = istr[::-1]  # 翻转整数部分字符串
    so = []  # 用于记录转换结果

    # 零
    if value == 0:
        return prefix + num[0] + iunit[0]
    haszero = False  # 用于标记零的使用
    if dstr == '00':
        haszero = True  # 如果无小数部分，则标记加过零，避免出现“圆零整”

    # 处理小数部分
    # 分
    if dstr[1] != '0':
        so.append(dunit[1])
        so.append(num[int(dstr[1])])
    else:
        so.append(u'整')  # 无分，则加“整”

    # 角
    if dstr[0] != '0':
        so.append(dunit[0])
        so.append(num[int(dstr[0])])
    elif dstr[1] != '0':
        so.append(num[0])  # 无角有分，添加“零”
        haszero = True  # 标记加过零了

    # 无整数部分
    if istr == '0':
        if haszero:  # 既然无整数部分，那么去掉角位置上的零
            so.pop()
        so.append(prefix)  # 加前缀
        so.reverse()  # 翻转
        return ''.join(so)

    # 处理整数部分
    for i, n in enumerate(istr):
        n = int(n)
        if i % 4 == 0:  # 在圆、万、亿等位上，即使是零，也必须有单位
            if i == 8 and so[-1] == iunit[4]:  # 亿和万之间全部为零的情况
                so.pop()  # 去掉万
            so.append(iunit[i])
            if n == 0:  # 处理这些位上为零的情况
                if not haszero:  # 如果以前没有加过零
                    so.insert(-1, num[0])  # 则在单位后面加零
                    haszero = True  # 标记加过零了
            else:  # 处理不为零的情况
                so.append(num[n])
                haszero = False  # 重新开始标记加零的情况
        else:  # 在其他位置上
            if n != 0:  # 不为零的情况
                so.append(iunit[i])
                so.append(num[n])
                haszero = False  # 重新开始标记加零的情况
            else:  # 处理为零的情况
                if not haszero:  # 如果以前没有加过零
                    so.append(num[0])
                    haszero = True

    # 最终结果
    so.append(prefix)
    so.reverse()
    return u''.join(so)


class CFTemplateCategory(models.Model):
    """
    康虎云报表模板分类
    """
    _name = 'cf.template.category'
    _description = _(u"Report templates category of CFPrint")

    name = fields.Char(string=u"Category Name", required=True)
    lines = fields.One2many("cf.template", "category_id", string=u"Templates")
    # templ_histories = fields.One2many("cf.template.history", "category_id", string=u"Templates History")

    _sql_constraints = [
        ('cons_cf_templ_category', 'unique(name)', u'Template category name already exists!')
    ]

class CFTemplate(models.Model):
    """
    康虎云报表模板模型类，通过该模型把康虎云报表保存在服务器数据库中，便于统一管理模板
    """
    _name = 'cf.template'
    _description = _(u"Report templates of CFPrint")

    category_id = fields.Many2one("cf.template.category", string=u"Category")
    templ_id = fields.Char(u'Template ID', required=True, help=u'Unique ID of template')
    name = fields.Char(u'Name', required=True)
    description = fields.Text(u'Description', required=False)
    preview_img = fields.Binary(u'Preview image', required=False, help=u'Picture used to preview a report')
    template = fields.Binary(u'Template', required=True, help=u'Content of template')
    template_filename = fields.Char(string=u'Template Filename', compute="_compute_template_filename")
    templ_histories = fields.One2many('cf.template.history', 'origin', string=u'History', help=u"History of template")

    _sql_constraints = [
        ('cons_cf_templ_id', 'unique(templ_id)', u'Template ID already exists!')
    ]

    @api.multi
    def write(self, values):
        # 保存模板历史
        # 模板ID未更新时，表示是模板更新,需要保存历史记录，否则是新建模板
        if 'templ_id' not in values and \
                ("template" in values or "category_id" in values or "name" in values or "description" in values ):
            self.env['cf.template.history'].create({
                "category_id": self.category_id.id,
                'origin': self.id,
                "ver": datetime.strftime(self.write_date, "%Y%m%d%H%M%S"),
                "templ_id":self.templ_id,
                "name":self.name,
                "description":self.description,
                "preview_img":self.preview_img,
                "template":self.template,
            })

        return super(CFTemplate, self).write(values)

    @api.multi
    def _compute_template_filename(self):
        for templ in self:
            templ.template_filename = templ.templ_id + ".fr3"


class CFTemplateHistory(models.Model):
    """
    康虎云报表模板历史版本，通过该模型把康虎云报表保存在服务器数据库中，便于统一管理模板
    """
    _name = 'cf.template.history'
    _description = _(u"History of report templates of CFPrint")

    category_id = fields.Many2one("cf.template.category", string=u"Category")
    origin = fields.Many2one('cf.template', string=u'Origin Template')
    ver = fields.Char(string=u"Version", help=u"Version of template")
    templ_id = fields.Char(string=u'Template ID', required=True, help=u'Unique ID of template')
    name = fields.Char(string=u'Name', required=True)
    description = fields.Text(string=u'Description', required=False)
    preview_img = fields.Binary(string=u'Preview image', required=False, help=u'Picture used to preview a report')
    template = fields.Binary(string=u'Content', required=True, help=u'Content of template')
    template_filename = fields.Char(string=u'Template Filename', compute="_compute_template_filename")

    @api.multi
    def _compute_template_filename(self):
        for templ in self:
            templ.template_filename = "%s_%s.fr3"%(templ.templ_id, templ.ver)

    _sql_constraints = [
        ('cons_cf_templ_id_ver', 'unique(templ_id, ver)', u'Same version and template ID already exists!')
    ]

class IrActionsReport(models.Model):
    """
    继承ir.actions.report基类，增加自定义函数输出到QWeb模板中，方便在模板中便捷取康虎云报表模板

    在模板可以直接使用的对象有：
    get_cf_template：根据env和模板ID获取保存在数据库中的模板。示例：<t t-esc="cf_template(user.env, 'cf.sale.order')" />
    get_cn_currency：把金额转成中文，arg1: 数字金额，arg2: 是否显示大写汉字，arg3: 金额前缀，arg4: 金额后缀（单位）。示例：<t t-esc="_convert_cn_currency(1234.56, True, '人民币', '圆')" />
    get_local_time：把timestamp转成本地时间，与context_timestamp相同
    to_base64： 把指定内容进行base64编码。参数： value： 要转换的内容，altchars：用以替换'+'和'/'的替代字符，一般用以生成url时需要替换
    from_base64： 把指定内容进行base64解码。参数： value： 要转换的内容，altchars：用以替换'+'和'/'的替代字符，一般用以生成url时需要替换

    time：python自带的time工具文件，里面有一堆时间处理函数
    context_timestamp：把timestamp转成本地时间，与get_local_time相同
    user：当前user对象
    res_company：当前user所在公司对象
    website：website对象（如果request中没有website属性，则是None)
    web_base_url：配置信息中的web.base.url值（网站base URL）
    """
    _inherit = "ir.actions.report"
    _description = "Report action extend from base/ir/ir_action_report.py"

    @api.multi
    def render_template(self, template, values=None):
        """
        继承ir.actions.report对象的渲染方法，在上下文中增加模板对象ORM
        :param template:    模板对象
        :param values:      在渲染时使用的额外方法/变量
        :return:            模板的HTML表示
        """
        if values is None:
            values = {}

        ####################################
        user = self.env['res.users'].browse(self.env.uid)
        # 暴露给模板使用的工具函数
        values.update(
            get_cf_template = _get_cfprint_template,      #把获取模板函数传入模板
            get_cn_currency = _convert_cn_currency,     #把金额转成中文大写
            get_local_time = lambda t: fields.Datetime.context_timestamp(self.with_context(tz=user.tz), t),    #把时间转换成本地时间
            to_base64 = lambda value, altchars: base64.b64encode(value, altchars),  #把内容转成base64
            from_base64 = lambda value, altchars: base64.b64decode(value, altchars),  # 把base64内容解码
        )

        obj = super(IrActionsReport, self).render_template(template, values)
        return obj
