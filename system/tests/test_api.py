#!/usr/bin/env python3
import pytest
import json
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_server import app, db_manager, add_log, clear_logs, process_logs
from system.db_manager import DBManager
from system.extractor import extract_invoice, calculate_file_md5
from system.services.file_service import ensure_directories, scan_pending_files
from system.config import INPUT_INVOICES_DIR, ARCHIVE_DIR, DB_PATH


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def clean_logs():
    clear_logs()
    yield
    clear_logs()


EXISTING_INVOICE_NUM = '26204437'
EXISTING_INVOICE_MD5 = 'bafbe773dcef89bc0ede5042f895974a'


# ================================================================
# 1. 首页 / 静态文件
# ================================================================

class TestStaticFiles:
    """测试静态文件服务"""

    def test_index_page(self, client):
        """正常流程：访问首页应返回200和HTML内容"""
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'invoice' in resp.data.lower() or '\u53d1\u7968'.encode('utf-8') in resp.data

    def test_index_html_exists(self, client):
        """正常流程：直接访问index.html"""
        resp = client.get('/index.html')
        assert resp.status_code == 200

    def test_nonexistent_static_file(self, client):
        """异常处理：访问不存在的静态文件应返回404"""
        resp = client.get('/nonexistent_file_xyz.txt')
        assert resp.status_code == 404


# ================================================================
# 2. GET /api/dashboard
# ================================================================

