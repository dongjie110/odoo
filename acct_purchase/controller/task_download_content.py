# -*- coding: utf-8 -*-
from odoo import http
import os
import sys
import logging
import datetime
import calendar
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception,content_disposition
_logger = logging.getLogger(__name__)
import base64
import zipfile
import shutil
from odoo.http import request
# import simplejson
# pic_url = "guide_addons/task_work_content"
# pic_download_url = os.path.join(sys.path[0],pic_url)

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
        # print arcname
        zf.write(tar, arcname)
    zf.close()


class DownloadFiles(http.Controller):

    @http.route('/download/work/files_export', type='http', auth="user")
    # @serialize_exception
    def download_sale_data(self, year=None, month=None, *args, **kwargs):
        data = request.params
        file = data.get('file')
        if file:
            # with open(file,encoding='UTF-8') as f:
            file_name = "{}".format(file[file.rfind('/')+1:])
            f=open(file, 'rb')
            content = f.read()
            # content = f.read()
            # content = base64.b64decode(f)
            # content.decode('latin-1').encode("utf-8")
            # content.encode('latin-1').decode('utf8')
            os.remove(file)
            return request.make_response(content,
                                         [('Content-Type', 'application/octet-stream'),
                                          ('Content-Disposition', content_disposition(file_name))]
                                         )