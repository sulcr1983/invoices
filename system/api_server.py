from flask import Flask, jsonify

from .routes import dashboard_bp, invoices_bp, stats_bp, tasks_bp, system_bp
from .routes.shared import api_error


def create_app():
    app = Flask(__name__)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(system_bp)

    @app.errorhandler(500)
    def handle_500(error):
        return jsonify(api_error(str(error), 500))

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

if __name__ == '__main__':
    print("天颐发票处理系统 API服务器启动中...")
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    app.run(host='0.0.0.0', port=5000, debug=False)
