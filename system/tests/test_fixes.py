# -*- coding: utf-8 -*-
"""本轮修复的回归用例（2026-11-12）

安全约束：本模块只在设置了 INVOICE_DB_PATH 的隔离环境运行；
未设置时整组跳过，避免误写真实台账。
"""

import io
import json
import os
import sqlite3

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get('INVOICE_DB_PATH'),
    reason='需要隔离环境：请设置 INVOICE_DB_PATH / INVOICE_PROJECT_ROOT 后再跑',
)


@pytest.fixture()
def client():
    from system.api_server import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# ---------- 上传安全 ----------

def test_upload_rejects_path_traversal(client):
    """文件名带 ../ 时只保留 basename，且不会写到上层目录"""
    data = {'files': (io.BytesIO(b'%PDF-1.4 test'), '../../../evil.pdf')}
    resp = client.post('/api/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    body = resp.get_json()['data']
    # 要么被接受为 evil.pdf（路径已剥离），要么被拒；两种都不允许出现 ../ 落地
    names = body['uploaded'] + body['skipped'] + body['rejected']
    assert all('..' not in n and '/' not in n and '\\' not in n for n in names)


def test_upload_rejects_disallowed_extension(client):
    """非发票后缀必须被拒绝"""
    data = {'files': (io.BytesIO(b'echo hi'), 'run.bat')}
    resp = client.post('/api/upload', data=data, content_type='multipart/form-data')
    body = resp.get_json()['data']
    assert 'run.bat' in body['rejected']
    assert body['uploaded'] == []


# ---------- 参数校验 ----------

@pytest.mark.parametrize('query', ['limit=0', 'limit=999', 'page=abc', 'page=0'])
def test_pagination_invalid_returns_400(client, query):
    resp = client.get('/api/invoices?' + query)
    assert resp.status_code == 400
    assert resp.get_json()['status'] == 'error'


# ---------- 推送状态 ----------

def test_push_skipped_not_success_when_no_webhook():
    """没有 webhook 时推送状态应为 skipped；并可通过唯一索引挡住重复号"""
    from system.db_manager import DBManager
    from system.config import DB_PATH
    db = DBManager(DB_PATH)
    # 若无 webhook，调用推送应标记 skipped
    webhooks = db.get_all_webhooks(only_enabled=True)
    if webhooks:
        pytest.skip('当前环境配置了 webhook，跳过')

    rec = db.get_record_by_invoice_num('INV20240004') or db.query_records(limit=1, offset=0)[0][0]
    num = rec.get('invoice_num') if isinstance(rec, dict) else rec['invoice_num']
    from system.webhook_manager import push_to_all_webhooks
    push_to_all_webhooks({'invoice_num': num}, db)
    status, _ = db.get_push_status(num)
    assert status == 'skipped'


# ---------- 唯一索引 ----------

def test_invoice_num_unique_index_exists():
    from system.config import DB_PATH
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='records' "
        "AND name='idx_records_invoice_num'"
    ).fetchall()
    conn.close()
    assert rows, '缺少发票号索引'
    assert 'UNIQUE' in (rows[0][0] or '').upper()


def test_duplicate_invoice_num_rejected():
    from system.db_manager import DBManager
    from system.config import DB_PATH
    db = DBManager(DB_PATH)
    existing = db.query_records(limit=1, offset=0)[0][0]
    record = dict(existing)
    record['file_md5'] = 'test_fixes_' + os.urandom(6).hex()
    ok, reason, _ = db.insert_record_with_transaction(record)
    assert ok is False
    assert reason == 'duplicate_invoice_num'


# ---------- CSV 原子写 ----------

def test_export_csv_no_tmp_leftover(tmp_path):
    from system.db_manager import DBManager
    from system.config import DB_PATH
    target = tmp_path / 'ledger.csv'
    DBManager(DB_PATH).export_to_csv(target)
    assert target.exists()
    assert target.stat().st_size > 0
    assert not (tmp_path / 'ledger.csv.tmp').exists()


# ---------- 日志增量 ----------

def test_logs_have_seq_and_incremental(client):
    from system.routes.shared import add_log
    add_log('回归测试日志 A', 'info')
    resp = client.get('/api/logs?count=50')
    data = resp.get_json()['data']
    assert data and all('seq' in e for e in data)
    last_seq = max(e['seq'] for e in data)

    add_log('回归测试日志 B', 'info')
    resp2 = client.get('/api/logs?since=%d' % last_seq)
    new = resp2.get_json()['data']
    assert len(new) == 1
    assert new[0]['message'] == '回归测试日志 B'


# ---------- 模糊去重 ----------

def test_fuzzy_dedup_flags_similar(monkeypatch):
    """同金额、同日期、发票号仅末位不同 → 判定疑似重复"""
    from system.core import dedup
    if not dedup.is_available():
        pytest.skip('未安装 rapidfuzz')

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def cursor(self):
            class C:
                description = []

                def execute(self, *a, **k):
                    pass

                def fetchall(self):
                    return [('25442000000391842252', '广州市杰鑫物流有限公司', '*运输服务*', 786.0, '2025-07-01')]
            return C()

    class FakeDB:
        def connection(self):
            return FakeConn()

    record = {
        'invoice_num': '25442000000391842253',
        'seller': '广州市杰鑫物流有限公司',
        'item': '*运输服务*国内道路货物运输服务',
        'total_amount': 786.0,
        'date': '2025-07-01',
    }
    hit = dedup.find_near_duplicate(record, FakeDB())
    assert hit is not None
    assert hit['invoice_num'] == '25442000000391842252'


# ---------- 归档重名 ----------

def test_archive_name_avoids_collision(tmp_path, monkeypatch):
    from system.services import file_service
    monkeypatch.setattr(file_service, 'ARCHIVE_DIR', str(tmp_path))
    p1 = file_service.get_archive_path('测试公司', 'NUM001', 100.0, '.pdf', invoice_date='2026-01-02')
    open(p1, 'wb').write(b'x')
    p2 = file_service.get_archive_path('测试公司', 'NUM001', 100.0, '.pdf', invoice_date='2026-01-02')
    assert p1 != p2
    assert p2.endswith('_1.pdf')


# ---------- 验真参数 ----------

def test_verify_uses_total_amount_and_skips_unknown_type(monkeypatch):
    from system.core import verify

    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {'words_result': {'VerifyResult': '0001', 'VerifyMessage': 'ok'}}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured.update(data or {})
        return FakeResp()

    monkeypatch.setattr(verify, 'get_baidu_access_token', lambda: 'token')
    monkeypatch.setattr(verify.requests, 'post', fake_post)

    verify.verify_invoice_baidu({
        'invoice_num': '25442000000391842252',
        'invoice_code': '044002100611',
        'date': '2025-07-01',
        'check_code': '123456',
        'price_without_tax': 721.10,
        'total_amount': 786.00,
        'invoice_type': '',
    })
    assert captured.get('total_amount') == '786.0'
    # 20 位号码按数电票推断为 '8'；无论是否传，都不能再是历史错误的 '0'（专票）
    assert captured.get('invoice_type') in (None, '', '8')
