import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_PARENT_DIR = os.path.dirname(_THIS_DIR)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file

try:
    from .db_manager import DBManager
    from .core.pipeline import run_pipeline, check_environment
    from .core.data_utils import calculate_file_md5
    from .services import scan_pending_files, ensure_directories
    from .config import INPUT_DIR as INPUT_INVOICES_DIR, DB_PATH, ARCHIVE_DIR, LOG_PATH, PROJECT_ROOT, err_to_cn
except ImportError:
    from db_manager import DBManager
    from core.pipeline import run_pipeline, check_environment
    from core.data_utils import calculate_file_md5
    from services import scan_pending_files, ensure_directories
    from config import INPUT_DIR as INPUT_INVOICES_DIR, DB_PATH, ARCHIVE_DIR, LOG_PATH, PROJECT_ROOT, err_to_cn

app = Flask(__name__)

db_manager = DBManager(DB_PATH)

process_logs = []


def add_log(message, level='info'):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {'timestamp': timestamp, 'message': message, 'level': level}
    process_logs.append(log_entry)
    if len(process_logs) > 100:
        process_logs.pop(0)
    return log_entry


def get_recent_logs(count=50):
    return process_logs[-count:] if len(process_logs) >= count else process_logs


def clear_logs():
    process_logs.clear()
    add_log('日志已清空', 'info')
    return True


def api_error(message, status_code=500):
    cn_msg = err_to_cn(message)
    return jsonify({'status': 'error', 'message': cn_msg}), status_code


@app.errorhandler(500)
def handle_500(error):
    return api_error(str(error), 500)


@app.errorhandler(404)
def handle_404(error):
    return jsonify({'status': 'error', 'message': '请求的资源不存在'}), 404


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response


@app.route('/')
def index():
    return send_from_directory('components', 'index.html')


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    try:
        stats = db_manager.get_stats()
        recent_records = db_manager.get_recent_records(limit=10)
        recent_invoices = []
        for record in recent_records:
            recent_invoices.append({
                'invoice_num': record[0],
                'seller': record[1],
                'item': record[2],
                'total_amount': record[3],
                'date': record[4]
            })

        ensure_directories()
        pending_files = scan_pending_files()
        pending_count = len(pending_files)
        failed_count = db_manager.get_failed_count()
        unsynced_count = db_manager.get_unsynced_count()
        archived_count = stats['total_cnt']
        duplicate_count = db_manager.get_duplicate_stats()['total']

        monthly_trend = []
        now = datetime.now()
        for i in range(5, -1, -1):
            m = now.month - i
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            month_str = f"{y:04d}-{m:02d}"
            conn = db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_amount),0) FROM records WHERE strftime('%Y-%m', date) = ?", (month_str,))
            row = cursor.fetchone()
            conn.close()
            monthly_trend.append({
                'month': month_str,
                'count': row[0],
                'amount': round(row[1], 2)
            })

        return jsonify({
            'status': 'success',
            'data': {
                'stats': {
                    'total_cnt': stats['total_cnt'],
                    'total_amt': stats['total_amt'],
                    'month_cnt': stats['month_cnt'],
                    'month_amt': stats['month_amt']
                },
                'directory_status': {
                    'pending': pending_count,
                    'archived': archived_count,
                    'failed': failed_count,
                    'duplicate': duplicate_count
                },
                'recent_invoices': recent_invoices,
                'monthly_trend': monthly_trend
            }
        })
    except Exception as e:
        return api_error(str(e))


@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    try:
        keyword = request.args.get('keyword')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        seller = request.args.get('seller')
        amt_from = request.args.get('amt_from')
        amt_to = request.args.get('amt_to')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        offset = (page - 1) * limit

        records, total = db_manager.query_records(
            keyword=keyword, date_from=date_from, date_to=date_to,
            seller=seller, amt_from=amt_from, amt_to=amt_to,
            limit=limit, offset=offset
        )

        invoices = []
        for record in records:
            invoices.append({
                'invoice_num': record.get('invoice_num'),
                'seller': record.get('seller'),
                'seller_tax_id': record.get('seller_tax_id'),
                'date': record.get('date'),
                'buyer': record.get('buyer'),
                'total_amount': record.get('total_amount'),
                'remark': record.get('remark')
            })

        return jsonify({
            'status': 'success',
            'data': {
                'invoices': invoices,
                'total': total,
                'page': page,
                'limit': limit,
                'pages': (total + limit - 1) // limit
            }
        })
    except Exception as e:
        return api_error(str(e))


