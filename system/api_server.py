import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持直接运行 python system/api_server.py）
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flask import Flask, jsonify

from system.routes import dashboard_bp, invoices_bp, stats_bp, tasks_bp, system_bp
from system.routes.shared import api_error


def create_app():
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
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        return response

    return app


app = create_app()


def _kill_port_occupants(port):
    import subprocess
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True, text=True, timeout=5
        )
        pids = set()
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and f':{port}' in parts[1] and parts[3] == 'LISTENING':
                try:
                    pids.add(int(parts[4]))
                except ValueError:
                    pass
        if pids:
            print(f"检测到端口 {port} 被占用 (PID: {pids})，正在释放...")
            for pid in pids:
                try:
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                                   capture_output=True, timeout=5)
                    print(f"  已终止进程 PID {pid}")
                except Exception:
                    pass
            import time
            time.sleep(1)
    except Exception as e:
        print(f"端口检测失败: {e}")


if __name__ == '__main__':
    _kill_port_occupants(5000)
    print("天颐发票处理系统 API服务器启动中...")
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    app.run(host='0.0.0.0', port=5000, debug=False)
