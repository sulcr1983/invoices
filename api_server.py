import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from system.api_server import app

if __name__ == '__main__':
    print("天颐发票处理系统 API服务器启动中...")
    print("访问地址: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
