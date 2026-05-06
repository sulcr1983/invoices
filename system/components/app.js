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

        function showSuccessModal(title, message, stats, failedFiles) {
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
            var failuresEl = document.getElementById('success-failures');
            if (failuresEl) {
                failuresEl.innerHTML = '';
                if (failedFiles && failedFiles.length > 0) {
                    var fhtml = '<div style="margin-top:12px;padding-top:12px;border-top:1px solid #f1f5f9;text-align:left;">' +
                        '<p style="font-size:12px;font-weight:600;color:#ef4444;margin-bottom:8px;"><i class="fa fa-exclamation-triangle"></i> 失败详情</p>';
                    failedFiles.forEach(function(f) {
                        var reason = f.reason_cn || f.reason || '未知错误';
                        fhtml += '<div style="padding:8px 10px;background:#fef2f2;border-radius:6px;margin-bottom:6px;">' +
                            '<p style="font-size:11px;font-weight:500;color:#dc2626;">' + escapeHtml(f.filename) + '</p>' +
                            '<p style="font-size:10px;color:#ef4444;margin-top:2px;">' + escapeHtml(reason) + '</p></div>';
                    });
                    fhtml += '</div>';
                    failuresEl.innerHTML = fhtml;
                }
            }
            document.getElementById('success-modal').classList.add('show');
        }

        function closeSuccessModal() {
            document.getElementById('success-modal').classList.remove('show');
            if (window._pendingFailedProcessing) {
                window._pendingFailedProcessing = false;
                // Auto-expand log panel when processing had failures
                var logContent = document.getElementById('log-panel-content');
                if (logContent && logContent.style.display === 'none') {
                    toggleLogPanel();
                }
                // Switch to error filter
                var errorBtn = document.querySelector('.log-filter-btn[data-level="error"]');
                if (errorBtn) errorBtn.click();
            }
        }

        function switchPage(pageId) {
            currentPage = pageId;
            document.querySelectorAll('.page-content').forEach(function(p) { p.classList.remove('active'); });
            var target = document.getElementById('page-' + pageId);
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

        function toggleAdvSearch() {
            var area = document.getElementById('advanced-search-area');
            var icon = document.getElementById('adv-search-icon');
            if (!area) return;
            if (area.style.display === 'none') {
                area.style.display = '';
                if (icon) icon.className = 'fa fa-angle-up';
            } else {
                area.style.display = 'none';
                if (icon) icon.className = 'fa fa-angle-down';
            }
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
            const recent = invoices.slice(0, 5);
            let html = '';
            recent.forEach(function(inv) {
                var statusTag = '';
                if (inv.verify_status === 'success') {
                    statusTag = '<span style="display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;font-size:9px;font-weight:600;background:#ecfdf5;color:#059669;">已验真</span>';
                } else if (inv.verify_status === 'failed' || inv.verify_status === 'voided') {
                    statusTag = '<span style="display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;font-size:9px;font-weight:600;background:#fef2f2;color:#dc2626;">异常</span>';
                } else if (inv.risk_flags) {
                    statusTag = '<span style="display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;font-size:9px;font-weight:600;background:#fffbeb;color:#d97706;">风险</span>';
                } else {
                    statusTag = '<span style="display:inline-flex;align-items:center;padding:1px 6px;border-radius:4px;font-size:9px;font-weight:600;background:#f1f5f9;color:#94a3b8;">待处理</span>';
                }
                html += '<div class="result-card flex items-center gap-3 border-b border-border-light last:border-b-0">';
                html += '<div class="flex-1 min-w-0"><div class="flex items-center gap-2"><span class="font-mono font-medium" style="font-size:11px;color:var(--color-primary);">' + escapeHtml(inv.invoice_num || '') + '</span>' + statusTag + '</div>';
                html += '<p class="text-text-muted text-xs truncate mt-0.5">' + escapeHtml(inv.seller || '') + ' · ' + escapeHtml(inv.item || '') + '</p></div>';
                html += '<div class="text-right flex-shrink-0"><p class="font-semibold font-mono" style="font-size:12px;color:#1e293b;">¥' + formatMoney(inv.total_amount) + '</p>';
                html += '<p class="text-text-muted text-xs">' + escapeHtml(inv.date || '') + '</p></div></div>';
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
            var amtEl = document.getElementById('stat-archived-amt');
            if (amtEl) amtEl.textContent = '¥' + formatMoney(data.stats.total_amt || 0);
            document.getElementById('stat-month-cnt').textContent = data.stats.month_cnt || 0;
            document.getElementById('hero-pending-count').textContent = data.directory_status.pending || 0;
            loadDashboardAlerts();
            renderTrendChart(data);
            renderRecentResults(data);
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

        async function loadSellers() {
            const data = await apiRequest('/sellers');
            if (!data) return;
            var sel = document.getElementById('search-seller');
            sel.innerHTML = '<option value="">全部</option>';
            data.forEach(function(s) { var opt = document.createElement('option'); opt.value = s; opt.textContent = s; sel.appendChild(opt); });
        }

        var _sortField = '';
        var _sortDir = 'desc';
        var _quickFilter = 'all';
        var _lastLogCount = 0;

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
            var btnVerify = document.getElementById('btn-batch-verify');
            var btnCertify = document.getElementById('btn-batch-certify');
            var btnAttrib = document.getElementById('btn-batch-attribution');
            if (!btnCertify) return;
            if (selectedInvoices.size > 0) {
                if (btnVerify && verifyConfig.enabled && verifyConfig.available) {
                    btnVerify.style.display = '';
                    btnVerify.innerHTML = '<i class="fa fa-search"></i> 批量验真 (' + selectedInvoices.size + ')';
                } else if (btnVerify) {
                    btnVerify.style.display = 'none';
                }
                btnCertify.style.display = '';
                btnCertify.innerHTML = '<i class="fa fa-check-circle-o"></i> 批量标记已认证 (' + selectedInvoices.size + ')';
                if (btnAttrib) { btnAttrib.style.display = ''; btnAttrib.innerHTML = '<i class="fa fa-tag"></i> 批量设置归属 (' + selectedInvoices.size + ')'; }
            } else {
                if (btnVerify) btnVerify.style.display = 'none';
                btnCertify.style.display = 'none';
                if (btnAttrib) btnAttrib.style.display = 'none';
            }
        }

        function toggleInvoiceSelect(checkbox) {
            if (checkbox.checked) {
                selectedInvoices.add(checkbox.dataset.invoice);
            } else {
                selectedInvoices.delete(checkbox.dataset.invoice);
            }
            updateBatchCertifyButton();
            updateSelectedInfo();
        }

        function updateSelectedInfo() {
            var el = document.getElementById('selected-info');
            if (!el) return;
            if (selectedInvoices.size > 0) {
                el.style.display = '';
                el.textContent = '已选 ' + selectedInvoices.size + ' 张';
            } else if (_quickFilter !== 'all') {
                // keep filter indicator visible (set by applyQuickFilter)
            } else {
                el.style.display = 'none';
            }
        }

        function toggleSort(field) {
            if (_sortField === field) {
                _sortDir = _sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                _sortField = field;
                _sortDir = field === 'date' ? 'desc' : 'desc';
            }
            var indicators = {'date': 'sort-indicator-date', 'amount': 'sort-indicator-amount'};
            for (var key in indicators) {
                var el = document.getElementById(indicators[key]);
                if (el) el.textContent = (key === _sortField) ? (_sortDir === 'asc' ? ' ▲' : ' ▼') : '';
            }
            loadInvoices(1);
        }

        function applyQuickFilter(filter) {
            _quickFilter = filter;
            document.querySelectorAll('.inv-filter-pill').forEach(function(el) {
                el.classList.toggle('active', el.dataset.filter === filter);
            });
            var filterLabels = {'all':'全部','month':'本月','quarter':'近三月','unverified':'未验真','risk':'高风险'};
            var infoEl = document.getElementById('selected-info');
            if (filter !== 'all' && infoEl) {
                infoEl.style.display = '';
                infoEl.textContent = '筛选: ' + (filterLabels[filter] || filter);
            } else if (infoEl) {
                infoEl.style.display = 'none';
                infoEl.textContent = '';
            }
            loadInvoices(1);
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

        function showBatchAttributionModal() {
            if (selectedInvoices.size === 0) return;
            document.getElementById('batch-attrib-count').textContent = selectedInvoices.size;
            document.getElementById('batch-dept').value = '';
            document.getElementById('batch-project').value = '';
            document.getElementById('batch-expense-type').value = '';
            document.getElementById('batch-attribution-modal').classList.add('show');
        }

        function closeBatchAttributionModal() {
            document.getElementById('batch-attribution-modal').classList.remove('show');
        }

        async function doBatchAttribution() {
            var dept = document.getElementById('batch-dept').value;
            var proj = document.getElementById('batch-project').value;
            var exp = document.getElementById('batch-expense-type').value;
            if (!dept && !proj && !exp) { showToast('请至少填写一项归属信息', 'warning'); return; }
            var nums = Array.from(selectedInvoices);
            var success = 0;
            for (var i = 0; i < nums.length; i++) {
                var result = await apiRequest('/invoices/' + encodeURIComponent(nums[i]) + '/attribution', 'PUT', {
                    department: dept, project: proj, expense_type: exp
                });
                if (result) success++;
            }
            closeBatchAttributionModal();
            showToast('已为 ' + success + ' 张发票设置归属', 'success');
            selectedInvoices.clear();
            loadInvoices(invoiceListPage);
            updateBatchCertifyButton();
        }

        var verifyStatusConfig = {
            'unverified': {label: '待验真', bg: '#f1f5f9', color: '#94a3b8'},
            'success': {label: '已验真', bg: '#ecfdf5', color: '#10b981'},
            'failed': {label: '验真失败', bg: '#fef2f2', color: '#ef4444'},
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
            'high_amount': '单张大额',
            'split_suspicion': '疑似拆票'
        };

        var riskFlagDescMap = {
            'high_amount': '单张发票金额超过10万元，需关注审批流程',
            'split_suspicion': '同一销售方短期内多张开票，可能存在拆分避审'
        };

        function getRiskLabels(riskFlags) {
            if (!riskFlags) return '';
            return riskFlags.split(',').filter(function(f) { return f.trim(); }).map(function(f) {
                return riskFlagLabelsMap[f.trim()] || f.trim();
            }).join('；');
        }

        function getRiskDesc(riskFlags) {
            if (!riskFlags) return '';
            return riskFlags.split(',').filter(function(f) { return f.trim(); }).map(function(f) {
                return riskFlagDescMap[f.trim()] || '';
            }).filter(function(d) { return d; }).join('；');
        }

        function renderRiskBadge(riskFlags) {
            if (!riskFlags) return '';
            var labels = getRiskLabels(riskFlags);
            var desc = getRiskDesc(riskFlags);
            return '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;background:#fef2f2;color:#dc2626;cursor:help;" title="' + escapeHtml(desc) + '"><i class="fa fa-exclamation-triangle" style="font-size:10px;"></i>' + escapeHtml(labels) + '</span>';
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
            updateBatchCertifyButton();
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

        /* ---- 批量验真 ---- */
        function batchVerifyFromList() {
            if (selectedInvoices.size === 0) return;
            if (!verifyConfig.enabled || !verifyConfig.available) {
                showToast('验真功能未启用或API未配置', 'error');
                return;
            }
            document.getElementById('batch-verify-count').textContent = selectedInvoices.size + ' 张';
            document.getElementById('batch-verify-cost').textContent = '¥' + (selectedInvoices.size * verifyConfig.cost).toFixed(2);
            document.getElementById('batch-verify-confirm-modal').classList.add('show');
        }

        function closeBatchVerifyConfirm() {
            document.getElementById('batch-verify-confirm-modal').classList.remove('show');
        }

        async function confirmBatchVerify() {
            closeBatchVerifyConfirm();
            var nums = Array.from(selectedInvoices);
            selectedInvoices.clear();
            updateBatchCertifyButton();

            showToast('正在批量验真，请稍候...', 'info');
            var result = await apiRequest('/invoices/batch-verify', 'POST', {invoice_nums: nums});
            if (!result) return;

            var d = result.data || {};
            var results = d.results || [];

            var successCount = 0, failCount = 0, skipCount = 0;
            results.forEach(function(r) {
                if (r.skipped) skipCount++;
                else if (r.verify_status === 'success') successCount++;
                else failCount++;
            });

            document.getElementById('batch-verify-result-summary').textContent =
                '共 ' + d.total + ' 张 · 成功 ' + successCount + ' · 失败 ' + failCount + ' · 跳过 ' + skipCount + ' · 费用 ¥' + (d.total_cost || 0).toFixed(2);

            var listHtml = '';
            results.forEach(function(r) {
                var icon = r.skipped ? '<i class="fa fa-minus-circle" style="color:#94a3b8;"></i>'
                    : r.verify_status === 'success' ? '<i class="fa fa-check-circle" style="color:#10b981;"></i>'
                    : '<i class="fa fa-times-circle" style="color:#ef4444;"></i>';
                var label = r.skipped ? '已跳过'
                    : r.verify_status === 'success' ? '通过'
                    : '失败';
                listHtml += '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--color-border-light);">';
                listHtml += icon;
                listHtml += '<span class="font-mono text-sm text-text-primary flex-1">' + escapeHtml(r.invoice_num) + '</span>';
                listHtml += '<span class="text-xs" style="color:#94a3b8;">' + label + '</span>';
                listHtml += '</div>';
            });
            document.getElementById('batch-verify-result-list').innerHTML = listHtml;
            document.getElementById('batch-verify-result-modal').classList.add('show');

            loadInvoices(invoiceListPage);
        }

        function closeBatchVerifyResult() {
            document.getElementById('batch-verify-result-modal').classList.remove('show');
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
            if (_sortField) { params.append('sort_field', _sortField); params.append('sort_dir', _sortDir); }
            if (_quickFilter === 'unverified') params.append('verify_status', 'unverified');
            if (_quickFilter === 'risk') params.append('risk_flags', 'yes');
            if (_quickFilter === 'month') {
                var d = new Date(); params.append('date_from', d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-01');
            }
            if (_quickFilter === 'quarter') {
                var d = new Date(); d.setMonth(d.getMonth()-3);
                params.append('date_from', d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-01');
            }
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
                    if (inv.risk_flags) tr.className = 'risk-row';
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
                        '<td>' + (attributionTags || '<span class="text-text-muted text-xs">-</span>') + '</td>' +
                        '<td class="text-center"><button data-invoice="' + escapeHtml(inv.invoice_num) + '" class="text-sm hover:underline font-medium btn-detail" style="color:#6366f1">详情</button></td>';
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
            var typeBadge = document.getElementById('detail-type-badge');
            if (typeBadge) {
                var typeText = data.invoice_type && data.invoice_type.trim() ? data.invoice_type : '未识别';
                typeBadge.textContent = typeText;
            }
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
            document.getElementById('btn-save-all').dataset.invoiceNum = data.invoice_num;
            var verifyBadge = document.getElementById('detail-verify-badge');
            if (verifyBadge) verifyBadge.innerHTML = renderVerifyBadge(data.verify_status || 'unverified');
            var certBadge = document.getElementById('detail-cert-badge');
            if (certBadge) certBadge.innerHTML = renderCertBadge(data.deduction_status || 'unverified');
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
            if (certBadge) certBadge.style.display = 'none';
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
            if (viewBtn) {
                if (data.file_md5) { viewBtn.dataset.md5 = data.file_md5; viewBtn.style.display = 'inline-flex'; }
                else { viewBtn.style.display = 'none'; }
            }

            document.getElementById('invoice-detail-modal').classList.add('show');
            loadDatalistOptions();
        }
        window.showInvoiceDetail = showInvoiceDetail;
        window.openInvoiceDetail = showInvoiceDetail;

        async function loadDatalistOptions() {
            try {
                var sellers = await apiRequest('/sellers');
                if (!sellers) return;
                var deptEl = document.getElementById('dept-options');
                var projEl = document.getElementById('proj-options');
                var deptSet = new Set();
                var projSet = new Set();
                var deptRecords = await apiRequest('/invoices?limit=200');
                if (deptRecords && deptRecords.invoices) {
                    deptRecords.invoices.forEach(function(inv) {
                        if (inv.department) deptSet.add(inv.department);
                        if (inv.project) projSet.add(inv.project);
                    });
                }
                if (deptEl) {
                    deptEl.innerHTML = '';
                    deptSet.forEach(function(d) {
                        deptEl.innerHTML += '<option value="' + escapeHtml(d) + '">';
                    });
                }
                if (projEl) {
                    projEl.innerHTML = '';
                    projSet.forEach(function(p) {
                        projEl.innerHTML += '<option value="' + escapeHtml(p) + '">';
                    });
                }
            } catch(e) {}
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
            _lastLogCount = 0;

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
                        showSuccessModal('处理失败', error, null);
                    } else {
                        var failedFiles = (stats && stats.failed_files) || [];
                        var msg = '所有待识别发票已处理完毕';
                        if (failedFiles.length > 0) {
                            window._pendingFailedProcessing = true;
                            var total = (stats.success || 0) + (stats.duplicate || 0) + (stats.failed || 0);
                            if ((stats.failed || 0) >= total) {
                                msg = '所有文件均处理失败，请查看下方详情';
                            } else {
                                msg = '部分文件处理失败，请查看下方详情';
                            }
                        }
                        showSuccessModal('处理完成', msg, stats, failedFiles);
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
            // Append-only: only render new entries since last poll (avoid flicker)
            var newLogs = data.length > _lastLogCount ? data.slice(_lastLogCount) : data;
            _lastLogCount = data.length;
            if (newLogs.length === 0) { updateLogBadge(); return; }
            var activeFilter = document.querySelector('.log-filter-btn.active');
            var filterLevel = activeFilter ? activeFilter.dataset.level : 'all';
            var icons = { 'info': 'fa-info-circle', 'success': 'fa-check-circle', 'warning': 'fa-exclamation-triangle', 'error': 'fa-times-circle' };
            var colors = { 'info': '#818cf8', 'success': '#34d399', 'warning': '#fbbf24', 'error': '#f87171' };
            newLogs.forEach(function(log) {
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
            _lastLogCount = 0;
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

        var statsPeriod = 'all';
        var statsCustomDates = false;  // true when user sets custom dates

        function switchStatsPeriod(period, btn) {
            statsPeriod = period;
            statsCustomDates = false;
            // Clear custom date inputs
            var fromEl = document.getElementById('stats-date-from');
            var toEl = document.getElementById('stats-date-to');
            if (fromEl) fromEl.value = '';
            if (toEl) toEl.value = '';
            document.querySelectorAll('.stats-period-btn').forEach(function(b) { b.classList.remove('active'); });
            if (btn) btn.classList.add('active');
            var labels = {'month':'本月数据','quarter':'本季度数据','year':'本年度数据','all':'全部数据'};
            var labelEl = document.getElementById('stats-period-label');
            if (labelEl) labelEl.textContent = labels[period] || '';
            loadStatsSummary();
        }

        function onStatsDateChange() {
            var fromEl = document.getElementById('stats-date-from');
            var toEl = document.getElementById('stats-date-to');
            if (fromEl && fromEl.value) {
                statsCustomDates = true;
                document.querySelectorAll('.stats-period-btn').forEach(function(b) { b.classList.remove('active'); });
                var labelEl = document.getElementById('stats-period-label');
                if (labelEl) labelEl.textContent = '自定义日期';
                loadStatsSummary();
            } else if (!fromEl || !fromEl.value) {
                statsCustomDates = false;
                // Re-trigger the active period
                var active = document.querySelector('.stats-period-btn.active');
                if (active) switchStatsPeriod(active.dataset.period, active);
            }
        }

        function getStatsDateRange() {
            if (statsCustomDates) {
                var fromEl = document.getElementById('stats-date-from');
                var toEl = document.getElementById('stats-date-to');
                return {from: fromEl ? fromEl.value : '', to: toEl ? toEl.value : ''};
            }
            var now = new Date();
            var y = now.getFullYear();
            var m = now.getMonth();
            if (statsPeriod === 'month') {
                return {from: y + '-' + String(m+1).padStart(2,'0') + '-01', to: ''};
            } else if (statsPeriod === 'quarter') {
                var qStart = Math.floor(m / 3) * 3;
                return {from: y + '-' + String(qStart+1).padStart(2,'0') + '-01', to: ''};
            } else if (statsPeriod === 'year') {
                return {from: y + '-01-01', to: ''};
            }
            return {from: '', to: ''};
        }

        function showStatsLoading() {
            ['stat-total-amt','stat-total-price','stat-total-tax','stat-seller-cnt','stat-total-cnt'].forEach(function(id) {
                var el = document.getElementById(id);
                if (el) el.innerHTML = '<span class="skeleton" style="display:inline-block;width:60px;height:18px;"></span>';
            });
            var sr = document.getElementById('seller-ranking');
            if (sr) sr.innerHTML = '<p class="text-text-muted text-sm text-center py-4">加载中...</p>';
            var mc = document.getElementById('monthly-amount-chart');
            if (mc) mc.innerHTML = '<p class="text-text-muted text-sm text-center py-4">加载中...</p>';
        }

        async function loadStatsSummary() {
            showStatsLoading();
            var range = getStatsDateRange();
            var params = [];
            if (range.from) params.push('date_from=' + range.from);
            if (range.to) params.push('date_to=' + range.to);
            var qs = params.length ? '?' + params.join('&') : '';
            var result = await apiRequest('/stats/summary' + qs);
            if (!result) return;
            document.getElementById('stat-total-amt').textContent = formatMoney(result.total_amt);
            document.getElementById('stat-total-price').textContent = formatMoney(result.total_price);
            document.getElementById('stat-total-tax').textContent = formatMoney(result.total_tax);
            document.getElementById('stat-seller-cnt').textContent = result.seller_cnt || 0;
            var cntEl = document.getElementById('stat-total-cnt');
            if (cntEl) cntEl.textContent = '共 ' + (result.total_cnt || 0) + ' 张';
            renderSellerRanking(result.top_sellers || []);
            renderMonthlyAmountChart(result.monthly_summary || []);
            renderInvoiceTypeChart(result.type_summary || [], result.total_cnt || 0);
            loadInputTaxSummary(qs);
            loadExpenseDistribution(qs);
        }

        async function loadInputTaxSummary(qs) {
            qs = qs || '';
            var result = await apiRequest('/stats/input-tax-summary' + qs);
            if (!result) return;
            var period = result.period || '';
            var periodEl = document.getElementById('input-tax-period');
            if (periodEl) periodEl.textContent = period;
            // Dynamic heading
            var titleEl = document.getElementById('input-tax-title');
            if (titleEl) {
                var labels = {'month':'进项税额汇总（本月专票）','quarter':'进项税额汇总（本季度专票）','year':'进项税额汇总（本年度专票）','all':'进项税额汇总'};
                titleEl.textContent = labels[statsPeriod] || '进项税额汇总';
            }
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

        function renderInvoiceTypeChart(types, totalCnt) {
            var section = document.getElementById('invoice-type-section');
            var container = document.getElementById('invoice-type-chart');
            if (!section || !container) return;
            if (!types || types.length === 0) {
                section.style.display = 'none';
                return;
            }
            var hasRealType = types.some(function(t) { return t.invoice_type && t.invoice_type.trim() !== ''; });
            if (!hasRealType) {
                section.style.display = '';
                container.innerHTML = '<p class="text-text-muted text-sm text-center py-4">发票类型字段暂未识别，无法统计占比</p>';
                return;
            }
            section.style.display = '';
            container.innerHTML = '';
            if (typeof echarts === 'undefined') { container.innerHTML = '<p class="text-text-muted text-sm text-center py-4">图表库未加载</p>'; return; }
            var colorMap = {'增值税专用发票':'#6366f1','增值税普通发票':'#10b981','全电发票（专用发票）':'#f59e0b','全电发票（普通发票）':'#8b5cf6','增值税电子专用发票':'#6366f1','增值税电子普通发票':'#10b981'};
            var chart = echarts.init(container);
            chart.setOption({
                tooltip: {
                    trigger: 'item',
                    formatter: function(params) {
                        return params.name + '<br/>数量: ' + params.value + ' 张 (' + params.percent + '%)<br/>金额: ¥' + formatMoney(params.data.amt || 0);
                    }
                },
                color: ['#6366f1','#10b981','#f59e0b','#8b5cf6','#ec4899','#14b8a6','#94a3b8'],
                legend: { orient: 'vertical', left: 'left', textStyle: { fontSize: 11, color: '#64748b' } },
                series: [{
                    type: 'pie',
                    radius: ['45%','70%'],
                    center: ['55%','50%'],
                    avoidLabelOverlap: true,
                    itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
                    label: { show: false },
                    emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } },
                    data: types.map(function(t) {
                        var label = t.invoice_type && t.invoice_type.trim() ? t.invoice_type : '未分类';
                        return { name: label, value: t.cnt, amt: t.amt };
                    })
                }]
            });
            chart.on('click', function(params) {
                var el = container.querySelector('.text-xs.text-text-muted');
                if (el) el.textContent = params.name + ': ' + params.value + ' 张';
            });
        }

        function renderSellerRanking(sellers) {
            var container = document.getElementById('seller-ranking');
            if (sellers.length === 0) {
                container.innerHTML = '<p class="text-text-muted text-sm text-center py-4">暂无数据</p>';
                return;
            }
            var maxAmt = Math.max.apply(null, sellers.map(function(s) { return s.amt; }), 1);
            var html = '';
            sellers.forEach(function(s, i) {
                var pct = Math.max(5, (s.amt / maxAmt) * 100);
                html += '<div class="flex items-center gap-3 mb-3 last:mb-0 cursor-pointer" onclick="searchSeller(\'' + escapeHtml((s.seller || '').replace(/'/g,"\\'")) + '\')" title="查看该销售方发票">';
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

        function searchSeller(seller) {
            switchPage('invoices');
            setTimeout(function() {
                var sel = document.getElementById('search-seller');
                if (sel) { sel.value = seller; }
                loadInvoices(1);
            }, 200);
        }

        function renderMonthlyAmountChart(monthly) {
            var container = document.getElementById('monthly-amount-chart');
            if (monthly.length === 0) {
                container.innerHTML = '<p class="text-text-muted text-sm text-center py-4">暂无数据</p>';
                return;
            }
            monthly.reverse();
            var maxVal = Math.max.apply(null, monthly.map(function(m) { return m.amt; }), 1);
            var html = '<div style="display:flex;align-items:flex-end;gap:6px;height:130px;">';
            monthly.forEach(function(m) {
                var pctAmt = Math.max(3, (m.amt / maxVal) * 100);
                var label = m.month ? m.month.substring(5) : '';
                html += '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;">';
                html += '<div style="font-size:9px;color:#64748b;font-weight:500;">¥' + (m.amt >= 10000 ? (m.amt / 10000).toFixed(1) + '万' : m.amt.toFixed(0)) + '</div>';
                // Stacked bar: price (bottom) + tax (top) with column-reverse
                html += '<div style="width:100%;max-width:28px;height:' + pctAmt + '%;display:flex;flex-direction:column-reverse;min-height:3px;">';
                html += '<div style="width:100%;flex:' + (m.price / (m.amt || 1)) + ';background:linear-gradient(180deg,#a78bfa,#6366f1);border-radius:0 0 2px 2px;min-height:2px;" title="不含税: ' + formatMoney(m.price) + '"></div>';
                html += '<div style="width:100%;flex:' + (m.tax / (m.amt || 1)) + ';background:linear-gradient(180deg,#f59e0b,#d97706);border-radius:2px 2px 0 0;min-height:2px;" title="税额: ' + formatMoney(m.tax) + '"></div>';
                html += '</div>';
                html += '<div style="font-size:10px;color:#94a3b8;">' + label + '</div>';
                html += '</div>';
            });
            html += '</div>';
            // Legend
            html += '<div style="display:flex;justify-content:center;gap:16px;margin-top:8px;">';
            html += '<span style="font-size:10px;color:#64748b;"><span style="display:inline-block;width:10px;height:10px;background:#a78bfa;border-radius:2px;margin-right:4px;"></span>不含税金额</span>';
            html += '<span style="font-size:10px;color:#64748b;"><span style="display:inline-block;width:10px;height:10px;background:#f59e0b;border-radius:2px;margin-right:4px;"></span>税额</span>';
            html += '</div>';
            container.innerHTML = html;
        }

        async function exportStatsReport() {
            var range = getStatsDateRange();
            var params = [];
            if (range.from) params.push('date_from=' + range.from);
            if (range.to) params.push('date_to=' + range.to);
            var qs = params.length ? '?' + params.join('&') : '';
            var result = await apiRequest('/stats/summary' + qs);
            if (!result) return;
            var rows = [];
            rows.push('指标,值');
            rows.push('发票总额,' + (result.total_amt || 0));
            rows.push('不含税金额,' + (result.total_price || 0));
            rows.push('税额合计,' + (result.total_tax || 0));
            rows.push('发票数量,' + (result.total_cnt || 0));
            rows.push('销售方数量,' + (result.seller_cnt || 0));
            rows.push('');
            rows.push('销售方排名,金额,数量');
            (result.top_sellers || []).forEach(function(s) {
                rows.push(escapeHtml(s.seller || '未知') + ',' + (s.amt || 0) + ',' + (s.cnt || 0));
            });
            rows.push('');
            rows.push('月度趋势,月份,价税合计,不含税金额,税额');
            (result.monthly_summary || []).forEach(function(m) {
                rows.push((m.month || '') + ',' + (m.amt || 0) + ',' + (m.price || 0) + ',' + (m.tax || 0));
            });
            var csv = rows.join('\n');
            var blob = new Blob(['﻿' + csv], {type: 'text/csv;charset=utf-8;'});
            var link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = '统计报表_' + new Date().toISOString().slice(0, 10) + '.csv';
            link.click();
            URL.revokeObjectURL(link.href);
            showToast('统计报表已导出', 'success');
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

        async function saveAll() {
            var invoiceNum = document.getElementById('btn-save-all').dataset.invoiceNum;
            if (!invoiceNum) return;
            var btn = document.getElementById('btn-save-all');
            btn.innerHTML = '<i class="fa fa-spinner fa-spin-custom"></i> 保存中...';
            btn.disabled = true;
            try {
                var remark = document.getElementById('detail-remark').value;
                var dept = document.getElementById('detail-department').value;
                var proj = document.getElementById('detail-project').value;
                var exp = document.getElementById('detail-expense-type').value;
                var remarkResult = await apiRequest('/invoices/' + encodeURIComponent(invoiceNum) + '/remark', 'PUT', {remark: remark});
                var attrResult = await apiRequest('/invoices/' + encodeURIComponent(invoiceNum) + '/attribution', 'PUT', {
                    department: dept, project: proj, expense_type: exp
                });
                if (remarkResult || attrResult) {
                    closeDetailModal();
                    loadInvoices(invoiceListPage);
                    showToast('保存成功', 'success');
                }
            } finally {
                btn.innerHTML = '<i class="fa fa-save"></i> 保存';
                btn.disabled = false;
            }
        }

        async function loadExpenseDistribution(qs) {
            qs = qs || '';
            var result = await apiRequest('/stats/expense-distribution' + qs);
            if (!result) return;
            renderDeptChart(result.dept_distribution || []);
            renderExpenseTypeChart(result.expense_distribution || []);
            var riskSection = document.getElementById('risk-alert-section');
            var riskCountEl = document.getElementById('risk-alert-count');
            var riskListEl = document.getElementById('risk-alert-list');
            if (result.risk_count > 0 && riskSection && riskCountEl && riskListEl) {
                riskCountEl.textContent = result.risk_count + ' 条预警';
                var html = '<table style="width:100%;border-collapse:collapse;font-size:12px;"><thead><tr style="border-bottom:1px solid var(--color-border-light);">';
                html += '<th style="text-align:left;padding:6px 8px;color:#64748b;font-weight:600;">发票号码</th>';
                html += '<th style="text-align:left;padding:6px 8px;color:#64748b;font-weight:600;">销售方</th>';
                html += '<th style="text-align:right;padding:6px 8px;color:#64748b;font-weight:600;">金额</th>';
                html += '<th style="text-align:left;padding:6px 8px;color:#64748b;font-weight:600;">风险类型</th>';
                html += '<th style="text-align:center;padding:6px 8px;color:#64748b;font-weight:600;">操作</th>';
                html += '</tr></thead><tbody>';
                (result.risk_invoices || []).forEach(function(inv) {
                    var riskLabels = (inv.risk_labels || []).join('；') || '异常';
                    html += '<tr style="border-bottom:1px solid var(--color-border-light);cursor:pointer;" onclick="showInvoiceDetail(\'' + escapeHtml((inv.invoice_num || '').replace(/'/g,"\\'")) + '\')">';
                    html += '<td style="padding:8px;font-family:\'JetBrains Mono\',monospace;color:#1e293b;font-weight:500;">' + escapeHtml(inv.invoice_num) + '</td>';
                    html += '<td style="padding:8px;color:#334155;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(inv.seller) + '</td>';
                    html += '<td style="padding:8px;text-align:right;color:#6366f1;font-weight:600;font-family:\'JetBrains Mono\',monospace;">' + formatMoney(inv.total_amount) + '</td>';
                    html += '<td style="padding:8px;"><span style="display:inline-flex;align-items:center;gap:3px;padding:2px 6px;border-radius:4px;background:#fef2f2;color:#dc2626;font-size:11px;font-weight:600;"><i class="fa fa-exclamation-triangle" style="font-size:9px;"></i>' + escapeHtml(riskLabels) + '</span></td>';
                    html += '<td style="padding:8px;text-align:center;"><span style="color:#6366f1;font-size:11px;">查看详情</span></td>';
                    html += '</tr>';
                });
                html += '</tbody></table>';
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
                _quickFilter = 'all';
                document.querySelectorAll('.inv-filter-pill').forEach(function(el) { el.classList.toggle('active', el.dataset.filter === 'all'); });
                loadInvoices(1);
            });
            document.getElementById('btn-export-csv').addEventListener('click', exportCSV);
            document.getElementById('hero-start-process').addEventListener('click', startProcessing);
            document.getElementById('btn-confirm-process').addEventListener('click', doStartProcessing);
            document.getElementById('btn-clear-logs').addEventListener('click', clearLogs);
            document.getElementById('btn-save-all').addEventListener('click', saveAll);
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
                if (btn) { showInvoiceDetail(btn.dataset.invoice); return; }
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
