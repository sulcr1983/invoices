const API_BASE = '/api';
        let currentPage = 'dashboard';
        let invoiceListPage = 1;
        const PAGE_LIMIT = 10;

        // ====== Toast 通知 ======
        function showToast(message, type) {
            type = type || 'success';
            var container = document.getElementById('toast-container');
            var icons = { 'success': 'fa-check-circle', 'error': 'fa-times-circle', 'info': 'fa-info-circle', 'warning': 'fa-exclamation-triangle' };
            var icon = icons[type] || 'fa-info-circle';
            var toast = document.createElement('div');
            toast.className = 'toast toast-' + type;
            toast.innerHTML = '<i class="fa ' + icon + '"></i>' + message;
            container.appendChild(toast);
            setTimeout(function() { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 3000);
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatMoney(amount) {
            if (amount === null || amount === undefined) return '¥0.00';
            return '¥' + Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        function safeText(val, def) { return (val !== null && val !== undefined && val !== '') ? val : (def || ''); }

        async function apiRequest(endpoint, method, data) {
            try {
                const options = { method: method || 'GET', headers: { 'Content-Type': 'application/json' } };
                if (data) options.body = JSON.stringify(data);
                const response = await fetch(API_BASE + endpoint, options);
                const result = await response.json();
                if (result.status === 'success') {
                    return result.data !== undefined ? result.data : result;
                }
                return null;
            } catch (error) {
                console.error('API错误:', error);
                return null;
            }
        }

        function showModal(title, bodyHtml) {
            document.getElementById('generic-modal-title').textContent = title;
            document.getElementById('generic-modal-body').innerHTML = bodyHtml;
            document.getElementById('generic-modal').classList.add('show');
        }

        function closeGenericModal() {
            document.getElementById('generic-modal').classList.remove('show');
        }

        function showSuccessModal(title, message, stats) {
            document.getElementById('success-title').textContent = title;
            document.getElementById('success-message').textContent = message;
            const statsEl = document.getElementById('success-stats');
            statsEl.innerHTML = '';
            if (stats) {
                const items = [
                    { label: '成功', value: stats.success || 0, color: '#10b981' },
                    { label: '重复', value: stats.duplicate || 0, color: '#f59e0b' },
                    { label: '失败', value: stats.failed || 0, color: '#ef4444' },
                ];
                items.forEach(function(item) {
                    const div = document.createElement('div');
                    div.className = 'rounded-xl p-3';
                    div.style.background = '#f8fafc';
                    div.innerHTML = '<p class="text-2xl font-bold" style="color:' + item.color + '">' + item.value + '</p>' +
                        '<p class="text-xs text-text-muted mt-1">' + item.label + '</p>';
                    statsEl.appendChild(div);
                });
            }
            document.getElementById('success-modal').classList.add('show');
        }

        function closeSuccessModal() {
            document.getElementById('success-modal').classList.remove('show');
        }

        function switchPage(pageId) {
            currentPage = pageId;
            document.querySelectorAll('.page-content').forEach(function(p) { p.classList.remove('active'); });
            const target = document.getElementById('page-' + pageId);
            if (target) {
                target.classList.add('active');
                target.style.animation = 'none';
                setTimeout(function() { target.style.animation = ''; }, 10);
            }
            document.querySelectorAll('.nav-tab').forEach(function(tab) {
                tab.classList.remove('active');
                if (tab.dataset.page === pageId) tab.classList.add('active');
            });
            if (pageId === 'dashboard') { loadDashboard(); }
            else if (pageId === 'invoices') { loadSellers(); loadInvoices(1); loadDupBadge(); }
            else if (pageId === 'stats') { loadStatsSummary(); }
        }

        function toggleLogPanel() {
            var content = document.getElementById('log-panel-content');
            var icon = document.getElementById('log-toggle-icon');
            if (!content) return;
            if (content.style.display === 'none') {
                content.style.display = '';
                if (icon) icon.style.transform = 'rotate(180deg)';
                loadLogs();
            } else {
                content.style.display = 'none';
                if (icon) icon.style.transform = '';
            }
        }

        function renderTrendChart(data) {
            const container = document.getElementById('trend-chart');
            container.innerHTML = '';
            var trend = (data && data.monthly_trend) || [];
            var months = [];
            var values = [];
            var totalCnt = 0;
            for (var i = 0; i < trend.length; i++) {
                var parts = trend[i].month.split('-');
                months.push(parts[0] + '/' + parts[1]);
                values.push(trend[i].count);
                totalCnt += trend[i].count;
            }
            if (values.length === 0) {
                container.innerHTML = '<div class="text-text-muted text-sm text-center py-6">暂无趋势数据</div>';
                document.getElementById('trend-total').textContent = '近6月共 0 笔';
                return;
            }
            const maxVal = Math.max(...values, 1);
            values.forEach(function(val, idx) {
                const pct = Math.max(3, (val / maxVal) * 100);
                const bar = document.createElement('div');
                bar.className = 'bar-item';
                bar.innerHTML = '<div class="bar-value">' + val + '</div><div class="bar" style="height:' + pct + '%"></div><div class="bar-label">' + months[idx] + '</div>';
                container.appendChild(bar);
                setTimeout(function() { bar.querySelector('.bar').style.height = pct + '%'; }, 100 + idx * 100);
            });
            document.getElementById('trend-total').textContent = '近6月共 ' + totalCnt + ' 笔';
        }

        function renderRecentResults(data) {
            const container = document.getElementById('recent-results');
            const invoices = (data && data.recent_invoices) || [];
            if (invoices.length === 0) {
                container.innerHTML = '<div class="text-text-muted text-sm text-center py-6">暂无处理记录</div>';
                return;
            }
            const recent = invoices.slice(0, 3);
            let html = '';
            recent.forEach(function(inv) {
                html += '<div class="result-card flex items-center gap-3 border-b border-border-light last:border-b-0">' +
                    '<div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background:#f5f3ff;"><i class="fa fa-file-text-o" style="color:#6366f1;font-size:14px;"></i></div>' +
                    '<div class="flex-1 min-w-0"><p class="text-sm font-medium text-text-primary truncate">' + escapeHtml(inv.seller) + '</p><p class="text-xs text-text-muted truncate">' + escapeHtml(inv.invoice_num) + ' · ' + escapeHtml(inv.date) + '</p></div>' +
                    '<span class="text-sm font-semibold" style="color:#6366f1">' + formatMoney(inv.total_amount) + '</span></div>';
            });
            container.innerHTML = html;
        }

        async function loadDashboard() {
            var statEls = ['stat-pending', 'stat-archived', 'stat-month-cnt', 'hero-pending-count'];
            statEls.forEach(function(id) { var el = document.getElementById(id); if (el) el.innerHTML = '<span class="skeleton" style="display:inline-block;width:32px;height:18px;"></span>'; });
            const data = await apiRequest('/dashboard');
            if (!data) { statEls.forEach(function(id) { var el = document.getElementById(id); if (el) el.textContent = '-'; }); return; }
            document.getElementById('stat-pending').textContent = data.directory_status.pending || 0;
            document.getElementById('stat-archived').textContent = data.directory_status.archived || 0;
            document.getElementById('stat-month-cnt').textContent = data.stats.month_cnt || 0;
            document.getElementById('hero-pending-count').textContent = data.directory_status.pending || 0;
            loadDashboardAlerts();
            loadDeductionAlertCount();
            renderTrendChart(data);
            renderRecentResults(data);
        }

        async function loadDeductionAlertCount() {
            var result = await apiRequest('/stats/deduction-alert');
            if (!result) return;
            var expired = result.expired_count || 0;
            var expiring = result.expiring_count || 0;
            var total = expired + expiring;
            var el = document.getElementById('stat-deduction-alert');
            if (el) {
                if (total > 0) {
                    el.textContent = total + ' 张';
                    el.style.color = expired > 0 ? '#dc2626' : '#f59e0b';
                } else {
                    el.textContent = '0';
                    el.style.color = '#10b981';
                }
            }
        }

        async function loadDashboardAlerts() {
            try {
                var invResult = await apiRequest('/invoices?limit=1000');
                var verifyPending = 0, certifyPending = 0;
                if (invResult && invResult.invoices) {
                    invResult.invoices.forEach(function(inv) {
                        if (inv.verify_status === 'unverified') verifyPending++;
                        if (inv.certification_status === 'unverified' && inv.invoice_type && inv.invoice_type.indexOf('专') >= 0) certifyPending++;
                    });
                }
                var vpEl = document.getElementById('stat-verify-pending');
                if (vpEl) vpEl.textContent = verifyPending;
                var cpEl = document.getElementById('stat-certify-pending');
                if (cpEl) cpEl.textContent = certifyPending;
            } catch(e) {}

            try {
                var distResult = await apiRequest('/stats/expense-distribution');
                if (distResult) {
                    var raEl = document.getElementById('stat-risk-alert');
                    if (raEl) raEl.textContent = distResult.risk_count || 0;
                }
            } catch(e) {}
        }

        async function loadDeductionAlert() {
            var result = await apiRequest('/stats/deduction-alert');
            if (!result) return;
            var expired = result.expired || [];
            var expiring = result.expiring || [];
            var html = '<div style="max-height:400px;overflow-y:auto;">';
            if (expired.length > 0) {
                html += '<div class="mb-4"><h4 style="color:#dc2626;font-size:13px;font-weight:600;margin-bottom:8px;"><i class="fa fa-times-circle"></i> 已过期（不可抵扣）</h4>';
                expired.forEach(function(inv) {
                    html += '<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #fef2f2;font-size:12px;">';
                    html += '<span class="font-mono">' + escapeHtml(inv.invoice_num) + '</span>';
                    html += '<span>' + escapeHtml(inv.seller || '') + '</span>';
                    html += '<span style="color:#dc2626;">过期' + Math.abs(inv.days_remaining) + '天</span>';
                    html += '</div>';
                });
                html += '</div>';
            }
            if (expiring.length > 0) {
                html += '<div><h4 style="color:#d97706;font-size:13px;font-weight:600;margin-bottom:8px;"><i class="fa fa-exclamation-circle"></i> 即将到期（30天内）</h4>';
                expiring.forEach(function(inv) {
                    html += '<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #fffbeb;font-size:12px;">';
                    html += '<span class="font-mono">' + escapeHtml(inv.invoice_num) + '</span>';
                    html += '<span>' + escapeHtml(inv.seller || '') + '</span>';
                    html += '<span style="color:#d97706;">剩' + inv.days_remaining + '天</span>';
                    html += '</div>';
                });
                html += '</div>';
            }
            if (expired.length === 0 && expiring.length === 0) {
                html += '<div class="text-center py-6"><i class="fa fa-check-circle text-2xl" style="color:#10b981;"></i><p class="text-sm mt-2" style="color:#10b981;">暂无到期预警</p></div>';
            }
            html += '</div>';
            showModal('认证到期预警', html);
        }

        async function loadSellers() {
            const data = await apiRequest('/sellers');
            if (!data) return;
            var sel = document.getElementById('search-seller');
            sel.innerHTML = '<option value="">全部</option>';
            data.forEach(function(s) { var opt = document.createElement('option'); opt.value = s; opt.textContent = s; sel.appendChild(opt); });
        }

        var selectedInvoices = new Set();

        function toggleSelectAll(checkbox) {
            var checkboxes = document.querySelectorAll('.invoice-checkbox');
            selectedInvoices.clear();
            checkboxes.forEach(function(cb) {
                cb.checked = checkbox.checked;
                if (checkbox.checked) {
                    selectedInvoices.add(cb.dataset.invoice);
                }
            });
            updateBatchCertifyButton();
        }

        function updateBatchCertifyButton() {
            var btn = document.getElementById('btn-batch-certify');
            if (!btn) return;
            if (selectedInvoices.size > 0) {
                btn.style.display = '';
                btn.innerHTML = '<i class="fa fa-check-circle-o"></i> 批量标记已认证 (' + selectedInvoices.size + ')';
            } else {
                btn.style.display = 'none';
            }
        }

        function toggleInvoiceSelect(checkbox) {
            if (checkbox.checked) {
                selectedInvoices.add(checkbox.dataset.invoice);
            } else {
                selectedInvoices.delete(checkbox.dataset.invoice);
            }
            updateBatchCertifyButton();
        }

        async function batchCertify() {
            if (selectedInvoices.size === 0) return;
            var nums = Array.from(selectedInvoices);
            var result = await apiRequest('/invoices/batch-certify', 'POST', {invoice_nums: nums});
            if (result) {
                showToast(result.message || '认证成功', 'success');
                selectedInvoices.clear();
                loadInvoices(invoiceListPage);
                updateBatchCertifyButton();
            }
        }

        var verifyStatusConfig = {
            'unverified': {label: '待查验', bg: '#f1f5f9', color: '#94a3b8'},
            'success': {label: '查验通过', bg: '#ecfdf5', color: '#10b981'},
            'failed': {label: '查验失败', bg: '#fef2f2', color: '#ef4444'},
            'voided': {label: '已作废', bg: '#fef2f2', color: '#dc2626'},
            'red': {label: '红冲发票', bg: '#fff7ed', color: '#ea580c'}
        };

        var certStatusConfig = {
            'unverified': {label: '未认证', bg: '#f1f5f9', color: '#94a3b8'},
            'certified': {label: '已认证', bg: '#ecfdf5', color: '#10b981'}
        };

        function renderVerifyBadge(status, invoiceNum) {
            var cfg = verifyStatusConfig[status] || verifyStatusConfig['unverified'];
            var clickable = (status === 'unverified') ? ' style="cursor:pointer;" onclick="handleVerifyFromList(\'' + (invoiceNum || '') + '\')" title="点击验真（¥' + verifyConfig.cost.toFixed(2) + '/次）"' : '';
            return '<span' + clickable + ' style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:' + cfg.bg + ';color:' + cfg.color + ';' + (status === 'unverified' ? 'text-decoration:underline dotted;' : '') + '">' + cfg.label + '</span>';
        }

        function renderCertBadge(status) {
            var cfg = certStatusConfig[status] || certStatusConfig['unverified'];
            return '<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:' + cfg.bg + ';color:' + cfg.color + ';">' + cfg.label + '</span>';
        }

        var riskFlagLabelsMap = {
            'high_amount': '大额预警',
            'split_suspicion': '拆票预警'
        };

        function getRiskLabels(riskFlags) {
            if (!riskFlags) return '';
            return riskFlags.split(',').filter(function(f) { return f.trim(); }).map(function(f) {
                return riskFlagLabelsMap[f.trim()] || f.trim();
            }).join('；');
        }

        function renderRiskBadge(riskFlags) {
            if (!riskFlags) return '';
            var labels = getRiskLabels(riskFlags);
            return '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:#fef2f2;color:#dc2626;"><i class="fa fa-exclamation-triangle" style="font-size:10px;"></i>' + escapeHtml(labels) + '</span>';
        }

        var verifyConfig = {enabled: false, available: false, cost: 0.25};
        var verifyNoRemind = localStorage.getItem('verify_no_remind') === 'true';
        var pendingVerifyInvoiceNum = null;

        async function loadVerifyConfig() {
            var result = await apiRequest('/verify/config');
            if (result) {
                verifyConfig.enabled = result.enabled;
                verifyConfig.available = result.available;
                verifyConfig.cost = result.cost_per_call;
            }
        }

        function showVerifyConfirm(invoiceNum) {
            pendingVerifyInvoiceNum = invoiceNum;
            document.getElementById('verify-confirm-invoice-num').textContent = invoiceNum;
            document.getElementById('verify-confirm-cost').textContent = '¥' + verifyConfig.cost.toFixed(2) + '/次';
            document.getElementById('verify-no-remind').checked = false;
            document.getElementById('verify-confirm-modal').classList.add('show');
        }

        function closeVerifyConfirm() {
            document.getElementById('verify-confirm-modal').classList.remove('show');
            pendingVerifyInvoiceNum = null;
        }

        async function confirmVerify() {
            var noRemind = document.getElementById('verify-no-remind').checked;
            if (noRemind) {
                localStorage.setItem('verify_no_remind', 'true');
                verifyNoRemind = true;
            }
            closeVerifyConfirm();
            if (pendingVerifyInvoiceNum) {
                await doVerifyInvoice(pendingVerifyInvoiceNum);
            }
        }

        async function handleVerifyFromList(invoiceNum) {
            if (!verifyConfig.enabled || !verifyConfig.available) {
                showToast('验真功能未启用或API未配置', 'error');
                return;
            }
            if (verifyNoRemind) {
                await doVerifyInvoice(invoiceNum);
            } else {
                showVerifyConfirm(invoiceNum);
            }
        }

        async function handleVerifyFromDetail() {
            var invoiceNum = document.getElementById('btn-verify-invoice').dataset.invoiceNum;
            if (!invoiceNum) return;
            if (!verifyConfig.enabled || !verifyConfig.available) {
                showToast('验真功能未启用或API未配置', 'error');
                return;
            }
            if (verifyNoRemind) {
                await doVerifyInvoice(invoiceNum);
            } else {
                showVerifyConfirm(invoiceNum);
            }
        }

        async function doVerifyInvoice(invoiceNum) {
            var btn = document.getElementById('btn-verify-invoice');
            var originalText = '';
            if (btn && btn.dataset.invoiceNum === invoiceNum) {
                originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fa fa-spinner fa-spin-custom"></i> 查验中...';
                btn.disabled = true;
            }
            try {
                var result = await apiRequest('/invoices/' + invoiceNum + '/verify', 'POST');
                if (result) {
                    if (result.already_verified) {
                        showToast('该发票已查验过，无需重复查验', 'info');
                    } else {
                        showToast(result.verify_message || '查验完成', result.verify_status === 'success' ? 'success' : 'error');
                    }
                    loadInvoices(invoiceListPage);
                    var detailModal = document.getElementById('invoice-detail-modal');
                    if (detailModal && detailModal.classList.contains('show')) {
                        showInvoiceDetail(invoiceNum);
                    }
                }
            } finally {
                if (btn && btn.dataset.invoiceNum === invoiceNum) {
                    btn.innerHTML = originalText || '<i class="fa fa-search"></i> 立即查验';
                    btn.disabled = false;
                }
            }
        }

        async function loadInvoices(page) {
            invoiceListPage = page;
            var invTbody = document.getElementById('invoices-body');
            invTbody.innerHTML = '<tr><td colspan="9" class="text-center py-6"><i class="fa fa-spinner fa-spin-custom" style="color:#8b5cf6;font-size:20px;"></i><span class="ml-2 text-text-muted text-sm">加载中...</span></td></tr>';
            var keyword = document.getElementById('search-keyword').value;
            var dateFrom = document.getElementById('search-date-from').value;
            var dateTo = document.getElementById('search-date-to').value;
            var seller = document.getElementById('search-seller').value;
            var amtFrom = document.getElementById('search-amt-from').value;
            var amtTo = document.getElementById('search-amt-to').value;
            var invoiceType = document.getElementById('search-invoice-type').value;
            var pushStatus = document.getElementById('search-push-status').value;
            var params = new URLSearchParams();
            if (keyword) params.append('keyword', keyword);
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
            if (seller) params.append('seller', seller);
            if (amtFrom) params.append('amt_from', amtFrom);
            if (amtTo) params.append('amt_to', amtTo);
            if (invoiceType) params.append('invoice_type', invoiceType);
            if (pushStatus) params.append('push_status', pushStatus);
            params.append('page', page);
            params.append('limit', PAGE_LIMIT);
            var data = await apiRequest('/invoices?' + params.toString());
            if (!data) return;
            var tbody = document.getElementById('invoices-body');
            tbody.innerHTML = '';
            if (data.invoices.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" class="text-center py-10 text-text-muted">暂无匹配的发票记录</td></tr>';
            } else {
                data.invoices.forEach(function(inv) {
                    var tr = document.createElement('tr');
                    var deductionTag = '';
                    if (inv.deduction_status === 'expired') {
                        deductionTag = ' <span style="display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600;background:#fef2f2;color:#dc2626;">已过期</span>';
                    } else if (inv.deduction_status === 'expiring') {
                        deductionTag = ' <span style="display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600;background:#fffbeb;color:#d97706;">剩' + inv.days_remaining + '天</span>';
                    }
                    var attributionTags = '';
                    if (inv.department || inv.project || inv.expense_type) {
                        var tags = [];
                        if (inv.department) tags.push('<span style="display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:500;background:var(--color-primary-bg);color:var(--color-primary);margin-right:2px;">' + escapeHtml(inv.department) + '</span>');
                        if (inv.project) tags.push('<span style="display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:500;background:#ecfdf5;color:#059669;margin-right:2px;">' + escapeHtml(inv.project) + '</span>');
                        if (inv.expense_type) tags.push('<span style="display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:500;background:#fffbeb;color:#d97706;">' + escapeHtml(inv.expense_type) + '</span>');
                        attributionTags = tags.join('');
                    }
                    var isChecked = selectedInvoices.has(inv.invoice_num) ? 'checked' : '';
                    tr.innerHTML = '<td><input type="checkbox" class="invoice-checkbox" data-invoice="' + escapeHtml(inv.invoice_num) + '" ' + isChecked + ' onchange="toggleInvoiceSelect(this)" style="accent-color:var(--color-primary);"></td>' +
                        '<td class="font-mono text-xs text-text-muted">' + (inv.risk_flags ? '<span style="cursor:pointer;margin-right:4px;" title="' + escapeHtml(getRiskLabels(inv.risk_flags)) + '"><i class="fa fa-exclamation-triangle" style="color:#ef4444;font-size:12px;"></i></span>' : '') + escapeHtml(inv.invoice_num) + deductionTag + '</td>' +
                        '<td class="font-medium text-text-primary">' + escapeHtml(inv.seller) + '</td>' +
                        '<td class="text-text-muted">' + escapeHtml(inv.date) + '</td>' +
                        '<td class="text-right font-semibold" style="color:#6366f1">' + formatMoney(inv.total_amount) + '</td>' +
                        '<td>' + renderVerifyBadge(inv.verify_status, inv.invoice_num) + '</td>' +
                        '<td>' + renderCertBadge(inv.certification_status) + '</td>' +
                        '<td>' + (attributionTags || '<span class="text-text-muted text-xs">-</span>') + '</td>' +
                        '<td><button data-invoice="' + escapeHtml(inv.invoice_num) + '" class="text-sm hover:underline font-medium btn-detail" style="color:#6366f1">详情</button></td>';
                    tbody.appendChild(tr);
                });
            }
            document.getElementById('pagination-info').textContent = '共 ' + data.total + ' 条记录';
            var hint = document.getElementById('search-total-hint');
            if (hint) hint.textContent = data.total;
            var pd = document.getElementById('pagination-detail');
            if (pd) pd.textContent = '第 ' + data.page + '/' + data.pages + ' 页 · 共 ' + data.total + ' 条';
            var pb = document.getElementById('pagination-buttons');
            pb.innerHTML = '';
            if (data.pages <= 1 && data.total === 0) return;
            var prevBtn = document.createElement('button');
            prevBtn.className = 'page-btn'; prevBtn.textContent = '‹ 上一页';
            prevBtn.disabled = data.page <= 1;
            if (data.page > 1) prevBtn.addEventListener('click', function() { loadInvoices(data.page - 1); });
            pb.appendChild(prevBtn);
            var startPage = Math.max(1, data.page - 2);
            var endPage = Math.min(data.pages, startPage + 4);
            startPage = Math.max(1, endPage - 4);
            for (var i = startPage; i <= endPage; i++) {
                (function(pageNum) {
                    var btn = document.createElement('button');
                    btn.className = 'page-btn' + (i === data.page ? ' active' : '');
                    btn.textContent = i;
                    btn.addEventListener('click', function() { loadInvoices(pageNum); });
                    pb.appendChild(btn);
                })(i);
            }
            var nextBtn = document.createElement('button');
            nextBtn.className = 'page-btn'; nextBtn.textContent = '下一页 ›';
            nextBtn.disabled = data.page >= data.pages;
            if (data.page < data.pages) nextBtn.addEventListener('click', function() { loadInvoices(data.page + 1); });
            pb.appendChild(nextBtn);
        }

        async function showInvoiceDetail(invoiceNum) {
            var data = await apiRequest('/invoices/' + encodeURIComponent(invoiceNum));
            if (!data) return;
            document.getElementById('detail-invoice-num').textContent = safeText(data.invoice_num);
            document.getElementById('detail-invoice-code').textContent = safeText(data.invoice_code);
            document.getElementById('detail-date').textContent = safeText(data.date);
            document.getElementById('detail-invoice-type').textContent = safeText(data.invoice_type);
            document.getElementById('detail-seller').textContent = safeText(data.seller);
            document.getElementById('detail-seller-tax-id').textContent = safeText(data.seller_tax_id);
            document.getElementById('detail-buyer').textContent = safeText(data.buyer);
            document.getElementById('detail-buyer-tax-id').textContent = safeText(data.buyer_tax_id);
            document.getElementById('detail-item').textContent = safeText(data.item);
            document.getElementById('detail-price-without-tax').textContent = formatMoney(data.price_without_tax);
            document.getElementById('detail-tax-rate').textContent = safeText(data.tax_rate);
            document.getElementById('detail-tax-amount').textContent = formatMoney(data.tax_amount);
            document.getElementById('detail-total-amount').textContent = formatMoney(data.total_amount);
            var deptInput = document.getElementById('detail-department');
            var projInput = document.getElementById('detail-project');
            var expInput = document.getElementById('detail-expense-type');
            if (deptInput) deptInput.value = data.department || '';
            if (projInput) projInput.value = data.project || '';
            if (expInput) expInput.value = data.expense_type || '';
            document.getElementById('detail-remark').value = safeText(data.remark);
            document.getElementById('btn-save-remark').dataset.invoiceNum = data.invoice_num;
            var verifyBadge = document.getElementById('detail-verify-badge');
            if (verifyBadge) verifyBadge.innerHTML = renderVerifyBadge(data.verify_status || 'unverified');
            var verifyBtn = document.getElementById('btn-verify-invoice');
            if (verifyBtn) {
                verifyBtn.dataset.invoiceNum = data.invoice_num || '';
                if (data.verify_status && data.verify_status !== 'unverified') {
                    verifyBtn.style.display = 'none';
                } else {
                    verifyBtn.style.display = '';
                    if (!verifyConfig.enabled || !verifyConfig.available) {
                        verifyBtn.disabled = true;
                        verifyBtn.style.opacity = '0.5';
                        verifyBtn.style.cursor = 'not-allowed';
                        verifyBtn.title = '验真接口待配置';
                    } else {
                        verifyBtn.disabled = false;
                        verifyBtn.style.opacity = '1';
                        verifyBtn.style.cursor = 'pointer';
                        verifyBtn.title = '点击验真（¥' + verifyConfig.cost.toFixed(2) + '/次）';
                    }
                }
            }
            var verifyMsg = document.getElementById('detail-verify-message');
            if (verifyMsg) {
                if (data.verify_time) {
                    verifyMsg.textContent = '查验时间: ' + data.verify_time;
                    verifyMsg.style.display = '';
                } else {
                    verifyMsg.style.display = 'none';
                }
            }
            var verifyResultArea = document.getElementById('detail-verify-result-area');
            var verifyResultContent = document.getElementById('detail-verify-result-content');
            if (verifyResultArea && verifyResultContent) {
                if (data.verify_result && data.verify_status && data.verify_status !== 'unverified') {
                    try {
                        var detail = typeof data.verify_result === 'string' ? JSON.parse(data.verify_result) : data.verify_result;
                        var html = '<table class="data-table" style="font-size:11px;"><tbody>';
                        var fields = {
                            'VerifyMessage': '查验结果', 'VerifyFrequency': '查验次数',
                            'InvalidSign': '作废标志', 'InvoiceType': '发票类型',
                            'SellerName': '销售方名称', 'SellerRegisterNum': '销售方税号',
                            'TotalAmount': '合计金额', 'TotalTax': '合计税额',
                            'AmountInFiguers': '价税合计'
                        };
                        for (var key in fields) {
                            if (detail[key] !== undefined && detail[key] !== '') {
                                html += '<tr><td class="text-text-muted" style="white-space:nowrap;">' + fields[key] + '</td><td class="text-text-primary font-medium">' + escapeHtml(String(detail[key])) + '</td></tr>';
                            }
                        }
                        html += '</tbody></table>';
                        verifyResultContent.innerHTML = html;
                        verifyResultArea.style.display = '';
                    } catch (e) {
                        verifyResultArea.style.display = 'none';
                    }
                } else {
                    verifyResultArea.style.display = 'none';
                }
            }
            var certBadge = document.getElementById('detail-certification-badge');
            if (certBadge) certBadge.innerHTML = renderCertBadge(data.deduction_status || 'unverified');
            var riskBadgeArea = document.getElementById('detail-risk-badge-area');
            var riskBadgeEl = document.getElementById('detail-risk-badge');
            if (riskBadgeArea && riskBadgeEl) {
                if (data.risk_flags) {
                    riskBadgeEl.innerHTML = renderRiskBadge(data.risk_flags);
                    riskBadgeArea.style.display = 'flex';
                } else {
                    riskBadgeArea.style.display = 'none';
                }
            }
            var viewBtn = document.getElementById('btn-view-original');
            if (data.file_md5) { viewBtn.dataset.md5 = data.file_md5; viewBtn.style.display = 'inline-flex'; }
            else { viewBtn.style.display = 'none'; }
            document.getElementById('invoice-detail-modal').classList.add('show');
        }

        function closeDetailModal() { document.getElementById('invoice-detail-modal').classList.remove('show'); }

        document.getElementById('invoice-detail-modal').addEventListener('click', function(e) { if (e.target === this) closeDetailModal(); });
            document.getElementById('success-modal').addEventListener('click', function(e) { if (e.target === this) closeSuccessModal(); });
            document.getElementById('confirm-modal').addEventListener('click', function(e) { if (e.target === this) closeConfirmModal(); });

        function closeConfirmModal() {
            document.getElementById('confirm-modal').classList.remove('show');
        }

        async function startProcessing() {
            var confirmModal = document.getElementById('confirm-modal');
            confirmModal.classList.add('show');
        }

        async function doStartProcessing() {
            document.getElementById('confirm-modal').classList.remove('show');

            var heroBtn = document.getElementById('hero-start-process');
            var progressEl = document.getElementById('process-progress');
            heroBtn.disabled = true;
            heroBtn.innerHTML = '<i class="fa fa-spinner fa-spin-custom"></i> <span id="hero-btn-text">处理中...</span>';
            progressEl.classList.remove('hidden');
            var logsContainer = document.getElementById('logs-container');
            logsContainer.innerHTML = '';
            addLogEntry('系统就绪，准备处理发票...', 'info');
            addLogEntry('开始批量处理...', 'info');

            var startData = await apiRequest('/tasks/process', 'POST');
            if (!startData) {
                showSuccessModal('处理失败', '无法启动处理任务', null);
                heroBtn.disabled = false;
                heroBtn.innerHTML = '<i class="fa fa-play-circle"></i> <span id="hero-btn-text">开始处理发票</span>';
                progressEl.classList.add('hidden');
                return;
            }

            var pollInterval = setInterval(async function() {
                await loadLogs();
                var statusData = await apiRequest('/tasks/status');
                if (statusData && !statusData.running) {
                    clearInterval(pollInterval);
                    var stats = statusData.stats || {success: 0, duplicate: 0, failed: 0};
                    var error = statusData.error;
                    if (error) {
                        showSuccessModal('处理失败', '请检查系统日志或文件状态', null);
                    } else {
                        showSuccessModal('处理完成', '所有待识别发票已处理完毕', stats);
                        loadDashboard();
                    }
                    heroBtn.disabled = false;
                    heroBtn.innerHTML = '<i class="fa fa-play-circle"></i> <span id="hero-btn-text">开始处理发票</span>';
                    progressEl.classList.add('hidden');
                }
            }, 1500);
        }

        function addLogEntry(message, level) {
            var container = document.getElementById('logs-container');
            if (!container) return;
            if (container.querySelector('.text-center') && container.innerHTML.indexOf('暂无日志') !== -1) { container.innerHTML = ''; }
            var div = document.createElement('div');
            var icons = { 'info': 'fa-info-circle', 'success': 'fa-check-circle', 'warning': 'fa-exclamation-triangle', 'error': 'fa-times-circle' };
            var colors = { 'info': '#818cf8', 'success': '#34d399', 'warning': '#fbbf24', 'error': '#f87171' };
            var l = level || 'info';
            div.className = 'log-entry log-' + l;
            div.setAttribute('data-level', l);
            var ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
            var icon = icons[l] || 'fa-info-circle';
            var color = colors[l] || '#818cf8';
            div.innerHTML = '<span style="color:rgba(148,163,184,0.4);margin-right:10px;font-size:11px;">' + ts + '</span><span style="color:' + color + ';margin-right:6px;font-size:11px;"><i class="fa ' + icon + '"></i></span><span style="color:rgba(226,232,240,0.85);">' + message + '</span>';
            container.appendChild(div);
            // Apply current filter
            var activeFilter = document.querySelector('.log-filter-btn.active');
            if (activeFilter) {
                var level = activeFilter.dataset.level;
                if (level !== 'all') {
                    div.style.display = (l === level) ? '' : 'none';
                }
            }
            if (document.getElementById('log-auto-scroll') && document.getElementById('log-auto-scroll').checked) {
                container.scrollTop = container.scrollHeight;
            }
            updateLogBadge();
        }

        async function loadLogs() {
            var data = await apiRequest('/logs');
            var container = document.getElementById('logs-container');
            if (!container) return;
            if (!data || data.length === 0) {
                if (!container.querySelector('.log-entry')) {
                    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:rgba(148,163,184,0.4);font-size:13px;"><div class="text-center"><i class="fa fa-terminal" style="font-size:32px;display:block;margin-bottom:10px;opacity:0.25;"></i>暂无日志记录</div></div>';
                }
                updateLogBadge();
                return;
            }
            container.innerHTML = '';
            var activeFilter = document.querySelector('.log-filter-btn.active');
            var filterLevel = activeFilter ? activeFilter.dataset.level : 'all';
            var icons = { 'info': 'fa-info-circle', 'success': 'fa-check-circle', 'warning': 'fa-exclamation-triangle', 'error': 'fa-times-circle' };
            var colors = { 'info': '#818cf8', 'success': '#34d399', 'warning': '#fbbf24', 'error': '#f87171' };
            data.forEach(function(log) {
                var l = log.level || 'info';
                if (filterLevel !== 'all' && l !== filterLevel) return;
                var div = document.createElement('div');
                div.className = 'log-entry log-' + l;
                div.setAttribute('data-level', l);
                var icon = icons[l] || 'fa-info-circle';
                var color = colors[l] || '#818cf8';
                div.innerHTML = '<span style="color:rgba(148,163,184,0.4);margin-right:10px;font-size:11px;">[' + log.timestamp + ']</span><span style="color:' + color + ';margin-right:6px;font-size:11px;"><i class="fa ' + icon + '"></i></span><span style="color:rgba(226,232,240,0.85);">' + log.message + '</span>';
                container.appendChild(div);
            });
            if (document.getElementById('log-auto-scroll') && document.getElementById('log-auto-scroll').checked) {
                container.scrollTop = container.scrollHeight;
            }
            updateLogBadge();
        }

        function updateLogBadge() {
            var container = document.getElementById('logs-container');
            var badge = document.getElementById('log-count-badge');
            if (!container || !badge) return;
            var count = container.querySelectorAll('.log-entry').length;
            badge.textContent = count + ' 条';
        }

        async function clearLogs() {
            await apiRequest('/logs/clear', 'POST');
            var container = document.getElementById('logs-container');
            container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:rgba(148,163,184,0.4);font-size:13px;"><div class="text-center"><i class="fa fa-terminal" style="font-size:32px;display:block;margin-bottom:10px;opacity:0.25;"></i>暂无日志记录</div></div>';
            updateLogBadge();
        }

        function initUploadZone() {
            var zone = document.getElementById('upload-zone');
            var input = document.getElementById('file-input');
            var btnSelect = document.getElementById('btn-select-files');
            var placeholder = document.getElementById('upload-placeholder');
            var filesArea = document.getElementById('upload-files-area');
            var fileList = document.getElementById('file-list');
            var selectedFiles = [];
            btnSelect.addEventListener('click', function(e) { e.stopPropagation(); input.click(); });
            zone.addEventListener('click', function() { input.click(); });
            input.addEventListener('change', function() { handleFiles(this.files); this.value = ''; });
            zone.addEventListener('dragover', function(e) { e.preventDefault(); e.stopPropagation(); zone.classList.add('dragover'); });
            zone.addEventListener('dragleave', function(e) { e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover'); });
            zone.addEventListener('drop', function(e) {
                e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) { handleFiles(e.dataTransfer.files); }
            });
            function handleFiles(files) {
                var formData = new FormData();
                var validExt = ['pdf','ofd','jpg','jpeg','png'];
                var fileCount = 0;
                for (var i = 0; i < files.length; i++) {
                    var f = files[i];
                    var ext = f.name.split('.').pop().toLowerCase();
                    if (validExt.indexOf(ext) === -1) continue;
                    formData.append('files', f);
                    fileCount++;
                }
                if (fileCount === 0) {
                    showToast('请选择 PDF、OFD、JPG 或 PNG 格式的文件', 'warning');
                    return;
                }
                var uploadingEl = document.createElement('div');
                uploadingEl.className = 'text-center py-4';
                uploadingEl.innerHTML = '<i class="fa fa-spinner fa-spin-custom text-2xl block mb-2" style="color:#8b5cf6;"></i><p class="text-text-secondary text-sm">正在上传 ' + fileCount + ' 个文件...</p>';
                placeholder.classList.add('hidden');
                filesArea.classList.remove('hidden');
                fileList.innerHTML = '';
                fileList.appendChild(uploadingEl);

                fetch('/api/upload', { method:'POST', body:formData })
                    .then(function(r) { return r.json(); })
                    .then(function(result) {
                        if (result.status === 'success') {
                            var d = result.data;
                            showToast('成功上传 ' + d.total + ' 个文件', 'success');
                            loadDashboard();
                        } else {
                            showToast((result.message || '上传失败'), 'error');
                        }
                        placeholder.classList.remove('hidden');
                        filesArea.classList.add('hidden');
                    })
                    .catch(function() {
                        showToast('文件上传失败，请检查网络', 'error');
                        placeholder.classList.remove('hidden');
                        filesArea.classList.add('hidden');
                    });
            }
        }

        document.addEventListener('click', function(e) {
            var btn = e.target.closest('.btn-open-dir');
            if (btn && btn.dataset.dir) {
                fetch('/api/open-dir', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({dir: btn.dataset.dir}) }).catch(function(){});
            }
        });

        function switchInvoiceTab(tab) {
            var tabAll = document.getElementById('tab-all-invoices');
            var tabDup = document.getElementById('tab-dup-invoices');
            var panelAll = document.getElementById('invoice-tab-all');
            var panelDup = document.getElementById('invoice-tab-duplicates');
            if (tab === 'duplicates') {
                tabAll.classList.remove('active');
                tabDup.classList.add('active');
                panelAll.style.display = 'none';
                panelDup.style.display = '';
                loadDuplicateRecords();
            } else {
                tabAll.classList.add('active');
                tabDup.classList.remove('active');
                panelAll.style.display = '';
                panelDup.style.display = 'none';
            }
        }

        var dupTypeLabels = {
            'duplicate_md5': '文件重复',
            'duplicate_invoice_num': '号码重复'
        };

        async function loadDupBadge() {
            var result = await apiRequest('/invoices/duplicates?limit=1');
            if (!result) return;
            var stats = result.stats || {};
            var badge = document.getElementById('dup-count-badge');
            var total = stats.total || 0;
            if (total > 0) {
                badge.textContent = total;
                badge.style.display = '';
            } else {
                badge.style.display = 'none';
            }
        }

        async function loadDuplicateRecords() {
            var result = await apiRequest('/invoices/duplicates');
            if (!result) return;
            var records = result.records || [];
            var stats = result.stats || {};
            var hint = document.getElementById('duplicates-hint');
            var recordCount = document.getElementById('duplicates-record-count');
            var badge = document.getElementById('dup-count-badge');
            var tbody = document.getElementById('duplicates-table-body');
            var total = stats.total || 0;
            var unique = stats.unique_invoices || 0;
            if (total > 0) {
                hint.textContent = '共 ' + unique + ' 个发票号码被重复提交';
                recordCount.textContent = '累计 ' + total + ' 条重复记录';
                badge.textContent = total;
                badge.style.display = '';
            } else {
                hint.textContent = '暂无重复发票记录';
                recordCount.textContent = '';
                badge.style.display = 'none';
            }
            if (records.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center py-10"><div class="flex flex-col items-center gap-2"><i class="fa fa-check-circle text-3xl" style="color:#10b981;"></i><p class="text-text-primary font-semibold">暂无重复发票记录</p><p class="text-text-muted text-sm">处理流程中检测到的重复发票将自动记录在此</p></div></td></tr>';
                return;
            }
            var html = '';
            records.forEach(function(rec) {
                var typeLabel = dupTypeLabels[rec.duplicate_type] || rec.duplicate_type || '未知';
                var typeColor = rec.duplicate_type === 'duplicate_md5' ? '#f59e0b' : '#ef4444';
                html += '<tr>';
                html += '<td style="padding:12px 16px;"><span class="font-mono text-xs">' + escapeHtml(rec.invoice_num || '') + '</span></td>';
                html += '<td style="padding:12px 16px;">' + escapeHtml(rec.seller || '-') + '</td>';
                html += '<td style="padding:12px 16px;">' + escapeHtml(rec.date || '-') + '</td>';
                html += '<td style="padding:12px 16px;text-align:right;font-weight:600;color:#6366f1;">¥' + (rec.total_amount || 0) + '</td>';
                html += '<td style="padding:12px 16px;"><span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:' + typeColor + '15;color:' + typeColor + ';">' + typeLabel + '</span></td>';
                html += '<td style="padding:12px 16px;font-size:12px;color:#64748b;" title="' + escapeHtml(rec.file_md5 || '') + '">' + escapeHtml(rec.filename || '-') + '</td>';
                html += '<td style="padding:12px 16px;font-size:12px;color:#94a3b8;">' + escapeHtml(rec.detected_at || '-') + '</td>';
                html += '</tr>';
            });
            tbody.innerHTML = html;
        }

        async function loadStatsSummary() {
            var dateFrom = document.getElementById('search-date-from').value;
            var dateTo = document.getElementById('search-date-to').value;
            var params = [];
            if (dateFrom) params.push('date_from=' + dateFrom);
            if (dateTo) params.push('date_to=' + dateTo);
            var url = '/stats/summary' + (params.length ? '?' + params.join('&') : '');
            var result = await apiRequest(url);
            if (!result) return;
            document.getElementById('stat-total-amt').textContent = formatMoney(result.total_amt);
            document.getElementById('stat-total-price').textContent = formatMoney(result.total_price);
            document.getElementById('stat-total-tax').textContent = formatMoney(result.total_tax);
            document.getElementById('stat-seller-cnt').textContent = result.seller_cnt || 0;
            renderSellerRanking(result.top_sellers || []);
            renderMonthlyAmountChart(result.monthly_summary || []);
            loadInputTaxSummary();
            loadExpenseDistribution();
        }

        async function loadInputTaxSummary() {
            var result = await apiRequest('/stats/input-tax-summary');
            if (!result) return;
            var period = result.period || '';
            var periodEl = document.getElementById('input-tax-period');
            if (periodEl) periodEl.textContent = period;
            var certSummary = result.certified_summary || {cnt: 0, total_tax: 0};
            var unvSummary = result.unverified_summary || {cnt: 0, total_tax: 0};
            var certEl = document.getElementById('input-tax-certified');
            var certCntEl = document.getElementById('input-tax-certified-cnt');
            var unvEl = document.getElementById('input-tax-unverified');
            var unvCntEl = document.getElementById('input-tax-unverified-cnt');
            if (certEl) certEl.textContent = formatMoney(certSummary.total_tax);
            if (certCntEl) certCntEl.textContent = certSummary.cnt + ' 张';
            if (unvEl) unvEl.textContent = formatMoney(unvSummary.total_tax);
            if (unvCntEl) unvCntEl.textContent = unvSummary.cnt + ' 张';
            var tableEl = document.getElementById('input-tax-detail-table');
            if (!tableEl) return;
            var allRates = {};
            (result.certified || []).forEach(function(r) { allRates[r.tax_rate] = allRates[r.tax_rate] || {}; allRates[r.tax_rate].certified = r; });
            (result.unverified || []).forEach(function(r) { allRates[r.tax_rate] = allRates[r.tax_rate] || {}; allRates[r.tax_rate].unverified = r; });
            var rates = Object.keys(allRates).sort();
            if (rates.length === 0) {
                tableEl.innerHTML = '<p class="text-text-muted text-xs text-center py-3">暂无专票数据</p>';
                return;
            }
            var html = '<table class="data-table" style="font-size:12px;"><thead><tr><th>税率</th><th class="text-right">已认证税额</th><th class="text-right">待认证税额</th></tr></thead><tbody>';
            rates.forEach(function(rate) {
                var item = allRates[rate];
                var certTax = (item.certified && item.certified.total_tax) || 0;
                var unvTax = (item.unverified && item.unverified.total_tax) || 0;
                html += '<tr><td>' + escapeHtml(rate) + '</td><td class="text-right" style="color:#10b981;">' + formatMoney(certTax) + '</td><td class="text-right" style="color:#f59e0b;">' + formatMoney(unvTax) + '</td></tr>';
            });
            html += '</tbody></table>';
            tableEl.innerHTML = html;
        }

        function renderSellerRanking(sellers) {
            var container = document.getElementById('seller-ranking');
            if (sellers.length === 0) {
                container.innerHTML = '<p class="text-text-muted text-sm text-center py-4">暂无数据</p>';
                return;
            }
            var maxAmt = Math.max(...sellers.map(function(s) { return s.amt; }), 1);
            var html = '';
            sellers.forEach(function(s, i) {
                var pct = Math.max(5, (s.amt / maxAmt) * 100);
                html += '<div class="flex items-center gap-3 mb-3 last:mb-0">';
                html += '<span class="text-xs font-bold w-5 text-right" style="color:' + (i < 3 ? '#6366f1' : '#94a3b8') + ';">' + (i + 1) + '</span>';
                html += '<div class="flex-1 min-w-0">';
                html += '<div class="flex justify-between items-center mb-1">';
                html += '<span class="text-sm text-text-primary truncate" style="max-width:60%;">' + escapeHtml(s.seller || '未知') + '</span>';
                html += '<span class="text-xs font-semibold" style="color:#6366f1">' + formatMoney(s.amt) + ' <span style="color:#94a3b8;font-weight:400;">(' + s.cnt + '张)</span></span>';
                html += '</div>';
                html += '<div style="height:6px;background:#f1f5f9;border-radius:3px;overflow:hidden;"><div style="height:100%;width:' + pct + '%;background:linear-gradient(90deg,#a78bfa,#8b5cf6);border-radius:3px;transition:width 0.6s ease;"></div></div>';
                html += '</div></div>';
            });
            container.innerHTML = html;
        }

        function renderMonthlyAmountChart(monthly) {
            var container = document.getElementById('monthly-amount-chart');
            if (monthly.length === 0) {
                container.innerHTML = '<p class="text-text-muted text-sm text-center py-4">暂无数据</p>';
                return;
            }
            monthly.reverse();
            var maxAmt = Math.max(...monthly.map(function(m) { return m.amt; }), 1);
            var html = '<div style="display:flex;align-items:flex-end;gap:6px;height:120px;">';
            monthly.forEach(function(m) {
                var pct = Math.max(3, (m.amt / maxAmt) * 100);
                var label = m.month ? m.month.substring(5) : '';
                html += '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;">';
                html += '<div style="font-size:10px;color:#6366f1;font-weight:600;">¥' + (m.amt >= 10000 ? (m.amt / 10000).toFixed(1) + '万' : m.amt.toFixed(0)) + '</div>';
                html += '<div style="width:100%;max-width:28px;height:' + pct + '%;background:linear-gradient(180deg,#a78bfa,#8b5cf6);border-radius:4px 4px 2px 2px;min-height:3px;transition:height 0.6s ease;"></div>';
                html += '<div style="font-size:10px;color:#94a3b8;">' + label + '</div>';
                html += '</div>';
            });
            html += '</div>';
            container.innerHTML = html;
        }

        async function exportCSV() {
            var data = await apiRequest('/export/invoices');
            if (!data || data.invoices.length === 0) { showToast('没有可导出的发票数据', 'warning'); return; }
            var csv = '\uFEFF';
            csv += '发票号码,销售方,销售方税号,开票日期,购买方,购买方税号,项目内容,不含税金额,税率,税额,价税合计,发票代码,校验码,发票类型,备注\n';
            data.invoices.forEach(function(inv) {
                csv += [inv.invoice_num||'', (inv.seller||'').replace(/,/g,'，'), inv.seller_tax_id||'', inv.date||'', (inv.buyer||'').replace(/,/g,'，'), inv.buyer_tax_id||'', (inv.item||'').replace(/,/g,'，'), inv.price_without_tax||0, inv.tax_rate||'', inv.tax_amount||0, inv.total_amount||0, inv.invoice_code||'', inv.check_code||'', (inv.invoice_type||'').replace(/,/g,'，'), (inv.remark||'').replace(/,/g,'，')].join(',') + '\n';
            });
            var blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
            var link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = '发票台账_' + new Date().toISOString().slice(0,10) + '.csv';
            link.click();
            URL.revokeObjectURL(link.href);
            showToast('已导出 ' + data.total + ' 条发票记录', 'success');
        }

        async function saveRemark() {
            var invoiceNum = document.getElementById('btn-save-remark').dataset.invoiceNum;
            var remark = document.getElementById('detail-remark').value;
            if (!invoiceNum) return;
            var result = await apiRequest('/invoices/' + encodeURIComponent(invoiceNum) + '/remark', 'PUT', {remark: remark});
            if (result) { closeDetailModal(); loadInvoices(invoiceListPage); showToast('备注已保存', 'success'); }
        }

        async function saveAttribution() {
            var btn = document.getElementById('btn-save-attribution');
            var invoiceNum = document.getElementById('btn-save-remark').dataset.invoiceNum;
            if (!invoiceNum) return;
            var dept = document.getElementById('detail-department').value;
            var proj = document.getElementById('detail-project').value;
            var exp = document.getElementById('detail-expense-type').value;
            btn.innerHTML = '<i class="fa fa-spinner fa-spin-custom"></i> 保存中...';
            btn.disabled = true;
            try {
                var result = await apiRequest('/invoices/' + invoiceNum + '/attribution', 'PUT', {
                    department: dept, project: proj, expense_type: exp
                });
                if (result) {
                    showToast('费用归属已保存', 'success');
                    loadInvoices(invoiceListPage);
                }
            } finally {
                btn.innerHTML = '<i class="fa fa-save"></i> 保存归属';
                btn.disabled = false;
            }
        }

        async function loadExpenseDistribution() {
            var result = await apiRequest('/stats/expense-distribution');
            if (!result) return;
            renderDeptChart(result.dept_distribution || []);
            renderExpenseTypeChart(result.expense_distribution || []);
            var riskSection = document.getElementById('risk-alert-section');
            var riskCountEl = document.getElementById('risk-alert-count');
            var riskListEl = document.getElementById('risk-alert-list');
            if (result.risk_count > 0 && riskSection && riskCountEl && riskListEl) {
                riskCountEl.textContent = result.risk_count + ' 条预警';
                var html = '';
                (result.risk_invoices || []).forEach(function(inv) {
                    html += '<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--color-border-light);">';
                    html += '<i class="fa fa-exclamation-triangle" style="color:#ef4444;font-size:14px;flex-shrink:0;"></i>';
                    html += '<div style="flex:1;min-width:0;">';
                    html += '<div class="flex items-center gap-2"><span class="font-mono text-xs text-text-muted">' + escapeHtml(inv.invoice_num) + '</span><span class="text-sm text-text-primary">' + escapeHtml(inv.seller) + '</span></div>';
                    html += '<div class="text-xs text-text-muted">' + (inv.risk_labels || []).join('；') + ' · ¥' + formatMoney(inv.total_amount) + '</div>';
                    html += '</div></div>';
                });
                riskListEl.innerHTML = html;
                riskSection.style.display = '';
            } else if (riskSection) {
                riskSection.style.display = 'none';
            }
        }

        function renderDeptChart(data) {
            var container = document.getElementById('dept-distribution-chart');
            if (!container || typeof echarts === 'undefined') return;
            if (!data.length) { container.innerHTML = '<p class="text-text-muted text-xs text-center py-8">暂无数据</p>'; return; }
            var chart = echarts.init(container);
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
                color: ['#6366f1','#8b5cf6','#a78bfa','#c4b5fd','#ddd6fe','#ede9fe','#f5f3ff','#e0e7ff','#c7d2fe','#a5b4fc'],
                series: [{ type: 'pie', radius: ['40%','70%'], center: ['50%','50%'],
                    label: { fontSize: 11, formatter: '{b}\n{d}%' },
                    data: data.map(function(d) { return { name: d.name, value: d.amt }; })
                }]
            });
        }

        function renderExpenseTypeChart(data) {
            var container = document.getElementById('expense-type-chart');
            if (!container || typeof echarts === 'undefined') return;
            if (!data.length) { container.innerHTML = '<p class="text-text-muted text-xs text-center py-8">暂无数据</p>'; return; }
            var chart = echarts.init(container);
            chart.setOption({
                tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                grid: { left: 60, right: 20, top: 10, bottom: 30 },
                xAxis: { type: 'category', data: data.map(function(d) { return d.name; }), axisLabel: { fontSize: 10, rotate: 30 } },
                yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
                series: [{ type: 'bar', data: data.map(function(d) { return d.amt; }),
                    itemStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'#6366f1'},{offset:1,color:'#a78bfa'}]) },
                    barWidth: '50%'
                }]
            });
        }

        // 按钮波纹效果
        document.addEventListener('mousedown', function(e) {
            var btn = e.target.closest('.btn-primary, .btn-ghost, button');
            if (!btn) return;
            var rect = btn.getBoundingClientRect();
            var x = ((e.clientX - rect.left) / rect.width * 100).toFixed(1);
            var y = ((e.clientY - rect.top) / rect.height * 100).toFixed(1);
            btn.style.setProperty('--ripple-x', x + '%');
            btn.style.setProperty('--ripple-y', y + '%');
        });

        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('btn-search').addEventListener('click', function() { loadInvoices(1); });
            document.getElementById('btn-reset').addEventListener('click', function() {
                document.querySelectorAll('#page-invoices input').forEach(function(inp) { inp.value = ''; });
                document.getElementById('search-seller').value = '';
                document.getElementById('search-invoice-type').value = '';
                document.getElementById('search-push-status').value = '';
                loadInvoices(1);
            });
            document.getElementById('btn-export-csv').addEventListener('click', exportCSV);
            document.getElementById('hero-start-process').addEventListener('click', startProcessing);
            document.getElementById('btn-confirm-process').addEventListener('click', doStartProcessing);
            document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
            document.getElementById('btn-save-remark').addEventListener('click', saveRemark);
            document.getElementById('btn-save-attribution').addEventListener('click', saveAttribution);
            document.getElementById('btn-view-original').addEventListener('click', function() {
                var md5 = this.dataset.md5;
                if (!md5) return;
                window.open('/api/invoice/file/' + md5, '_blank');
            });
            document.getElementById('search-keyword').addEventListener('keyup', function(e) { if (e.key === 'Enter') loadInvoices(1); });
            document.getElementById('top-search-input').addEventListener('keyup', function(e) {
                if (e.key === 'Enter' && this.value.trim()) {
                    document.getElementById('search-keyword').value = this.value.trim();
                    switchPage('invoices'); loadInvoices(1);
                }
            });
            document.getElementById('invoices-body').addEventListener('click', function(e) {
                var btn = e.target.closest('.btn-detail');
                if (btn) { showInvoiceDetail(btn.dataset.invoice); }
            });
            initUploadZone();
            loadVerifyConfig();

            // 日志级别过滤
            document.getElementById('log-filter-bar').addEventListener('click', function(e) {
                var btn = e.target.closest('.log-filter-btn');
                if (!btn) return;
                document.querySelectorAll('.log-filter-btn').forEach(function(b) {
                    b.style.background = 'transparent'; b.style.color = 'rgba(255,255,255,0.6)';
                });
                btn.style.background = 'rgba(255,255,255,0.12)';
                btn.style.color = '#fff';
                document.querySelectorAll('.log-filter-btn').forEach(function(b) { b.classList.remove('active'); });
                btn.classList.add('active');
                var level = btn.dataset.level;
                var container = document.getElementById('logs-container');
                container.querySelectorAll('.log-entry').forEach(function(entry) {
                    if (level === 'all' || entry.getAttribute('data-level') === level) {
                        entry.style.display = '';
                    } else {
                        entry.style.display = 'none';
                    }
                });
            });

            // 自动滚动切换 — 切回自动时滚到底
            document.getElementById('log-auto-scroll').addEventListener('change', function() {
                if (this.checked) {
                    var container = document.getElementById('logs-container');
                    container.scrollTop = container.scrollHeight;
                }
            });

            loadDashboard();
        });
