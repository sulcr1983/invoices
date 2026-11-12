import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持直接运行 python system/api_server.py）
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import os
import logging

from flask import Flask, jsonify

from system.config import setup_logging
from system.routes import dashboard_bp, invoices_bp, stats_bp, tasks_bp, system_bp
from system.routes.shared import api_error

logger = logging.getLogger(__name__)


def create_app():
    # 日志必须在任何业务代码前初始化，否则 Web 模式全程无日志落盘
    setup_logging()

    # 启动即做一次数据库热备份（<db>.backup），避免单文件损坏导致全量丢失
    try:
        from system.routes.shared import db_manager
        db_manager.backup_database()
    except Exception as e:
        logger.error(f"启动备份失败: {e}")

    app = Flask(__name__,
                static_folder=None,
                template_folder=None)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(system_bp)

    @app.errorhandler(500)
    def handle_500(error):
        msg, code = api_error(str(error), 500)
        return jsonify(msg), code

    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({'status': 'error', 'message': '请求的资源不存在'}), 404

    @app.after_request
    def after_request(response):
        # 仅允许本机来源，避免任意网页跨域读取台账
        origin = request_origin()
        if origin:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        return response

    return app


def request_origin():
    """放行本机来源（localhost / 127.0.0.1，任意端口），其余不返回 CORS 头。"""
    from flask import request
    origin = request.headers.get('Origin', '')
    if not origin:
        return ''
    allowed_prefixes = ('http://localhost', 'http://127.0.0.1')
    return origin if origin.startswith(allowed_prefixes) else ''


app = create_app()


if __name__ == '__main__':
    # 默认仅监听本机；容器/局域网场景可用 INVOICE_HOST=0.0.0.0 覆盖
    host = os.environ.get('INVOICE_HOST', '127.0.0.1')
    port = int(os.environ.get('INVOICE_PORT', '5000'))
    print(f"SuperSu 发票处理系统 API服务器启动中...")
    print(f"访问地址: http://{'localhost' if host == '127.0.0.1' else host}:{port}")
    print("按 Ctrl+C 停止服务器")
    app.run(host=host, port=port, debug=False)