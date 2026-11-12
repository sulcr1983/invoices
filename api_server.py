import os

from system.api_server import app
from system.config import setup_logging

if __name__ == '__main__':
    setup_logging()
    host = os.environ.get('INVOICE_HOST', '127.0.0.1')
    port = int(os.environ.get('INVOICE_PORT', '5000'))
    print("SuperSu 发票处理系统 API服务器启动中...")
    print(f"访问地址: http://{'localhost' if host == '127.0.0.1' else host}:{port}")
    print("按 Ctrl+C 停止服务器")
    app.run(host=host, port=port, debug=False)