@app.route('/api/export/invoices', methods=['GET'])
def export_invoices():
    try:
        keyword = request.args.get('keyword')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        seller = request.args.get('seller')
        amt_from = request.args.get('amt_from')
        amt_to = request.args.get('amt_to')

        records, total = db_manager.query_records(
            keyword=keyword, date_from=date_from, date_to=date_to,
            seller=seller, amt_from=amt_from, amt_to=amt_to,
            limit=None, offset=0
        )

        return jsonify({'status': 'success', 'data': {'invoices': records, 'total': total}})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/invoices/duplicates', methods=['GET'])
def get_duplicate_invoices():
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        offset = (page - 1) * limit
        records, total = db_manager.get_duplicate_records(limit=limit, offset=offset)
        dup_stats = db_manager.get_duplicate_stats()
        pages = max(1, (total + limit - 1) // limit)
        return jsonify({
            'status': 'success',
            'data': {
                'records': records,
                'total': total,
                'page': page,
                'pages': pages,
                'stats': dup_stats
            }
        })
    except Exception as e:
        return api_error(str(e))


@app.route('/api/invoices/<invoice_num>', methods=['GET'])
def get_invoice_detail(invoice_num):
    try:
        record = db_manager.get_record_by_invoice_num(invoice_num)
        if not record:
            return jsonify({'status': 'error', 'message': '发票不存在'}), 404

        return jsonify({'status': 'success', 'data': record})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/invoices/<invoice_num>/remark', methods=['PUT'])
def update_invoice_remark(invoice_num):
    try:
        data = request.get_json()
        remark = data.get('remark')

        success = db_manager.update_remark(invoice_num, remark)
        if not success:
            return jsonify({'status': 'error', 'message': '更新失败'}), 400

        return jsonify({'status': 'success', 'message': '更新成功'})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/tasks/pending', methods=['GET'])
def get_pending_files():
    try:
        ensure_directories()
        pending_files = scan_pending_files()

        return jsonify({
            'status': 'success',
            'data': {'files': pending_files, 'count': len(pending_files)}
        })
    except Exception as e:
        return api_error(str(e))


@app.route('/api/upload', methods=['POST'])
def upload_files():
    try:
        from config import INPUT_DIR
        from services import ensure_directories

        ensure_directories()
        files = request.files.getlist('files')

        if not files:
            return jsonify({'status': 'error', 'message': '没有选择文件'}), 400

        uploaded = []
        skipped = []
        for f in files:
            if f.filename == '':
                continue
            safe_name = f.filename
            dest = os.path.join(str(INPUT_DIR), safe_name)
            if os.path.exists(dest):
                skipped.append(safe_name)
                continue
            f.save(dest)
            uploaded.append(safe_name)

        return jsonify({
            'status': 'success',
            'data': {'uploaded': uploaded, 'skipped': skipped, 'total': len(uploaded)}
        })
    except Exception as e:
        return api_error(str(e))


@app.route('/api/system/logs', methods=['GET'])
def get_system_logs():
    try:
        count = int(request.args.get('count', 100))
        level = request.args.get('level', '')

        if not os.path.exists(str(LOG_PATH)):
            return jsonify({'status': 'success', 'data': []})

        entries = []
        with open(str(LOG_PATH), 'r', encoding='utf-8') as lf:
            lines = lf.readlines()
            for line in lines[-count:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(' / ')
                ts = ''
                lvl = 'info'
                src = ''
                msg = line
                if len(parts) >= 4:
                    ts = parts[0]
                    lvl = parts[1]
                    src = parts[2]
                    msg = ' / '.join(parts[3:])

                if level and lvl.lower() != level.lower():
                    continue
                entries.append({'timestamp': ts, 'level': lvl.lower(), 'source': src, 'message': msg})

        return jsonify({'status': 'success', 'data': entries})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/tasks/process', methods=['POST'])
def process_invoices():
    try:
        add_log('系统就绪，等待开始处理发票...', 'info')
        add_log('开始处理发票...', 'info')

        stats, batch_id = run_pipeline()

        if stats['success'] > 0:
            add_log(f'成功识别并归档发票：{stats["success"]} 张', 'success')
        if stats['duplicate'] > 0:
            add_log(f'检测到重复发票：{stats["duplicate"]} 张', 'warning')
        if stats['failed'] > 0:
            add_log(f'识别失败发票：{stats["failed"]} 张', 'error')

        add_log('处理流程结束', 'info')

        return jsonify({
            'status': 'success',
            'data': {'stats': stats, 'batch_id': batch_id}
        })
    except Exception as e:
        add_log(f'处理异常：{err_to_cn(str(e))}', 'error')
        return api_error(str(e))


@app.route('/api/system/status', methods=['GET'])
def get_system_status():
    try:
        env_ok = check_environment()
        db_ok = True
        try:
            db_manager.get_stats()
        except Exception:
            db_ok = False
        dir_ok = True
        try:
            ensure_directories()
        except Exception:
            dir_ok = False

        return jsonify({
            'status': 'success',
            'data': {'environment': env_ok, 'database': db_ok, 'directories': dir_ok}
        })
    except Exception as e:
        return api_error(str(e))


@app.route('/api/sellers', methods=['GET'])
def get_sellers():
    try:
        sellers = db_manager.get_distinct_values('seller')
        return jsonify({'status': 'success', 'data': sellers})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        count = int(request.args.get('count', 50))
        logs = get_recent_logs(count)
        return jsonify({'status': 'success', 'data': logs})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/logs/clear', methods=['POST'])
def clear_process_logs():
    try:
        clear_logs()
        return jsonify({'status': 'success', 'message': '日志已清空'})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/logs/add', methods=['POST'])
def add_process_log():
    try:
        data = request.get_json()
        message = data.get('message', '')
        level = data.get('level', 'info')
        add_log(message, level)
        return jsonify({'status': 'success'})
    except Exception as e:
        return api_error(str(e))


@app.route('/api/invoice/original', methods=['POST'])
def view_original_invoice():
    try:
        data = request.get_json()
        file_md5 = data.get('md5', '')
        if not file_md5:
            return jsonify({'status': 'error', 'message': '缺少文件MD5'}), 400

        record = db_manager.get_record_by_md5(file_md5)
        if not record:
            return jsonify({'status': 'error', 'message': '未找到对应文件'}), 404

        try:
            from .config import ARCHIVE_DIR
            from .core.data_utils import calculate_file_md5
        except ImportError:
            from config import ARCHIVE_DIR
            from core.data_utils import calculate_file_md5

        archive_path = None
        for root, dirs, files in os.walk(str(ARCHIVE_DIR)):
            for fname in files:
                fpath = os.path.join(root, fname)
                if calculate_file_md5(fpath) == file_md5:
                    archive_path = fpath
                    break
            if archive_path:
                break

        if not archive_path or not os.path.exists(archive_path):
            return jsonify({'status': 'error', 'message': '归档文件不存在'}), 404

        return jsonify({
            'status': 'success',
            'message': '已找到归档文件',
            'path': archive_path,
            'url': f'/api/invoice/file/{file_md5}'
        })
    except Exception as e:
        return api_error(str(e))


@app.route('/api/invoice/file/<file_md5>', methods=['GET'])
def serve_original_invoice(file_md5):
    try:
        try:
            from .config import ARCHIVE_DIR
            from .core.data_utils import calculate_file_md5
        except ImportError:
            from config import ARCHIVE_DIR
            from core.data_utils import calculate_file_md5

        archive_path = None
        for root, dirs, files in os.walk(str(ARCHIVE_DIR)):
            for fname in files:
                fpath = os.path.join(root, fname)
                if calculate_file_md5(fpath) == file_md5:
                    archive_path = fpath
                    break
            if archive_path:
                break

        if not archive_path or not os.path.exists(archive_path):
            return jsonify({'status': 'error', 'message': '归档文件不存在'}), 404

        return send_file(archive_path, as_attachment=False)
    except Exception as e:
        return api_error(str(e))


@app.route('/api/open-dir', methods=['POST'])
def open_directory():
    try:
        data = request.get_json()
        dir_name = data.get('dir', '')
        if not dir_name:
            return jsonify({'status': 'error', 'message': '缺少目录名称'}), 400

        try:
            from .config import PROJECT_ROOT
        except ImportError:
            from config import PROJECT_ROOT
        target_dir = str(PROJECT_ROOT / dir_name)

        if not os.path.exists(target_dir):
            return jsonify({'status': 'error', 'message': f'目录不存在: {dir_name}'}), 404

        subprocess.Popen(['explorer', target_dir])

        return jsonify({'status': 'success', 'message': f'已打开目录: {dir_name}'})
    except Exception as e:
        return api_error(str(e))


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('components', path)


if __name__ == '__main__':
    print("天颐发票处理系统 API服务器启动中...")
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务器")

    app.run(host='0.0.0.0', port=5000, debug=False)