class TestDashboard:
    """测试仪表盘接口"""

    def test_dashboard_success(self, client):
        """正常流程：获取仪表盘数据应返回成功"""
        resp = client.get('/api/dashboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert 'stats' in data['data']
        assert 'directory_status' in data['data']
        assert 'recent_invoices' in data['data']

    def test_dashboard_stats_fields(self, client):
        """正常流程：stats应包含total_cnt/total_amt/month_cnt/month_amt"""
        resp = client.get('/api/dashboard')
        data = resp.get_json()['data']['stats']
        assert 'total_cnt' in data
        assert 'total_amt' in data
        assert 'month_cnt' in data
        assert 'month_amt' in data

    def test_dashboard_directory_status_fields(self, client):
        """正常流程：directory_status应包含pending/archived/failed/duplicate"""
        resp = client.get('/api/dashboard')
        data = resp.get_json()['data']['directory_status']
        assert 'pending' in data
        assert 'archived' in data
        assert 'failed' in data
        assert 'duplicate' in data

    def test_dashboard_recent_invoices_is_list(self, client):
        """正常流程：recent_invoices应为列表"""
        resp = client.get('/api/dashboard')
        data = resp.get_json()['data']['recent_invoices']
        assert isinstance(data, list)

    def test_dashboard_total_cnt_positive(self, client):
        """正常流程：数据库有数据时total_cnt应大于0"""
        resp = client.get('/api/dashboard')
        data = resp.get_json()['data']['stats']['total_cnt']
        assert data > 0


# ================================================================
# 3. GET /api/invoices
# ================================================================

class TestInvoices:
    """测试发票列表接口"""

    def test_invoices_default(self, client):
        """正常流程：默认分页查询"""
        resp = client.get('/api/invoices')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert 'invoices' in data['data']
        assert 'total' in data['data']
        assert 'page' in data['data']
        assert 'pages' in data['data']

    def test_invoices_page_param(self, client):
        """正常流程：指定页码查询"""
        resp = client.get('/api/invoices?page=1&limit=5')
        data = resp.get_json()['data']
        assert data['page'] == 1
        assert data['limit'] == 5

    def test_invoices_keyword_search(self, client):
        """正常流程：关键字搜索"""
        resp = client.get('/api/invoices?keyword=地铁')
        data = resp.get_json()['data']
        assert isinstance(data['invoices'], list)

    def test_invoices_date_range(self, client):
        """正常流程：日期范围筛选"""
        resp = client.get('/api/invoices?date_from=2024-01-01&date_to=2025-12-31')
        data = resp.get_json()['data']
        assert isinstance(data['invoices'], list)

    def test_invoices_seller_filter(self, client):
        """正常流程：销售方筛选"""
        resp = client.get('/api/invoices?seller=广州地铁')
        data = resp.get_json()['data']
        assert isinstance(data['invoices'], list)

    def test_invoices_amount_range(self, client):
        """正常流程：金额范围筛选"""
        resp = client.get('/api/invoices?amt_from=10&amt_to=1000')
        data = resp.get_json()['data']
        assert isinstance(data['invoices'], list)

    def test_invoices_no_results(self, client):
        """边界条件：搜索不存在的关键字应返回空列表"""
        resp = client.get('/api/invoices?keyword=不存在的公司xyz999')
        data = resp.get_json()['data']
        assert data['invoices'] == []
        assert data['total'] == 0

    def test_invoices_invalid_page(self, client):
        """边界条件：超出范围的页码应返回空列表"""
        resp = client.get('/api/invoices?page=9999')
        data = resp.get_json()['data']
        assert data['invoices'] == []

    def test_invoices_record_fields(self, client):
        """正常流程：每条记录应包含必要字段"""
        resp = client.get('/api/invoices?limit=1')
        data = resp.get_json()['data']
        if data['invoices']:
            inv = data['invoices'][0]
            assert 'invoice_num' in inv
            assert 'seller' in inv
            assert 'date' in inv
            assert 'buyer' in inv
            assert 'total_amount' in inv


# ================================================================
# 4. GET /api/export/invoices
# ================================================================

class TestExportInvoices:
    """测试发票导出接口"""

    def test_export_all(self, client):
        """正常流程：导出全部发票"""
        resp = client.get('/api/export/invoices')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert 'invoices' in data['data']
        assert data['data']['total'] > 0

    def test_export_with_filter(self, client):
        """正常流程：带筛选条件导出"""
        resp = client.get('/api/export/invoices?keyword=地铁')
        data = resp.get_json()['data']
        assert isinstance(data['invoices'], list)

    def test_export_records_have_all_fields(self, client):
        """正常流程：导出记录应包含完整字段（非列表页的7个字段）"""
        resp = client.get('/api/export/invoices')
        data = resp.get_json()['data']
        if data['invoices']:
            inv = data['invoices'][0]
            assert 'invoice_num' in inv
            assert 'buyer_tax_id' in inv
            assert 'item' in inv
            assert 'price_without_tax' in inv
            assert 'tax_rate' in inv
            assert 'tax_amount' in inv
            assert 'invoice_code' in inv
            assert 'check_code' in inv
            assert 'invoice_type' in inv

    def test_export_no_results(self, client):
        """边界条件：无匹配结果时导出"""
        resp = client.get('/api/export/invoices?keyword=不存在的xyz')
        data = resp.get_json()['data']
        assert data['invoices'] == []
        assert data['total'] == 0


# ================================================================
# 5. GET /api/invoices/<invoice_num>
# ================================================================

class TestInvoiceDetail:
    """测试发票详情接口"""

    def test_detail_existing(self, client):
        """正常流程：查询存在的发票"""
        resp = client.get(f'/api/invoices/{EXISTING_INVOICE_NUM}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert data['data']['invoice_num'] == EXISTING_INVOICE_NUM

    def test_detail_all_fields(self, client):
        """正常流程：详情应包含所有字段"""
        resp = client.get(f'/api/invoices/{EXISTING_INVOICE_NUM}')
        data = resp.get_json()['data']
        expected_fields = [
            'invoice_num', 'seller', 'seller_tax_id', 'date', 'buyer',
            'buyer_tax_id', 'item', 'price_without_tax', 'tax_rate',
            'tax_amount', 'total_amount', 'invoice_code', 'check_code',
            'invoice_type', 'remark', 'file_md5'
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_detail_not_found(self, client):
        """异常处理：查询不存在的发票应返回404"""
        resp = client.get('/api/invoices/00000000')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data['status'] == 'error'

    def test_detail_empty_invoice_num(self, client):
        """边界条件：空发票号码"""
        resp = client.get('/api/invoices/')
        assert resp.status_code in [404, 308]


# ================================================================
# 6. PUT /api/invoices/<invoice_num>/remark
# ================================================================

class TestUpdateRemark:
    """测试更新备注接口"""

    def test_update_remark_success(self, client):
        """正常流程：更新备注"""
        resp = client.put(
            f'/api/invoices/{EXISTING_INVOICE_NUM}/remark',
            data=json.dumps({'remark': '测试备注'}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'

        resp2 = client.get(f'/api/invoices/{EXISTING_INVOICE_NUM}')
        assert resp2.get_json()['data']['remark'] == '测试备注'

        client.put(
            f'/api/invoices/{EXISTING_INVOICE_NUM}/remark',
            data=json.dumps({'remark': ''}),
            content_type='application/json'
        )

    def test_update_remark_empty(self, client):
        """边界条件：清空备注"""
        resp = client.put(
            f'/api/invoices/{EXISTING_INVOICE_NUM}/remark',
            data=json.dumps({'remark': ''}),
            content_type='application/json'
        )
        assert resp.status_code == 200

    def test_update_remark_long_text(self, client):
        """边界条件：超长备注"""
        long_remark = 'A' * 500
        resp = client.put(
            f'/api/invoices/{EXISTING_INVOICE_NUM}/remark',
            data=json.dumps({'remark': long_remark}),
            content_type='application/json'
        )
        assert resp.status_code == 200

        client.put(
            f'/api/invoices/{EXISTING_INVOICE_NUM}/remark',
            data=json.dumps({'remark': ''}),
            content_type='application/json'
        )

    def test_update_remark_nonexistent_invoice(self, client):
        """异常处理：更新不存在发票的备注"""
        resp = client.put(
            '/api/invoices/99999999/remark',
            data=json.dumps({'remark': 'test'}),
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_update_remark_no_body(self, client):
        """异常处理：请求体为空"""
        resp = client.put(
            f'/api/invoices/{EXISTING_INVOICE_NUM}/remark',
            content_type='application/json'
        )
        assert resp.status_code in [200, 400, 500]


# ================================================================
# 7. GET /api/tasks/pending
# ================================================================

class TestPendingFiles:
    """测试待处理文件接口"""

    def test_pending_files_success(self, client):
        """正常流程：获取待处理文件列表"""
        resp = client.get('/api/tasks/pending')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert 'files' in data['data']
        assert 'count' in data['data']

    def test_pending_files_count_matches(self, client):
        """正常流程：count应等于files列表长度"""
        resp = client.get('/api/tasks/pending')
        data = resp.get_json()['data']
        assert data['count'] == len(data['files'])


# ================================================================
# 8. POST /api/tasks/process
# ================================================================

class TestProcessInvoices:
    """测试发票处理接口"""

    def test_process_empty_dir(self, client):
        """正常流程：处理发票应返回stats和batch_id"""
        resp = client.post('/api/tasks/process')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert 'stats' in data['data']
        assert 'success' in data['data']['stats']
        assert 'duplicate' in data['data']['stats']
        assert 'failed' in data['data']['stats']

    def test_process_returns_batch_id(self, client):
        """正常流程：处理应返回batch_id"""
        resp = client.post('/api/tasks/process')
        data = resp.get_json()['data']
        assert 'batch_id' in data
        assert len(data['batch_id']) > 0


# ================================================================
# 9. GET /api/system/status
# ================================================================

class TestSystemStatus:
    """测试系统状态接口"""

    def test_system_status_success(self, client):
        """正常流程：获取系统状态"""
        resp = client.get('/api/system/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert 'environment' in data['data']
        assert 'database' in data['data']
        assert 'directories' in data['data']

    def test_database_status_ok(self, client):
        """正常流程：数据库状态应为True"""
        resp = client.get('/api/system/status')
        data = resp.get_json()['data']
        assert data['database'] is True

    def test_directories_status_ok(self, client):
        """正常流程：目录状态应为True"""
        resp = client.get('/api/system/status')
        data = resp.get_json()['data']
        assert data['directories'] is True


# ================================================================
# 10. GET /api/sellers
# ================================================================

class TestSellers:
    """测试销售方列表接口"""

    def test_sellers_success(self, client):
        """正常流程：获取销售方列表"""
        resp = client.get('/api/sellers')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert isinstance(data['data'], list)

    def test_sellers_not_empty(self, client):
        """正常流程：数据库有数据时销售方列表不为空"""
        resp = client.get('/api/sellers')
        data = resp.get_json()['data']
        assert len(data) > 0


# ================================================================
# 11. GET /api/logs
# ================================================================

class TestLogs:
    """测试日志接口"""

    def test_get_logs_default(self, client, clean_logs):
        """正常流程：获取日志（默认50条）"""
        add_log('test message', 'info')
        resp = client.get('/api/logs')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert isinstance(data['data'], list)
        assert len(data['data']) >= 1

    def test_get_logs_with_count(self, client, clean_logs):
        """正常流程：指定获取日志条数"""
        for i in range(5):
            add_log(f'msg {i}', 'info')
        resp = client.get('/api/logs?count=3')
        data = resp.get_json()['data']
        assert len(data) == 3

    def test_logs_have_required_fields(self, client, clean_logs):
        """正常流程：日志条目应包含timestamp/message/level"""
        add_log('test', 'info')
        resp = client.get('/api/logs')
        data = resp.get_json()['data']
        if data:
            entry = data[-1]
            assert 'timestamp' in entry
            assert 'message' in entry
            assert 'level' in entry

    def test_logs_levels(self, client, clean_logs):
        """正常流程：不同级别的日志"""
        add_log('info msg', 'info')
        add_log('success msg', 'success')
        add_log('warning msg', 'warning')
        add_log('error msg', 'error')
        resp = client.get('/api/logs')
        data = resp.get_json()['data']
        levels = [e['level'] for e in data[-4:]]
        assert 'info' in levels
        assert 'success' in levels
        assert 'warning' in levels
        assert 'error' in levels


# ================================================================
# 12. POST /api/logs/clear
# ================================================================

class TestClearLogs:
    """测试清空日志接口"""

    def test_clear_logs_success(self, client, clean_logs):
        """正常流程：清空日志"""
        add_log('before clear', 'info')
        resp = client.post('/api/logs/clear')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'

    def test_clear_logs_result(self, client, clean_logs):
        """正常流程：清空后日志列表应只有'日志已清空'一条"""
        add_log('before clear', 'info')
        client.post('/api/logs/clear')
        resp = client.get('/api/logs')
        data = resp.get_json()['data']
        assert len(data) == 1
        assert data[0]['message'] == '日志已清空'


# ================================================================
# 13. POST /api/logs/add
# ================================================================

class TestAddLog:
    """测试添加日志接口"""

    def test_add_log_success(self, client, clean_logs):
        """正常流程：添加日志"""
        resp = client.post(
            '/api/logs/add',
            data=json.dumps({'message': 'api test log', 'level': 'info'}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'

    def test_add_log_default_level(self, client, clean_logs):
        """边界条件：不指定level默认为info"""
        resp = client.post(
            '/api/logs/add',
            data=json.dumps({'message': 'no level'}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        resp2 = client.get('/api/logs')
        data = resp2.get_json()['data']
        last = data[-1]
        assert last['level'] == 'info'

    def test_add_log_empty_message(self, client, clean_logs):
        """边界条件：空消息"""
        resp = client.post(
            '/api/logs/add',
            data=json.dumps({'message': '', 'level': 'info'}),
            content_type='application/json'
        )
        assert resp.status_code == 200


# ================================================================
# 14. POST /api/invoice/original
# ================================================================

class TestViewOriginal:
    """测试查看发票原件接口"""

    def test_view_original_no_md5(self, client):
        """异常处理：不传MD5应返回400"""
        resp = client.post(
            '/api/invoice/original',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_view_original_invalid_md5(self, client):
        """异常处理：无效MD5应返回404"""
        resp = client.post(
            '/api/invoice/original',
            data=json.dumps({'md5': 'invalid_md5_value_12345'}),
            content_type='application/json'
        )
        assert resp.status_code == 404

    def test_view_original_valid_md5(self, client):
        """正常流程：有效MD5应返回成功"""
        resp = client.post(
            '/api/invoice/original',
            data=json.dumps({'md5': EXISTING_INVOICE_MD5}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert 'path' in data


# ================================================================
# 15. POST /api/open-dir
# ================================================================

class TestOpenDir:
    """测试打开目录接口"""

    def test_open_dir_no_dir(self, client):
        """异常处理：不传目录名应返回400"""
        resp = client.post(
            '/api/open-dir',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_open_dir_nonexistent(self, client):
        """异常处理：打开不存在的目录应返回404"""
        resp = client.post(
            '/api/open-dir',
            data=json.dumps({'dir': '不存在的目录xyz'}),
            content_type='application/json'
        )
        assert resp.status_code == 404

    def test_open_dir_existing(self, client):
        """正常流程：打开存在的目录"""
        resp = client.post(
            '/api/open-dir',
            data=json.dumps({'dir': '1-待识别发票'}),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'


# ================================================================
# 16. 核心模块单元测试
# ================================================================

class TestCoreModules:
    """测试核心业务模块"""

    def test_extract_invoice_pdf(self):
        """正常流程：PDF发票识别"""
        archive_dir = ARCHIVE_DIR
        pdf_files = []
        for fp in Path(archive_dir).rglob('*.pdf'):
            pdf_files.append(str(fp))
            if len(pdf_files) >= 1:
                break

        if not pdf_files:
            pytest.skip('No archived PDF files found')

        result, details = extract_invoice(pdf_files[0])
        assert isinstance(result, dict)
        assert 'invoice_num' in result
        assert 'seller' in result
        assert 'total_amount' in result
        assert result['invoice_num'] != ''

    def test_calculate_md5(self):
        """正常流程：计算文件MD5"""
        archive_dir = ARCHIVE_DIR
        pdf_files = []
        for fp in Path(archive_dir).rglob('*.pdf'):
            pdf_files.append(str(fp))
            break

        if not pdf_files:
            pytest.skip('No archived PDF files found')

        md5 = calculate_file_md5(pdf_files[0])
        assert isinstance(md5, str)
        assert len(md5) == 32

    def test_calculate_md5_nonexistent(self):
        """异常处理：计算不存在文件的MD5应返回None或空字符串"""
        result = calculate_file_md5('/nonexistent/file.pdf')
        assert result is None or result == ''

    def test_ensure_directories(self):
        """正常流程：确保目录存在"""
        result = ensure_directories()
        assert result is True or result is None
        assert Path(INPUT_INVOICES_DIR).exists()

    def test_scan_pending_files(self):
        """正常流程：扫描待处理文件"""
        files = scan_pending_files()
        assert isinstance(files, list)

    def test_db_manager_get_stats(self):
        """正常流程：数据库统计"""
        stats = db_manager.get_stats()
        assert 'total_cnt' in stats
        assert 'total_amt' in stats
        assert stats['total_cnt'] > 0

    def test_db_manager_query_records(self):
        """正常流程：查询发票记录"""
        records, total = db_manager.query_records(limit=5, offset=0)
        assert isinstance(records, list)
        assert total > 0
        if records:
            assert 'invoice_num' in records[0]

    def test_db_manager_get_record_by_invoice_num(self):
        """正常流程：按发票号查询"""
        record = db_manager.get_record_by_invoice_num(EXISTING_INVOICE_NUM)
        assert record is not None
        assert record['invoice_num'] == EXISTING_INVOICE_NUM

    def test_db_manager_get_record_by_invoice_num_not_found(self):
        """异常处理：查询不存在的发票号"""
        record = db_manager.get_record_by_invoice_num('00000000')
        assert record is None

    def test_db_manager_get_distinct_values(self):
        """正常流程：获取去重值列表"""
        sellers = db_manager.get_distinct_values('seller')
        assert isinstance(sellers, list)
        assert len(sellers) > 0

    def test_db_manager_get_recent_records(self):
        """正常流程：获取最近记录"""
        records = db_manager.get_recent_records(limit=5)
        assert isinstance(records, list)
        assert len(records) > 0


# ================================================================
# 17. CORS 和 OPTIONS
# ================================================================

class TestCORS:
    """测试跨域支持"""

    def test_cors_headers(self, client):
        """正常流程：响应应包含CORS头"""
        resp = client.get('/api/dashboard')
        assert resp.headers.get('Access-Control-Allow-Origin') == '*'

    def test_options_request(self, client):
        """正常流程：OPTIONS预检请求"""
        resp = client.options('/api/invoices')
        assert resp.status_code in [200, 204]


# ================================================================
# 18. 日志内存管理
# ================================================================

class TestLogMemory:
    """测试日志内存管理"""

    def test_log_max_100(self, clean_logs):
        """边界条件：日志最多保留100条"""
        for i in range(120):
            add_log(f'msg {i}', 'info')
        assert len(process_logs) <= 100

    def test_log_fifo(self, clean_logs):
        """正常流程：日志先进先出"""
        add_log('first', 'info')
        add_log('second', 'info')
        add_log('third', 'info')
        assert process_logs[-3]['message'] == 'first'
        assert process_logs[-2]['message'] == 'second'
        assert process_logs[-1]['message'] == 'third'
