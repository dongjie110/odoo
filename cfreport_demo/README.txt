这是康虎云报表与odoo集成的示例程序，请按以下方法安装：

1、按正常方法安装 cfreport_demo 模块，该模块已经设置了依赖：
'base', 'sale','product', 'cfprint'
会自动安装；

2、这一步一定一定要看清楚，很多同学就没细看这一步！！！
从模块 cfreport_demo/templates 目录下把
product_label.fr3
和
report_saleorder.fr3
两个文件复制到康虎云报表的 cfprint/templates 目录下。

3、启动康虎云报表打印伺服程序： cfprint.exe

4、登录odoo,
从菜单 "销售" --> "销售订单" 进入打印 订单/询价单
从菜单 "销售" --> "产品" 进入打印 产品标签

