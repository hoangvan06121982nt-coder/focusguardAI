document.addEventListener('DOMContentLoaded', () => {
    // --- UI Elements ---
    const htmlEl = document.documentElement;
    const themeToggleBtn = document.getElementById('theme-toggle');
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const cameraOverlay = document.getElementById('camera-overlay');
    const videoStream = document.getElementById('video-stream');
    const alertSound = document.getElementById('alert-sound');
    
    // Stats elements
    const focusScoreEl = document.getElementById('focus-score');
    const focusStatusText = document.getElementById('focus-status-text');
    const topStatus = document.getElementById('top-status');
    const topStatusSub = document.getElementById('top-status-sub');
    const topStatusDot = document.getElementById('top-status-dot');
    const notificationBadge = document.getElementById('notification-badge');
    const gaugePath = document.getElementById('gauge-path');
    const studyTimerEl = document.getElementById('study-timer');
    const distractionCountEl = document.getElementById('distraction-count');
    const warningCountEl = document.getElementById('warning-count');
    
    // Activity Log
    const activityLogContainer = document.getElementById('activity-log');
    const emptyLogMsg = document.getElementById('empty-log-msg');

    // --- State ---
    let isSessionActive = false;
    let statsInterval;
    let timerInterval;
    let secondsElapsed = 0;
    let lastDistractions = 0;
    let currentSessionAlerts = JSON.parse(localStorage.getItem('currentSessionAlerts') || '[]');
    let unreadAlertsCount = parseInt(localStorage.getItem('unreadAlertsCount') || '0');
    let lastLoggedState = 'TAP TRUNG';
    let hasShownEarlyWarning = false;
    let tabSwitchCount = 0;
    
    // Alert history for the second chart
    let alertsHistory = { distraction: 0, sleep: 0, phone: 0 };
    let chartAlertsData = [];

    // --- Theme Management ---
    // Default to light mode as requested, but allow toggle
    const currentTheme = localStorage.getItem('theme') || 'light';
    htmlEl.setAttribute('data-bs-theme', currentTheme);
    updateThemeIcon(currentTheme);

    themeToggleBtn.addEventListener('click', () => {
        const newTheme = htmlEl.getAttribute('data-bs-theme') === 'light' ? 'dark' : 'light';
        htmlEl.setAttribute('data-bs-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme);
        updateChartTheme(newTheme);
    });

    function updateThemeIcon(theme) {
        if (theme === 'dark') {
            themeToggleBtn.innerHTML = '<i class="fa-solid fa-sun"></i>';
        } else {
            themeToggleBtn.innerHTML = '<i class="fa-solid fa-moon"></i>';
        }
    }

    // --- Charts Initialization ---
    if (typeof Chart !== 'undefined') {
        Chart.defaults.font.family = "'Outfit', sans-serif";
    }
    
    function getChartColors() {
        const theme = htmlEl.getAttribute('data-bs-theme');
        return {
            grid: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
            text: theme === 'dark' ? '#94a3b8' : '#64748b'
        };
    }

    const focusChartEl = document.getElementById('focusChart');
    let focusChart = null;
    if (focusChartEl) {
        const ctxFocus = focusChartEl.getContext('2d');
        focusChart = new Chart(ctxFocus, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Điểm tập trung',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointBackgroundColor: '#3b82f6',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { min: 0, max: 100, grid: { color: getChartColors().grid }, ticks: { color: getChartColors().text } },
                    x: { grid: { display: false }, ticks: { color: getChartColors().text, maxTicksLimit: 8 } }
                },
                plugins: { legend: { display: false } },
                animation: { duration: 0 }
            }
        });
    }

    const alertsChartEl = document.getElementById('alertsChart');
    let alertsChart = null;
    if (alertsChartEl) {
        const ctxAlerts = alertsChartEl.getContext('2d');
        alertsChart = new Chart(ctxAlerts, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    { label: 'Mất tập trung', data: [], backgroundColor: '#ef4444' },
                    { label: 'Cảnh báo chú ý', data: [], backgroundColor: '#f59e0b' }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, stacked: true, grid: { color: getChartColors().grid }, ticks: { color: getChartColors().text, stepSize: 1 } },
                    x: { stacked: true, grid: { display: false }, ticks: { color: getChartColors().text } }
                },
                plugins: { 
                    legend: { position: 'bottom', labels: { color: getChartColors().text, usePointStyle: true, boxWidth: 8 } }
                },
                animation: { duration: 0 }
            }
        });
    }

    function updateChartTheme(theme) {
        const colors = getChartColors();
        
        if (typeof focusChart !== 'undefined' && focusChart) {
            focusChart.options.scales.y.grid.color = colors.grid;
            focusChart.options.scales.y.ticks.color = colors.text;
            focusChart.options.scales.x.ticks.color = colors.text;
            focusChart.update();
        }

        if (typeof alertsChart !== 'undefined' && alertsChart) {
            alertsChart.options.scales.y.grid.color = colors.grid;
            alertsChart.options.scales.y.ticks.color = colors.text;
            alertsChart.options.scales.x.ticks.color = colors.text;
            alertsChart.options.plugins.legend.labels.color = colors.text;
            alertsChart.update();
        }
    }

    // --- Helpers ---
    function formatTime(totalSeconds) {
        const h = Math.floor(totalSeconds / 3600).toString().padStart(2, '0');
        const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, '0');
        return `${h}g ${m}p`;
    }

    function updateGauge(score) {
        if (score === null || score === undefined) {
            focusScoreEl.textContent = '--';
            gaugePath.style.strokeDasharray = `0, 100`;
            if (focusStatusText) {
                focusStatusText.className = 'text-muted fw-bold mt-2 mb-0';
                focusStatusText.textContent = 'Chưa có dữ liệu đo';
            }
            return;
        }
        focusScoreEl.textContent = score;
        // The stroke-dasharray is "length, gap". A circle is approx 100 long in this viewBox.
        // If score is 80, length is 80, gap is 20.
        gaugePath.style.strokeDasharray = `${score}, 100`;
        
        // Colors and texts
        if (score >= 80) {
            if (gaugePath) gaugePath.style.stroke = 'var(--success-color)';
            if (focusStatusText) {
                focusStatusText.className = 'text-success fw-bold mt-2 mb-0';
                focusStatusText.textContent = 'Tập trung rất tốt! Cố lên!';
            }
            if (topStatus) topStatus.textContent = 'Tập trung';
            if (topStatusSub) topStatusSub.textContent = "Bạn đang làm rất tốt!";
            if (topStatusDot) topStatusDot.className = 'status-dot bg-success';
        } else if (score >= 50) {
            if (gaugePath) gaugePath.style.stroke = 'var(--warning-color)';
            if (focusStatusText) {
                focusStatusText.className = 'text-warning fw-bold mt-2 mb-0';
                focusStatusText.textContent = 'Đang xao nhãng...';
            }
            if (topStatus) topStatus.textContent = 'Cảnh báo';
            if (topStatusSub) topStatusSub.textContent = "Hãy tập trung vào màn hình.";
            if (topStatusDot) topStatusDot.className = 'status-dot bg-warning';
        } else {
            if (gaugePath) gaugePath.style.stroke = 'var(--danger-color)';
            if (focusStatusText) {
                focusStatusText.className = 'text-danger fw-bold mt-2 mb-0';
                focusStatusText.textContent = 'Mất tập trung nghiêm trọng!';
            }
            if (topStatus) topStatus.textContent = 'Xao nhãng';
            if (topStatusSub) topStatusSub.textContent = "Vui lòng tập trung học tập.";
            if (topStatusDot) topStatusDot.className = 'status-dot bg-danger';
        }
    }

    function updateAntiCheatingUI(isActive) {
        const card = document.getElementById('anti-cheating-card');
        const iconBox = document.getElementById('anti-cheating-icon-box');
        const badge = document.getElementById('anti-cheating-status-badge');
        const label = document.getElementById('lbl-anti-cheating');
        
        const checklistIds = ['chk-phone-det', 'chk-tab-det', 'chk-cam-det', 'chk-multi-det', 'chk-away-det'];
        
        if (isActive) {
            if (card) {
                card.style.background = 'linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, transparent 100%)';
                card.style.borderColor = 'rgba(16, 185, 129, 0.15)';
                card.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.05)';
            }
            if (iconBox) {
                iconBox.className = 'p-3 bg-success bg-opacity-10 text-success rounded-3 fs-3';
            }
            if (badge) {
                badge.className = 'badge bg-success bg-opacity-10 text-success border border-success border-opacity-30 px-3 py-2 fw-bold';
                badge.textContent = '🟢 Bảo vệ đang Hoạt động';
            }
            if (label) {
                label.className = 'form-check-label ms-2 fw-semibold text-success';
                label.textContent = 'Bảo vệ đang Bật';
            }
            checklistIds.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.className = 'fa-solid fa-circle-check text-success';
            });
        } else {
            if (card) {
                card.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, transparent 100%)';
                card.style.borderColor = 'rgba(239, 68, 68, 0.15)';
                card.style.boxShadow = '0 0 10px rgba(239, 68, 68, 0.05)';
            }
            if (iconBox) {
                iconBox.className = 'p-3 bg-danger bg-opacity-10 text-danger rounded-3 fs-3';
            }
            if (badge) {
                badge.className = 'badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-30 px-3 py-2 fw-bold';
                badge.textContent = '🔴 Bảo vệ đã Tắt';
            }
            if (label) {
                label.className = 'form-check-label ms-2 fw-semibold text-danger';
                label.textContent = 'Bật bảo vệ';
            }
            checklistIds.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.className = 'fa-solid fa-circle-check text-muted';
            });
        }
    }

    function addActivityLog(type, message, timeStr) {
        if (emptyLogMsg) emptyLogMsg.style.display = 'none';
        
        let iconHtml = '';
        let typeText = '';
        if (type === 'focus') {
            iconHtml = `<div class="log-icon bg-success-subtle text-success"><i class="fa-solid fa-check"></i></div>`;
            typeText = 'Duy trì tập trung';
        } else if (type === 'warning') {
            iconHtml = `<div class="log-icon bg-warning-subtle text-warning"><i class="fa-solid fa-triangle-exclamation"></i></div>`;
            typeText = 'Cảnh báo chú ý';
        } else {
            iconHtml = `<div class="log-icon bg-danger-subtle text-danger"><i class="fa-solid fa-ban"></i></div>`;
            typeText = 'Mất tập trung cao';
        }
        
        const logHtml = `
            <div class="log-item">
                ${iconHtml}
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between">
                        <strong class="small">${typeText}</strong>
                        <span class="text-muted" style="font-size:0.75rem">${timeStr}</span>
                    </div>
                    <div class="text-muted" style="font-size:0.8rem">${message}</div>
                </div>
            </div>
        `;
        
        activityLogContainer.insertAdjacentHTML('afterbegin', logHtml);
        
        // Keep only last 20 logs
        if (activityLogContainer.children.length > 20) {
            activityLogContainer.removeChild(activityLogContainer.lastChild);
        }
    }

    // --- Main Logic ---
    let lastEmotionName = null;
    let emotionChangeTime = Date.now();
    let emotionMiniChartObj = null;

    function getEmotionSparkline(history) {
        const chars = {
            "Happy": "▆",
            "Neutral": "▃",
            "Tired": "▂",
            "Stressed": "▁"
        };
        return history.map(emo => chars[emo] || "▃").join("");
    }

    function renderEmotionMiniChart(history) {
        const canvas = document.getElementById('emotion-mini-chart');
        if (!canvas) return;
        
        const valueMap = { "Happy": 4, "Neutral": 3, "Tired": 2, "Stressed": 1 };
        const chartData = history.map(emo => valueMap[emo] || 3);
        const labels = Array.from({length: history.length}, (_, i) => i + 1);
        
        const ctx = canvas.getContext('2d');
        if (emotionMiniChartObj) {
            emotionMiniChartObj.data.labels = labels;
            emotionMiniChartObj.data.datasets[0].data = chartData;
            emotionMiniChartObj.update();
        } else {
            emotionMiniChartObj = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Mức cảm xúc',
                        data: chartData,
                        borderColor: '#06b6d4',
                        backgroundColor: 'rgba(6, 182, 212, 0.08)',
                        borderWidth: 1.5,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false }, tooltip: { enabled: false } },
                    scales: {
                        x: { display: false },
                        y: {
                            display: false,
                            min: 0.5,
                            max: 4.5
                        }
                    }
                }
            });
        }
    }

    async function fetchStats() {
        if (!isSessionActive) return;
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            
            // Update Gauge & Status
            updateGauge(data.focus_score);
            
            // Update Floating Cards based on current_state
            const cardFocused = document.getElementById('card-focused');
            const cardSleepy = document.getElementById('card-sleepy');
            const cardPhone = document.getElementById('card-phone');
            
            const subFocused = document.getElementById('sub-focused');
            const subSleepy = document.getElementById('sub-sleepy');
            const subPhone = document.getElementById('sub-phone');

            // Reset classes and subtitles
            cardFocused.classList.remove('active');
            cardSleepy.classList.remove('active');
            cardPhone.classList.remove('active');
            
            subFocused.textContent = 'Độ chú ý cao';
            subSleepy.textContent = 'Mắt mở bình thường';
            subPhone.textContent = 'Không phát hiện';

            if (data.current_state === 'TAP TRUNG') {
                cardFocused.classList.add('active');
            } else if (data.current_state === 'BUON NGU') {
                cardSleepy.classList.add('active');
                subSleepy.textContent = 'Phát hiện ngủ gật!';
            } else if (data.current_state === 'DUNG DIEN THOAI') {
                cardPhone.classList.add('active');
                subPhone.textContent = 'Phát hiện điện thoại!';
            } else if (data.current_state === 'NGOANH MAT DI') {
                subFocused.textContent = 'Đang ngoảnh mặt đi';
            } else if (data.current_state === 'KHONG THAY KHUON MAT') {
                subFocused.textContent = 'Không thấy khuôn mặt';
            }

            if (data.current_state !== lastLoggedState) {
                if (data.current_state === 'BUON NGU') {
                    addAlertRecord('Buồn ngủ');
                } else if (data.current_state === 'DUNG DIEN THOAI') {
                    addAlertRecord('Dùng điện thoại');
                } else if (data.current_state === 'NGOANH MAT DI') {
                    addAlertRecord('Quay đi chỗ khác');
                } else if (data.focus_state === 'AWAY') {
                    addAlertRecord('Rời chỗ');
                }
                lastLoggedState = data.current_state;
            }
            
            // Update Distractions
            if (distractionCountEl) distractionCountEl.textContent = data.distractions;
            
            // Time in frame (measured) and seat leaving (AWAY episodes)
            const screenAttentionPctEl = document.getElementById('screen-attention-pct');
            if (screenAttentionPctEl) {
                const vs = data.visible_seconds || 0;
                screenAttentionPctEl.textContent = `${Math.floor(vs / 60)}p ${vs % 60}s`;
            }
            const seatLeavingCountEl = document.getElementById('seat-leaving-count');
            if (seatLeavingCountEl) {
                seatLeavingCountEl.textContent = `${data.seat_leaving_count} lần`;
            }
            const seatLeavingDurationEl = document.getElementById('seat-leaving-duration');
            if (seatLeavingDurationEl) {
                const mins = Math.round(data.seat_leaving_duration / 60);
                seatLeavingDurationEl.textContent = `Tổng: ${mins} phút`;
            }

            // Live runtime status (server-authoritative, no emotion / prediction)
            const labels = data.labels || {};
            const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            setText('live-focus-state', labels.focus || 'Không có dữ liệu');
            setText('live-visibility', labels.visibility || '—');
            setText('live-attendance', labels.attendance || '—');
            const camLabels = { ACTIVE: 'Đang nhận hình', NO_SIGNAL: 'Mất tín hiệu', WAITING: 'Đang chờ' };
            setText('live-camera-status', camLabels[data.camera_status] || '—');
            const ev = data.event_counts || {};
            setText('evt-phone', ev.PHONE || 0);
            setText('evt-drowsy', ev.DROWSY || 0);
            setText('evt-head-away', ev.HEAD_AWAY || 0);
            setText('evt-away', ev.AWAY || 0);
            setText('val-drowsy-risk', `${ev.DROWSY || 0} lần`);
            setText('val-phone-risk', `${ev.PHONE || 0} lần`);

            // Session monitoring card: only real signals
            const securityViolationsEl = document.getElementById('security-violations');
            const securityScoreEl = document.getElementById('security-score');
            const securityLastEventEl = document.getElementById('security-last-event');
            const antiCheatingAnalysisEl = document.getElementById('anti-cheating-analysis');
            if (securityViolationsEl) securityViolationsEl.textContent = data.distractions || 0;
            if (securityScoreEl) securityScoreEl.textContent = tabSwitchCount;
            if (securityLastEventEl) securityLastEventEl.textContent = labels.focus || '—';
            if (antiCheatingAnalysisEl) {
                antiCheatingAnalysisEl.textContent = data.camera_status === 'NO_SIGNAL'
                    ? 'Camera không gửi hình: điểm tạm dừng, không bị trừ.'
                    : 'Chỉ hành vi kéo dài mới được ghi nhận thành sự kiện.';
            }

            if (warningCountEl) warningCountEl.textContent = ev.HEAD_AWAY || 0;
            
            // Update Notification Badge
            if (notificationBadge) {
                if (unreadAlertsCount > 0) {
                    notificationBadge.style.display = 'inline-block';
                    notificationBadge.textContent = unreadAlertsCount;
                    if (data.distractions > lastDistractions) {
                        notificationBadge.style.transform = 'translate(-50%, -50%) scale(1.4)';
                        setTimeout(() => {
                            notificationBadge.style.transform = 'translate(-50%, -50%) scale(1)';
                        }, 300);
                    }
                } else {
                    notificationBadge.style.display = 'none';
                }
            }
            
            // Play sound if new distraction
            if (data.distractions > lastDistractions) {
                lastDistractions = data.distractions;
                
                const soundEnabled = localStorage.getItem('alertSoundEnabled') !== 'false';
                if (soundEnabled) {
                    const volumeVal = parseInt(localStorage.getItem('alertVolume') || '80') / 100;
                    alertSound.volume = volumeVal;
                    alertSound.currentTime = 0;
                    alertSound.play().catch(e => {});
                }
                
                const now = new Date();
                addActivityLog('danger', 'Phát hiện hành vi xao nhãng.', now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}));
                
                // One bar per real behaviour event recorded by the server
                chartAlertsData.push({ time: now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}), dist: 1, warn: 0 });
            }
            
            // Update Focus Chart
            if (data.history.length > 0) {
                focusChart.data.labels = data.history.map(h => h.time.substring(0,5)); // HH:MM
                focusChart.data.datasets[0].data = data.history.map(h => h.score);
                focusChart.update();
                
                // Keep alerts chart in sync with time axis
                if (chartAlertsData.length === 0 && data.history.length > 0) {
                    chartAlertsData.push({ time: data.history[data.history.length-1].time.substring(0,5), dist: 0, warn: 0 });
                }
                alertsChart.data.labels = chartAlertsData.map(c => c.time);
                alertsChart.data.datasets[0].data = chartAlertsData.map(c => c.dist);
                alertsChart.data.datasets[1].data = chartAlertsData.map(c => c.warn);
                alertsChart.update();
            }
            
        } catch (error) {
            console.error("Error fetching stats:", error);
        }
    }

    if (btnStart) {
        btnStart.addEventListener('click', async () => {
            try {
                const subjectSelect = document.getElementById('select-subject');
                const subjectVal = subjectSelect ? subjectSelect.value : 'Toán';
                await fetch('/api/start_session', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subject: subjectVal })
                });
                isSessionActive = true;
                
                // UI States
                if (cameraOverlay) cameraOverlay.style.display = 'none';
                const cameraStatusOverlay = document.getElementById('camera-status-overlay');
                if (cameraStatusOverlay) cameraStatusOverlay.style.display = 'flex';
                if (btnStop) btnStop.style.display = 'block';
                if (videoStream) {
                    videoStream.style.opacity = '1';
                    videoStream.src = '/video_feed';
                }
                
                // Reset Data
                secondsElapsed = 0;
                lastDistractions = 0;
                currentSessionAlerts = [];
                unreadAlertsCount = 0;
                localStorage.setItem('currentSessionAlerts', JSON.stringify([]));
                localStorage.setItem('unreadAlertsCount', '0');
                lastLoggedState = 'TAP TRUNG';
                chartAlertsData = [];
                if (focusChart) {
                    focusChart.data.labels = []; focusChart.data.datasets[0].data = []; focusChart.update();
                }
                if (alertsChart) {
                    alertsChart.data.labels = []; alertsChart.data.datasets[0].data = []; alertsChart.data.datasets[1].data = []; alertsChart.update();
                }
                if (activityLogContainer) activityLogContainer.innerHTML = '';
                
                // Reset Topbar Status
                if (topStatus) topStatus.textContent = 'Đang học';
                if (topStatusSub) topStatusSub.textContent = 'Đang phân tích độ chú ý...';
                if (topStatusDot) topStatusDot.className = 'status-dot bg-success';
                if (notificationBadge) notificationBadge.style.display = 'none';
                
                const now = new Date();
                addActivityLog('focus', 'Hệ thống bắt đầu giám sát học tập.', now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}));
                
                // Intervals
                statsInterval = setInterval(fetchStats, 1000);
                timerInterval = setInterval(() => {
                    secondsElapsed++;
                    if (studyTimerEl) studyTimerEl.textContent = formatTime(secondsElapsed);
                }, 1000);
                
                // Audio unlock
                alertSound.volume = 0;
                alertSound.play().then(() => { alertSound.pause(); alertSound.volume = 1; alertSound.currentTime = 0; }).catch(e=>{});
                
            } catch (e) { console.error(e); }
        });
    }

    if (btnStop) {
        btnStop.addEventListener('click', async () => {
            try {
                await fetch('/api/stop_session', { method: 'POST' });
                isSessionActive = false;
                
                if (cameraOverlay) {
                    cameraOverlay.style.display = 'flex';
                    cameraOverlay.innerHTML = '<span class="text-white fw-bold">PHIÊN HỌC KẾT THÚC</span>';
                }
                const cameraStatusOverlay = document.getElementById('camera-status-overlay');
                if (cameraStatusOverlay) cameraStatusOverlay.style.display = 'none';
                if (btnStop) btnStop.style.display = 'none';
                if (videoStream) {
                    videoStream.style.opacity = '0.4';
                    videoStream.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
                }
                
                // Update Topbar Status
                if (topStatus) topStatus.textContent = 'Chưa học';
                if (topStatusSub) topStatusSub.textContent = 'Phiên học đã kết thúc.';
                if (topStatusDot) topStatusDot.className = 'status-dot bg-secondary';
                
                clearInterval(statsInterval);
                clearInterval(timerInterval);
                
                const now = new Date();
                addActivityLog('warning', 'Phiên học đã kết thúc bởi người dùng.', now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}));
                
            } catch (e) { console.error(e); }
        });
    }
    
    // --- Control Capsule Handlers ---
    const btnScreenshot = document.getElementById('btn-screenshot');
    const btnFullscreen = document.getElementById('btn-fullscreen');
    const videoContainer = document.querySelector('.video-container');

    if (btnScreenshot) {
        btnScreenshot.addEventListener('click', () => {
            if (!isSessionActive) return;
            try {
                const canvas = document.createElement('canvas');
                canvas.width = videoStream.naturalWidth || videoStream.width || 640;
                canvas.height = videoStream.naturalHeight || videoStream.height || 480;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(videoStream, 0, 0, canvas.width, canvas.height);
                
                const link = document.createElement('a');
                link.download = `snapshot_${new Date().toISOString().slice(0,10)}_${new Date().toTimeString().slice(0,8).replace(/:/g,"")}.jpg`;
                link.href = canvas.toDataURL('image/jpeg');
                link.click();
            } catch (err) {
                console.error("Lỗi chụp ảnh camera:", err);
            }
        });
    }

    if (btnFullscreen && videoContainer) {
        btnFullscreen.addEventListener('click', () => {
            try {
                if (!document.fullscreenElement) {
                    videoContainer.requestFullscreen().catch(err => {
                        console.error(`Lỗi mở toàn màn hình: ${err.message}`);
                    });
                } else {
                    document.exitFullscreen();
                }
            } catch (err) {
                console.error(err);
            }
        });
    }
    
    // --- Custom Functions for Sidebar Sections ---
    
    // 1. Tab Routing Logic (Server-side URL Routing helper)
    function handlePageRouting() {
        const activeTab = window.ACTIVE_TAB || 'dashboard';

        // If switching to Stats tab, load history, heatmap, leaderboard
        if (activeTab === 'stats') {
            loadDailyLeaderboard();
            loadStudentHeatmap();
            loadSessionHistory();
        }
        
        // If switching to Reports tab, update current report values and alerts table
        if (activeTab === 'reports') {
            loadSessionHistory();
            updateReportValues();
            updateAlertsTable();
        }
    }

    async function initSessionState() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            
            if (data.is_active) {
                isSessionActive = true;
                secondsElapsed = data.seconds_elapsed;
                lastDistractions = data.distractions;
                
                // Update header timer & status
                if (studyTimerEl) studyTimerEl.textContent = formatTime(secondsElapsed);
                if (distractionCountEl) distractionCountEl.textContent = data.distractions;
                if (warningCountEl) warningCountEl.textContent = (data.event_counts || {}).HEAD_AWAY || 0;
                
                // Set Topbar Status
                if (topStatus) topStatus.textContent = 'Đang học';
                if (topStatusSub) topStatusSub.textContent = 'Đang phân tích độ chú ý...';
                if (topStatusDot) topStatusDot.className = 'status-dot bg-success';
                
                // Set Notification Badge
                if (notificationBadge) {
                    if (unreadAlertsCount > 0) {
                        notificationBadge.style.display = 'inline-block';
                        notificationBadge.textContent = unreadAlertsCount;
                    } else {
                        notificationBadge.style.display = 'none';
                    }
                }
                
                // Show Stop button, hide Start button/overlay
                if (btnStop) btnStop.style.display = 'block';
                if (cameraOverlay) cameraOverlay.style.display = 'none';
                
                const cameraStatusOverlay = document.getElementById('camera-status-overlay');
                if (cameraStatusOverlay) cameraStatusOverlay.style.display = 'flex';
                
                if (videoStream) {
                    videoStream.style.opacity = '1';
                    videoStream.src = '/video_feed';
                }
                
                // Start background monitoring loops
                statsInterval = setInterval(fetchStats, 1000);
                timerInterval = setInterval(() => {
                    secondsElapsed++;
                    if (studyTimerEl) studyTimerEl.textContent = formatTime(secondsElapsed);
                }, 1000);
            }
        } catch (e) {
            console.error("Lỗi phục hồi phiên học:", e);
        }
    }

    // 2. Stats Section Logic (Session history loader)
    const historyTableBody = document.getElementById('history-table-body');
    const statsTotalSessions = document.getElementById('stats-total-sessions');
    const statsTotalTime = document.getElementById('stats-total-time');
    const statsAvgScore = document.getElementById('stats-avg-score');
    const btnRefreshHistory = document.getElementById('btn-refresh-history');

    let sessionComparisonChartObj = null;
    let subjectAnalyticsChartObj = null;

    async function initStudentStatsCharts() {
        const compEl = document.getElementById('sessionComparisonChart');
        if (compEl) {
            try {
                const res = await fetch('/api/student/session_comparison');
                const data = await res.json();
                const labels = (Array.isArray(data) ? data : []).map(d => String(d.start_time || '').substring(5, 16));
                const scores = data.map(d => d.score);
                const ctx = compEl.getContext('2d');
                if (sessionComparisonChartObj) sessionComparisonChartObj.destroy();
                sessionComparisonChartObj = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Điểm tập trung',
                            data: scores,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.08)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: { y: { min: 0, max: 100 } }
                    }
                });
            } catch (e) {
                console.error("Lỗi vẽ biểu đồ so sánh phiên học:", e);
            }
        }
        
        const subjEl = document.getElementById('subjectAnalyticsChart');
        if (subjEl) {
            try {
                const res = await fetch('/api/student/subject_analytics');
                const data = await res.json();
                const labels = data.map(d => d.subject);
                const scores = data.map(d => d.score);
                const ctx = subjEl.getContext('2d');
                if (subjectAnalyticsChartObj) subjectAnalyticsChartObj.destroy();
                subjectAnalyticsChartObj = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Độ tập trung TB',
                            data: scores,
                            backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#7c3aed', '#ef4444']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: { y: { min: 0, max: 100 } },
                        plugins: { legend: { display: false } }
                    }
                });
            } catch (e) {
                console.error("Lỗi vẽ biểu đồ môn học:", e);
            }
        }
    }

    async function loadDailyLeaderboard() {
        // Students only see their OWN attendance for class sessions (missed ones included).
        const body = document.getElementById('leaderboard-body');
        if (!body) return;
        try {
            const res = await fetch('/api/student/attendance_history');
            const data = await res.json();
            if (!Array.isArray(data) || data.length === 0) {
                body.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-3"><small>Chưa có buổi học lớp nào.</small></td></tr>';
                return;
            }
            const labels = { PRESENT: 'Có mặt', LATE: 'Đi muộn', ABSENT: 'Vắng mặt' };
            body.innerHTML = data.slice(0, 10).map(a => `
                <tr>
                    <td><small>${escapeHtml(a.started_at || '')}</small></td>
                    <td><span class="${a.missed ? 'text-danger' : 'text-success'} fw-semibold">${labels[a.attendance_status] || a.attendance_status}</span></td>
                    <td class="text-end fw-bold">${fmtScore(a.focus_score)}</td>
                </tr>`).join('');
        } catch (e) {
            console.error("Lỗi tải lịch sử điểm danh:", e);
            body.innerHTML = '<tr><td colspan="3" class="text-center text-danger py-3"><small>Lỗi tải dữ liệu.</small></td></tr>';
        }
    }

    async function loadStudentHeatmap() {
        const grid = document.getElementById('student-heatmap-grid');
        if (!grid) return;
        try {
            const res = await fetch('/api/student/heatmap');
            const data = await res.json();
            grid.innerHTML = '';
            
            Object.entries(data).forEach(([hour, val]) => {
                const cell = document.createElement('div');
                cell.className = 'heatmap-cell';
                cell.style.width = '35px';
                cell.style.height = '35px';
                cell.style.borderRadius = '6px';
                cell.style.display = 'flex';
                cell.style.flexDirection = 'column';
                cell.style.alignItems = 'center';
                cell.style.justifyContent = 'center';
                cell.style.fontSize = '0.7rem';
                cell.style.fontWeight = 'bold';
                cell.style.cursor = 'pointer';
                cell.textContent = hour.substring(0,2);
                
                if (val.status === 'high') {
                    cell.style.background = '#10b981';
                    cell.style.color = '#ffffff';
                    cell.title = `${hour} - Tập trung cao: ${val.score}%`;
                } else if (val.status === 'med') {
                    cell.style.background = '#f59e0b';
                    cell.style.color = '#ffffff';
                    cell.title = `${hour} - Tập trung trung bình: ${val.score}%`;
                } else if (val.status === 'low') {
                    cell.style.background = '#ef4444';
                    cell.style.color = '#ffffff';
                    cell.title = `${hour} - Mất tập trung: ${val.score}%`;
                } else {
                    cell.style.background = 'rgba(255, 255, 255, 0.05)';
                    cell.style.color = '#888888';
                    cell.style.border = '1px dashed rgba(255, 255, 255, 0.1)';
                    cell.title = `${hour} - Không có dữ liệu`;
                }
                grid.appendChild(cell);
            });
        } catch (e) {
            console.error("Lỗi tải heatmap:", e);
        }
    }

    async function loadSessionHistory() {
        try {
            historyTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Đang tải lịch sử phiên học...</td></tr>';
            const res = await fetch('/api/sessions');
            const sessions = await res.json();

            // Load charts too
            initStudentStatsCharts();

            // Load profile trend badge
            try {
                const profileRes = await fetch('/api/student/profile');
                const profileData = await profileRes.json();
                const trendBadge = document.getElementById('profile-trend-badge');
                if (trendBadge && profileData) {
                    if (profileData.trend === 'up') {
                        trendBadge.className = 'badge bg-success-subtle text-success d-flex align-items-center';
                        trendBadge.innerHTML = '<i class="fa-solid fa-arrow-trend-up me-1"></i>Tiến bộ';
                    } else if (profileData.trend === 'down') {
                        trendBadge.className = 'badge bg-danger-subtle text-danger d-flex align-items-center';
                        trendBadge.innerHTML = '<i class="fa-solid fa-arrow-trend-down me-1"></i>Sa sút';
                    } else if (profileData.trend === 'stable') {
                        trendBadge.className = 'badge bg-secondary-subtle text-secondary d-flex align-items-center';
                        trendBadge.innerHTML = '<i class="fa-solid fa-arrows-left-right me-1"></i>Ổn định';
                    } else {
                        trendBadge.className = 'badge bg-secondary-subtle text-secondary d-flex align-items-center';
                        trendBadge.innerHTML = '<i class="fa-solid fa-circle-info me-1"></i>Không đủ dữ liệu';
                    }
                }
            } catch (err) {
                console.error("Lỗi tải profile stats:", err);
            }

            const selectPeriod = document.getElementById('select-stats-period');
            const period = selectPeriod ? selectPeriod.value : '7days';
            
            const now = new Date();
            const filteredSessions = sessions.filter(sess => {
                const sessDate = new Date(sess.start_time.replace(/-/g, '/'));
                if (isNaN(sessDate.getTime())) return true;
                
                const diffMs = now - sessDate;
                const diffDays = diffMs / (1000 * 60 * 60 * 24);
                
                if (period === 'today') {
                    return sessDate.toDateString() === now.toDateString();
                } else if (period === '7days') {
                    return diffDays <= 7;
                } else if (period === '30days') {
                    return diffDays <= 30;
                }
                return true;
            });

            let totalDuration = 0;
            let sumScores = 0;
            let scored = 0;

            historyTableBody.innerHTML = '';
            filteredSessions.forEach(sess => {
                const sc = (sess.avg_focus_score !== null && sess.avg_focus_score !== undefined) ? Math.round(sess.avg_focus_score) : sess.final_score;
                totalDuration += sess.duration_seconds || 0;
                if (sc !== null && sc !== undefined) { sumScores += sc; scored++; }
                const badge = (sc === null || sc === undefined) ? '<span class="badge bg-secondary">N/A</span>'
                    : `<span class="badge ${sc >= 85 ? 'bg-success' : sc >= 70 ? 'bg-warning' : 'bg-danger'}">${sc}/100</span>`;
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${escapeHtml(sess.start_time)}</td>
                    <td>${escapeHtml(sess.end_time || 'Đang diễn ra')}</td>
                    <td>${formatTime(sess.duration_seconds || 0)}</td>
                    <td>${badge}</td>
                    <td class="text-danger fw-bold">${sess.total_distractions || 0}</td>
                `;
                historyTableBody.appendChild(tr);
            });

            // Class sessions the student missed are listed too (never silently dropped).
            try {
                const attRes = await fetch('/api/student/attendance_history');
                const att = await attRes.json();
                (Array.isArray(att) ? att : []).filter(a => a.missed).forEach(a => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${escapeHtml(a.started_at)}</td>
                        <td>${escapeHtml(a.ended_at || '')}</td>
                        <td>—</td>
                        <td><span class="badge bg-danger">Vắng mặt</span></td>
                        <td>—</td>
                    `;
                    historyTableBody.appendChild(tr);
                });
            } catch (err) {
                console.error("Lỗi tải lịch sử điểm danh:", err);
            }

            if (historyTableBody.children.length === 0) {
                historyTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Chưa có dữ liệu phiên học nào trong chu kỳ này.</td></tr>';
            }
            statsTotalSessions.textContent = filteredSessions.length;
            statsTotalTime.textContent = formatTime(totalDuration);
            statsAvgScore.textContent = scored ? Math.round(sumScores / scored) + '/100' : 'N/A';

        } catch (e) {
            console.error("Lỗi khi tải lịch sử:", e);
            historyTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-4">Lỗi kết nối máy chủ.</td></tr>';
        }
    }

    if (btnRefreshHistory) {
        btnRefreshHistory.addEventListener('click', loadSessionHistory);
    }

    // 3. Alerts Logger and filter
    const alertFilter = document.getElementById('alert-filter');
    const alertsTableBody = document.getElementById('alerts-table-body');

    function addAlertRecord(type) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
        currentSessionAlerts.push({
            time: timeStr,
            type: type,
            status: 'Đã nhắc nhở'
        });
        
        if (type.includes('ngủ')) alertsHistory.sleep++;
        else if (type.includes('thoại')) alertsHistory.phone++;
        else if (type.includes('Rời')) alertsHistory.away = (alertsHistory.away || 0) + 1;
        else alertsHistory.distraction++;
        
        localStorage.setItem('currentSessionAlerts', JSON.stringify(currentSessionAlerts));
        
        unreadAlertsCount++;
        localStorage.setItem('unreadAlertsCount', unreadAlertsCount.toString());
        if (notificationBadge) {
            notificationBadge.style.display = 'inline-block';
            notificationBadge.textContent = unreadAlertsCount;
            notificationBadge.style.transform = 'translate(-50%, -50%) scale(1.4)';
            setTimeout(() => {
                notificationBadge.style.transform = 'translate(-50%, -50%) scale(1)';
            }, 300);
        }
        
        // Refresh dropdown list if open
        const notifDropdown = document.getElementById('notification-dropdown');
        if (notifDropdown && !notifDropdown.classList.contains('d-none')) {
            renderNotificationDropdown();
        }
        
        // Refresh alert table if active tab is alerts
        updateAlertsTable();
    }

    function updateAlertsTable() {
        if (!alertsTableBody) return;
        const filterVal = alertFilter.value;
        const filtered = currentSessionAlerts.filter(item => {
            if (filterVal === 'all') return true;
            return item.type === filterVal;
        });

        if (filtered.length === 0) {
            alertsTableBody.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-4">Chưa có cảnh báo nào trong danh mục này.</td></tr>';
            return;
        }

        alertsTableBody.innerHTML = '';
        filtered.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.time}</td>
                <td><span class="badge bg-danger-subtle text-danger border-danger">${item.type}</span></td>
                <td><span class="badge bg-success-subtle text-success border-success">${item.status}</span></td>
            `;
            alertsTableBody.appendChild(tr);
        });
    }

    if (alertFilter) {
        alertFilter.addEventListener('change', updateAlertsTable);
    }

    // 4. Reports Section Logic
    const reportDate = document.getElementById('report-date');
    const reportDuration = document.getElementById('report-duration');
    const reportScore = document.getElementById('report-score');
    const reportDistractions = document.getElementById('report-distractions');
    const reportAiEvaluation = document.getElementById('report-ai-evaluation');
    const reportAiEvalBox = document.getElementById('report-ai-eval-box');
    const btnExportJson = document.getElementById('btn-export-json');
    const btnPrintReport = document.getElementById('btn-print-report');

    let reportDistractionsChartObj = null;

    async function renderReport(sessionId, durationSec, score, violations) {
        const hasScore = score !== null && score !== undefined && !isNaN(score);
        if (reportDuration) reportDuration.textContent = formatTime(durationSec || 0);
        if (reportScore) reportScore.textContent = hasScore ? `${score}/100` : 'N/A';
        if (reportDistractions) reportDistractions.textContent = violations || 0;

        let evalText, color;
        if (!hasScore) {
            evalText = 'Không đủ dữ liệu: camera chưa đo được khuôn mặt trong phiên này.';
            color = '#6366f1';
        } else if (score >= 85) {
            evalText = 'Điểm tập trung cao (≥ 85). Ít hành vi xao nhãng kéo dài được ghi nhận.';
            color = '#10b981';
        } else if (score >= 70) {
            evalText = 'Điểm tập trung khá (70–84). Có một số hành vi xao nhãng kéo dài; nên nghỉ ngắn định kỳ.';
            color = '#f59e0b';
        } else {
            evalText = 'Điểm tập trung thấp (< 70). Xem biểu đồ bên dưới để biết loại hành vi được ghi nhận nhiều nhất.';
            color = '#ef4444';
        }
        if (reportAiEvaluation) reportAiEvaluation.textContent = evalText;
        if (reportAiEvalBox) {
            reportAiEvalBox.style.background = 'rgba(99, 102, 241, 0.06)';
            reportAiEvalBox.style.border = `1px solid ${color}33`;
            reportAiEvalBox.style.color = color;
        }
        const analysisRow = document.getElementById('report-analysis-row');
        if (analysisRow) analysisRow.style.display = 'flex';

        const chartCanvas = document.getElementById('reportDistractionsChart');
        if (!chartCanvas) return;
        let counts = null;
        if (sessionId) {
            try {
                const breakdownRes = await fetch(`/api/session/${sessionId}/breakdown`);
                const breakdown = await breakdownRes.json();
                if (breakdown && breakdown.counts) counts = breakdown.counts;
            } catch (e) {
                console.error("Lỗi tải breakdown:", e);
            }
        } else {
            counts = { PHONE: alertsHistory.phone || 0, DROWSY: alertsHistory.sleep || 0, HEAD_AWAY: alertsHistory.distraction || 0, AWAY: alertsHistory.away || 0 };
        }
        counts = counts || { PHONE: 0, DROWSY: 0, HEAD_AWAY: 0, AWAY: 0 };
        const chartData = [counts.PHONE || 0, counts.DROWSY || 0, counts.HEAD_AWAY || 0, counts.AWAY || 0];
        const ctx = chartCanvas.getContext('2d');
        if (reportDistractionsChartObj) reportDistractionsChartObj.destroy();
        reportDistractionsChartObj = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Điện thoại', 'Buồn ngủ', 'Quay đi', 'Rời chỗ'],
                datasets: [{ data: chartData, backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#94a3b8'], borderWidth: 0 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                plugins: { legend: { display: false } }
            }
        });
    }

    async function updateReportValues() {
        if (!reportDate) return;
        const now = new Date();
        reportDate.textContent = now.toLocaleDateString('vi-VN', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        
        try {
            const recRes = await fetch('/api/student/recommendations');
            const recData = await recRes.json();
            const coachSec = document.getElementById('report-coach-section');
            const coachRec = document.getElementById('report-coach-recommendation');
            if (coachSec && coachRec && recData && recData.text) {
                coachRec.textContent = recData.text;
                coachSec.style.display = 'block';
            }
        } catch (e) {
            console.error("Lỗi khi tải đề xuất AI Coach:", e);
        }
        
        if (secondsElapsed > 0 && isSessionActive) {
            const liveScore = parseInt(focusScoreEl.textContent);
            renderReport(null, secondsElapsed, isNaN(liveScore) ? null : liveScore, parseInt(distractionCountEl.textContent) || 0);
        } else {
            try {
                const res = await fetch('/api/latest_session');
                const data = await res.json();
                if (data && data.status !== 'empty') {
                    reportDate.textContent = data.start_time;
                    renderReport(data.id, data.duration_seconds, data.avg_focus_score !== null && data.avg_focus_score !== undefined ? Math.round(data.avg_focus_score) : data.final_score, data.total_distractions);
                } else {
                    reportDuration.textContent = '00g 00p 00s';
                    reportScore.textContent = 'N/A';
                    reportDistractions.textContent = '0';
                    reportAiEvaluation.innerHTML = 'Hệ thống chưa ghi nhận dữ liệu phiên học nào trong cơ sở dữ liệu. Vui lòng thực hiện phiên học đầu tiên.';
                    reportAiEvalBox.style.background = 'rgba(99, 102, 241, 0.08)';
                    reportAiEvalBox.style.border = '1px solid rgba(99, 102, 241, 0.15)';
                    reportAiEvalBox.style.color = '#6366f1';
                }
            } catch (e) {
                console.error("Lỗi khi tải báo cáo mới nhất:", e);
            }
        }
    }

    if (btnPrintReport) {
        btnPrintReport.addEventListener('click', () => {
            window.print();
        });
    }

    if (btnExportJson) {
        btnExportJson.addEventListener('click', () => {
            const sessionData = {
                student_name: document.getElementById('report-student-name').textContent,
                report_date: reportDate.textContent,
                duration: reportDuration.textContent,
                focus_score: reportScore.textContent,
                total_distractions: reportDistractions.textContent,
                alerts: currentSessionAlerts
            };
            
            const blob = new Blob([JSON.stringify(sessionData, null, 4)], { type: 'application/json' });
            const link = document.createElement('a');
            link.download = `report_${new Date().toISOString().slice(0,10)}.json`;
            link.href = URL.createObjectURL(blob);
            link.click();
        });
    }

    // 5. Settings Section Logic
    const settingsForm = document.getElementById('settings-form');
    const settingEar = document.getElementById('setting-ear');
    const settingDrowsy = document.getElementById('setting-drowsy');
    const settingDistraction = document.getElementById('setting-distraction');
    const settingSoundEnabled = document.getElementById('setting-sound-enabled');
    const settingVolume = document.getElementById('setting-volume');
    const settingDisplayName = document.getElementById('setting-display-name');
    
    const valEar = document.getElementById('val-ear');
    const valDrowsy = document.getElementById('val-drowsy');
    const valDistraction = document.getElementById('val-distraction');
    const btnResetSettings = document.getElementById('btn-reset-settings');

    // Sync sliders value display
    if (settingEar) {
        settingEar.addEventListener('input', () => valEar.textContent = settingEar.value);
    }
    if (settingDrowsy) {
        settingDrowsy.addEventListener('input', () => valDrowsy.textContent = settingDrowsy.value + 's');
    }
    if (settingDistraction) {
        settingDistraction.addEventListener('input', () => valDistraction.textContent = settingDistraction.value + 's');
    }

    // Load initial settings
    async function loadSettings() {
        try {
            const res = await fetch('/api/settings');
            const data = await res.json();
            
            if (settingEar) {
                settingEar.value = data.ear_threshold;
                valEar.textContent = data.ear_threshold;
            }
            if (settingDrowsy) {
                settingDrowsy.value = data.drowsy_threshold;
                valDrowsy.textContent = data.drowsy_threshold + 's';
            }
            if (settingDistraction) {
                settingDistraction.value = data.distraction_threshold;
                valDistraction.textContent = data.distraction_threshold + 's';
            }
            // Thresholds are centralised on the server; only admins may change them.
            [settingEar, settingDrowsy, settingDistraction].forEach(el => { if (el) el.disabled = !data.editable; });
            
            // Sound and Volume local
            const localSound = localStorage.getItem('alertSoundEnabled');
            if (localSound !== null && settingSoundEnabled) {
                settingSoundEnabled.checked = localSound === 'true';
            }
            const localVolume = localStorage.getItem('alertVolume');
            if (localVolume !== null && settingVolume) {
                settingVolume.value = localVolume;
            }
            
            // Name loading
            const localName = localStorage.getItem('studentDisplayName') || 'Học sinh';
            if (settingDisplayName) {
                settingDisplayName.value = localName;
            }
            
            // Set elements on page
            const reportNameEl = document.getElementById('report-student-name');
            if (reportNameEl) reportNameEl.textContent = localName;
            
            const welcomeHeader = document.querySelector('.welcome-msg h4');
            if (welcomeHeader) {
                welcomeHeader.innerHTML = `Chào mừng trở lại, ${localName}! 👋`;
            }

            const topbarDisplayName = document.getElementById('topbar-display-name');
            if (topbarDisplayName) topbarDisplayName.textContent = localName;

            const topbarAvatar = document.getElementById('topbar-avatar');
            if (topbarAvatar) topbarAvatar.textContent = localName.substring(0, 2).toUpperCase();
        } catch (e) {
            console.error("Lỗi khi tải cài đặt:", e);
        }
    }

    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const earVal = parseFloat(settingEar.value);
            const drowsyVal = parseFloat(settingDrowsy.value);
            const distractVal = parseFloat(settingDistraction.value);
            const soundEnabled = settingSoundEnabled.checked;
            const volumeVal = parseInt(settingVolume.value);
            const displayName = settingDisplayName.value.trim() || 'Học sinh';

            // Save locally
            localStorage.setItem('alertSoundEnabled', soundEnabled);
            localStorage.setItem('alertVolume', volumeVal);
            localStorage.setItem('studentDisplayName', displayName);

            // Send to backend
            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ear_threshold: earVal,
                        drowsy_threshold: drowsyVal,
                        distraction_threshold: distractVal,
                        display_name: displayName
                    })
                });
                const result = await res.json();
                
                if (result.status === 'success') {
                    // Update UI immediately
                    const reportNameEl = document.getElementById('report-student-name');
                    if (reportNameEl) reportNameEl.textContent = displayName;
                    
                    const welcomeHeader = document.querySelector('.welcome-msg h4');
                    if (welcomeHeader) {
                        welcomeHeader.innerHTML = `Chào mừng trở lại, ${displayName}! 👋`;
                    }

                    const topbarDisplayName = document.getElementById('topbar-display-name');
                    if (topbarDisplayName) topbarDisplayName.textContent = displayName;

                    const topbarAvatar = document.getElementById('topbar-avatar');
                    if (topbarAvatar) topbarAvatar.textContent = displayName.substring(0, 2).toUpperCase();
                    
                    showToastNotification("Cấu hình hệ thống đã được lưu thành công!", "success");
                } else {
                    showToastNotification("Gặp lỗi khi lưu cấu hình: " + result.message, "danger");
                }
            } catch (err) {
                console.error("Lỗi khi lưu cấu hình:", err);
                showToastNotification("Không thể kết nối đến máy chủ.", "danger");
            }
        });
    }

    if (btnResetSettings) {
        btnResetSettings.addEventListener('click', () => {
            if (settingEar) {
                settingEar.value = 0.22;
                valEar.textContent = '0.22';
            }
            if (settingDrowsy) {
                settingDrowsy.value = 1.5;
                valDrowsy.textContent = '1.5s';
            }
            if (settingDistraction) {
                settingDistraction.value = 2.0;
                valDistraction.textContent = '2.0s';
            }
            if (settingSoundEnabled) settingSoundEnabled.checked = true;
            if (settingVolume) settingVolume.value = 80;
            if (settingDisplayName) settingDisplayName.value = 'Học sinh';
        });
    }

    // --- Notification Dropdown Logic ---
    const btnNotificationBell = document.getElementById('btn-notification-bell');
    const notificationDropdown = document.getElementById('notification-dropdown');
    const btnClearNotifications = document.getElementById('btn-clear-notifications');

    function renderNotificationDropdown() {
        const notifList = document.getElementById('notification-list');
        if (!notifList) return;
        
        if (currentSessionAlerts.length === 0) {
            notifList.innerHTML = '<div class="text-center py-4 text-muted small">Không có thông báo mới</div>';
            return;
        }
        
        // Show last 5 alerts, newest first
        const recentAlerts = [...currentSessionAlerts].reverse().slice(0, 5);
        notifList.innerHTML = '';
        recentAlerts.forEach(item => {
            let iconClass = 'fa-solid fa-bell';
            let iconBg = 'bg-secondary text-white';
            if (item.type.includes('Ngủ') || item.type.includes('ngủ')) {
                iconClass = 'fa-solid fa-moon';
                iconBg = 'bg-danger text-white';
            } else if (item.type.includes('điện thoại') || item.type.includes('Dùng')) {
                iconClass = 'fa-solid fa-mobile-screen';
                iconBg = 'bg-danger text-white';
            } else if (item.type.includes('Ngoảnh') || item.type.includes('ngoảnh') || item.type.includes('mặt')) {
                iconClass = 'fa-solid fa-eye-slash';
                iconBg = 'bg-warning text-white';
            }
            
            const div = document.createElement('div');
            div.className = 'notification-item';
            div.innerHTML = `
                <div class="notif-icon ${iconBg}">
                    <i class="${iconClass}" style="font-size: 0.85rem;"></i>
                </div>
                <div class="notif-content">
                    <div class="fw-semibold text-primary" style="font-size: 0.8rem;">${item.type}</div>
                    <div class="text-muted" style="font-size: 0.75rem;">Trạng thái: ${item.status || 'Đã nhắc nhở'}</div>
                    <div class="notif-time">${item.time}</div>
                </div>
            `;
            notifList.appendChild(div);
        });
    }

    if (btnNotificationBell) {
        btnNotificationBell.addEventListener('click', (e) => {
            e.stopPropagation();
            if (notificationDropdown) {
                const isHidden = notificationDropdown.classList.contains('d-none');
                if (isHidden) {
                    // Open dropdown
                    notificationDropdown.classList.remove('d-none');
                    renderNotificationDropdown();
                    
                    // Mark as read
                    unreadAlertsCount = 0;
                    localStorage.setItem('unreadAlertsCount', '0');
                    if (notificationBadge) notificationBadge.style.display = 'none';
                } else {
                    // Close dropdown
                    notificationDropdown.classList.add('d-none');
                }
            }
        });
    }

    if (btnClearNotifications) {
        btnClearNotifications.addEventListener('click', (e) => {
            e.stopPropagation();
            currentSessionAlerts = [];
            localStorage.setItem('currentSessionAlerts', JSON.stringify([]));
            unreadAlertsCount = 0;
            localStorage.setItem('unreadAlertsCount', '0');
            if (notificationBadge) notificationBadge.style.display = 'none';
            renderNotificationDropdown();
            updateAlertsTable();
        });
    }

    // Close dropdown on click outside
    document.addEventListener('click', (e) => {
        if (notificationDropdown && btnNotificationBell) {
            if (!btnNotificationBell.contains(e.target) && !notificationDropdown.contains(e.target)) {
                notificationDropdown.classList.add('d-none');
            }
        }
    });

    // --- Shared display helpers (server sends null when nothing was measured) ---
    const STATE_LABELS_VI = {
        Focused: 'Tập trung', Sleepy: 'Buồn ngủ', Distracted: 'Quay đi chỗ khác', Phone: 'Dùng điện thoại',
        NotVisible: 'Tạm khuất', Away: 'Rời chỗ', Unknown: 'Chưa có dữ liệu'
    };
    const EVENT_LABELS_VI = { PHONE: 'Dùng điện thoại', DROWSY: 'Buồn ngủ', HEAD_AWAY: 'Quay đi chỗ khác', AWAY: 'Rời chỗ' };
    function fmtScore(v) { return (v === null || v === undefined) ? '—' : `${v}%`; }
    function scoreNum(v) { return (v === null || v === undefined) ? 0 : v; }
    function fmtClock(t) {
        if (t === null || t === undefined || t === '') return '—';
        if (typeof t === 'number') return new Date(t * 1000).toLocaleTimeString('vi-VN', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
        return String(t);
    }
    function escapeHtml(v) {
        return String(v === null || v === undefined ? '' : v).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
    }
    function selectedClassId() {
        const el = document.getElementById('select-class-monitor');
        return el && el.value ? parseInt(el.value) : (window.userClassId ? parseInt(window.userClassId) : null);
    }

    // --- Teacher & Admin Dashboards Implementation ---
    let teacherPollInterval;
    let selectedStudentName = null;
    let teacherMiniChart = null;
    let donutChartObj = null;
    let lineAvgChartObj = null;
    let classRootCauseChartObj = null;
    let cachedStudents = [];
    let activeView = '2d';
    let analyticsTrendChart = null;
    let analyticsTypesChart = null;
    // Map to store latest video snapshot per student name
    const studentFrames = new Map();

    function initTeacherDashboard() {
        const btnStartClass = document.getElementById('btn-start-class');
        const btnEndClass = document.getElementById('btn-end-class');
        const classTimerEl = document.getElementById('class-timer');
        const classSessionBadge = document.getElementById('class-session-badge');
        const btnCloseDetail = document.getElementById('btn-close-detail');
        const detailPanel = document.getElementById('student-detail-panel');

        const btnView2d = document.getElementById('btn-view-2d');
        const btnViewGrid = document.getElementById('btn-view-grid');
        const btnViewList = document.getElementById('btn-view-list');
        const btnView3d = document.getElementById('btn-view-3d');
        
        const grid2d = document.getElementById('student-2d-grid');
        const cardsGrid = document.getElementById('student-cards-grid');
        const listGrid = document.getElementById('student-list-grid');
        const twinGrid = document.getElementById('student-3d-grid');
        
        const btnExportReport = document.getElementById('btn-export-report');

        if (btnView2d) {
            btnView2d.addEventListener('click', () => {
                activeView = '2d';
                btnView2d.classList.add('active');
                if (btnViewGrid) btnViewGrid.classList.remove('active');
                if (btnViewList) btnViewList.classList.remove('active');
                if (btnView3d) btnView3d.classList.remove('active');
                
                if (grid2d) grid2d.classList.remove('d-none');
                if (cardsGrid) cardsGrid.classList.add('d-none');
                if (listGrid) listGrid.classList.add('d-none');
                if (twinGrid) twinGrid.classList.add('d-none');
                render2DClassroom(cachedStudents);
            });
        }

        if (btnViewGrid && btnViewList) {
            btnViewGrid.addEventListener('click', () => {
                activeView = 'grid';
                btnViewGrid.classList.add('active');
                if (btnView2d) btnView2d.classList.remove('active');
                if (btnViewList) btnViewList.classList.remove('active');
                if (btnView3d) btnView3d.classList.remove('active');
                
                if (grid2d) grid2d.classList.add('d-none');
                if (cardsGrid) cardsGrid.classList.remove('d-none');
                if (listGrid) listGrid.classList.add('d-none');
                if (twinGrid) twinGrid.classList.add('d-none');
                renderStudentCards(cachedStudents);
            });

            btnViewList.addEventListener('click', () => {
                activeView = 'list';
                btnViewList.classList.add('active');
                if (btnView2d) btnView2d.classList.remove('active');
                if (btnViewGrid) btnViewGrid.classList.remove('active');
                if (btnView3d) btnView3d.classList.remove('active');
                
                if (grid2d) grid2d.classList.add('d-none');
                if (cardsGrid) cardsGrid.classList.add('d-none');
                if (listGrid) listGrid.classList.remove('d-none');
                if (twinGrid) twinGrid.classList.add('d-none');
                renderStudentListRows(cachedStudents);
            });
            
            if (btnView3d) {
                btnView3d.addEventListener('click', () => {
                    activeView = '3d';
                    btnView3d.classList.add('active');
                    if (btnView2d) btnView2d.classList.remove('active');
                    if (btnViewGrid) btnViewGrid.classList.remove('active');
                    if (btnViewList) btnViewList.classList.remove('active');
                    
                    if (grid2d) grid2d.classList.add('d-none');
                    if (cardsGrid) cardsGrid.classList.add('d-none');
                    if (listGrid) listGrid.classList.add('d-none');
                    if (twinGrid) twinGrid.classList.remove('d-none');
                    render3DClassroom(cachedStudents);
                });
            }
        }
        
        // Class selection dropdown change listener
        const classSelect = document.getElementById('select-class-monitor');
        if (classSelect) {
            const savedClassId = localStorage.getItem('selectedClassId');
            if (savedClassId) {
                classSelect.value = savedClassId;
            }
            classSelect.addEventListener('change', () => {
                const classId = classSelect.value;
                localStorage.setItem('selectedClassId', classId);
                if (window.teacherSocketGlobal && window.teacherSocketGlobal.connected) {
                    window.teacherSocketGlobal.emit('request_class_snapshot', {});
                } else {
                    pollTeacherData();
                }
            });
        }

        if (btnExportReport) {
            btnExportReport.addEventListener('click', () => {
                if (cachedStudents.length === 0) {
                    showToastNotification('Không có dữ liệu học sinh để xuất báo cáo.', 'warning');
                    return;
                }
                
                // Determine delimiter based on user OS/platform
                const isMac = navigator.userAgent.toLowerCase().includes('mac');
                const delimiter = isMac ? ',' : ';';
                
                let csvContent = "\ufeff"; // BOM for Excel UTF-8
                csvContent += `sep=${delimiter}\n`; // Excel metadata directive
                csvContent += `Mã HS${delimiter}Học sinh${delimiter}Trạng thái${delimiter}Độ tập trung${delimiter}Số lần vi phạm\n`;
                
                cachedStudents.forEach(s => {
                    const statusText = s.online ? 'Trực tuyến' : 'Ngoại tuyến';
                    const attentionText = s.state === 'Focused' ? 'Tập trung' : (s.state === 'Sleepy' ? 'Buồn ngủ' : (s.state === 'Distracted' ? 'Mất tập trung' : (s.state === 'Phone' ? 'Dùng điện thoại' : 'Bình thường')));
                    csvContent += `"${s.roll || 'N/A'}"${delimiter}"${s.name}"${delimiter}"${statusText} (${attentionText})"${delimiter}${s.focus_score}${delimiter}${s.distractions || 0}\n`;
                });
                
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                link.download = `bao_cao_lop_hoc_${new Date().toISOString().slice(0,10)}.csv`;
                link.href = URL.createObjectURL(blob);
                link.click();
                showToastNotification('Xuất báo cáo lớp học thành công (CSV)!', 'success');
            });
        }

        // Close details panel
        if (btnCloseDetail) {
            btnCloseDetail.addEventListener('click', () => {
                if (detailPanel) detailPanel.style.display = 'none';
                selectedStudentName = null;
            });
        }

        // Toggle start/end class session
        if (btnStartClass) {
            btnStartClass.addEventListener('click', async () => {
                const res = await fetch('/api/teacher/start_class', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ class_id: selectedClassId() }) });
                const data = await res.json();
                if (data.status === 'success') {
                    btnStartClass.style.display = 'none';
                    if (btnEndClass) btnEndClass.style.display = 'block';
                    if (classSessionBadge) {
                        classSessionBadge.className = 'badge bg-success-subtle text-success border border-success';
                        classSessionBadge.textContent = 'Đang diễn ra';
                    }
                    pollTeacherData();
                }
            });
        }

        if (btnEndClass) {
            btnEndClass.addEventListener('click', async () => {
                const res = await fetch('/api/teacher/end_class', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ class_id: selectedClassId() }) });
                const data = await res.json();
                if (data.status === 'success') {
                    btnEndClass.style.display = 'none';
                    if (btnStartClass) btnStartClass.style.display = 'block';
                    if (classSessionBadge) {
                        classSessionBadge.className = 'badge bg-danger-subtle text-danger border border-danger';
                        classSessionBadge.textContent = 'Đã kết thúc';
                    }
                    if (classTimerEl) classTimerEl.textContent = '00:00:00';
                    
                    // Fetch and show AI Class Summary modal
                    try {
                        const summaryRes = await fetch(`/api/teacher/class_summary?class_id=${selectedClassId()}`);
                        const summaryData = await summaryRes.json();
                        if (summaryData.status === 'success' || summaryData.status === 'insufficient_data') {
                            const avgEl = document.getElementById('summary-avg-score');
                            const dangerEl = document.getElementById('summary-danger-hour');
                            const textEl = document.getElementById('summary-text-content');
                            
                            if (avgEl) avgEl.textContent = summaryData.average_score === null || summaryData.average_score === undefined ? 'N/A' : `${summaryData.average_score}/100`;
                            if (dangerEl) dangerEl.textContent = summaryData.danger_hour || 'Chưa có';
                            if (textEl) textEl.textContent = summaryData.summary_text;
                            
                            if (typeof bootstrap !== 'undefined') {
                                const modal = new bootstrap.Modal(document.getElementById('classSummaryModal'));
                                modal.show();
                            }
                        }
                    } catch (e) {
                        console.error("Lỗi tải tóm tắt lớp học:", e);
                    }
                }
            });
        }

        // Setup Chart.js Charts
        initTeacherCharts();

        const searchInput = document.getElementById('search-students');
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                renderTeacherStudentsTable();
            });
        }
        
        // Handle view_student query parameter to automatically show details
        const urlParams = new URLSearchParams(window.location.search);
        const viewStudentName = urlParams.get('view_student');
        if (viewStudentName) {
            selectedStudentName = viewStudentName;
        }

        // ==============================================================
        // OFFLINE CLASSROOM MODE LOGIC
        // ==============================================================
        let offlinePollInterval = null;
        let isOfflineSessionActive = false;
        
        const modeSelectOnline = document.getElementById('mode-select-online');
        const modeSelectOffline = document.getElementById('mode-select-offline');
        
        if (modeSelectOnline && modeSelectOffline) {
            modeSelectOnline.addEventListener('change', toggleClassroomMode);
            modeSelectOffline.addEventListener('change', toggleClassroomMode);
        }
        
        function toggleClassroomMode() {
            const isOffline = modeSelectOffline && modeSelectOffline.checked;
            
            const onlineElements = document.querySelectorAll('.class-mode-online');
            const offlineElements = document.querySelectorAll('.class-mode-offline');
            
            if (isOffline) {
                // Switch to Offline
                onlineElements.forEach(el => el.classList.add('d-none'));
                offlineElements.forEach(el => el.classList.remove('d-none'));
                
                // Stop online polling
                if (teacherPollInterval) {
                    clearInterval(teacherPollInterval);
                    teacherPollInterval = null;
                }
                
                // Start offline polling
                pollOfflineClassroomData();
                if (!offlinePollInterval) {
                    offlinePollInterval = setInterval(pollOfflineClassroomData, 3000);
                }
            } else {
                // Switch to Online
                offlineElements.forEach(el => el.classList.add('d-none'));
                onlineElements.forEach(el => el.classList.remove('d-none'));
                
                // Stop offline polling
                if (offlinePollInterval) {
                    clearInterval(offlinePollInterval);
                    offlinePollInterval = null;
                }
                
                // Resume online polling
                if (!teacherPollInterval) {
                    pollTeacherData();
                    teacherPollInterval = setInterval(pollTeacherData, 3000);
                }
            }
        }
        
        // Perspective Seat Coordinate Mapper
        function getPerspectiveSeatCoords(row, col) {
            // row 0 is front row, row 6 is back row
            // Let's map row to Y ratio: row=6 (back) -> y=0.22, row=0 (front) -> y=0.76
            const yRatio = 0.22 + (6 - row) * 0.09; 
            
            // X position: col 0 to 3
            // For perspective, width of the rows increases as they get closer to front (bottom)
            const rowWidth = 0.52 + (6 - row) * 0.05; // width ratio from 0.52 to 0.82
            const leftPadding = (1 - rowWidth) / 2;
            const xRatio = leftPadding + (col / 3) * rowWidth;
            
            // Box size based on row (smaller in the back, larger in the front)
            const boxWidth = 6.5 + (6 - row) * 1.6; // percent width
            const boxHeight = 5.0 + (6 - row) * 1.2; // percent height
            
            return {
                top: yRatio * 100,
                left: (xRatio * 100) - (boxWidth / 2),
                width: boxWidth,
                height: boxHeight
            };
        }
        
        // Poll Offline data
        async function pollOfflineClassroomData() {
            try {
                const classSelect = document.getElementById('select-class-monitor');
                const classId = classSelect ? classSelect.value : 1;
                const res = await fetch(`/api/teacher/offline_classroom_status?class_id=${classId}`);
                const data = await res.json();
                
                if (data.status === 'success') {
                    isOfflineSessionActive = data.offline_class_active;
                    
                    // Sync controls UI
                    const btnStartOffline = document.getElementById('btn-start-offline-class');
                    const btnEndOffline = document.getElementById('btn-end-offline-class');
                    const offlineBadge = document.getElementById('offline-class-session-badge');
                    const cameraInactiveOverlay = document.getElementById('offline-camera-inactive-overlay');
                    const videoFeedImg = document.getElementById('offline-classroom-video');
                    
                    if (isOfflineSessionActive) {
                        if (btnStartOffline) btnStartOffline.style.display = 'none';
                        if (btnEndOffline) btnEndOffline.style.display = 'block';
                        if (offlineBadge) {
                            offlineBadge.className = 'badge bg-success-subtle text-success border border-success';
                            offlineBadge.textContent = 'Đang giám sát';
                        }
                        if (cameraInactiveOverlay) cameraInactiveOverlay.style.display = 'none';
                        
                        // Set the video stream src if not set already
                        if (videoFeedImg && (!videoFeedImg.src || videoFeedImg.src.indexOf('/video_feed') === -1)) {
                            videoFeedImg.src = `/video_feed?mode=classroom&class_id=${selectedClassId()}`;
                        }
                    } else {
                        if (btnStartOffline) btnStartOffline.style.display = 'block';
                        if (btnEndOffline) btnEndOffline.style.display = 'none';
                        if (offlineBadge) {
                            offlineBadge.className = 'badge bg-danger-subtle text-danger border border-danger';
                            offlineBadge.textContent = 'Chưa bắt đầu';
                        }
                        if (cameraInactiveOverlay) cameraInactiveOverlay.style.display = 'flex';
                        if (videoFeedImg) videoFeedImg.src = '';
                    }
                    
                    // Update stats
                    const statPresent = document.getElementById('offline-stat-present');
                    const statDistracted = document.getElementById('offline-stat-distracted');
                    const statDrowsy = document.getElementById('offline-stat-drowsy');
                    const statFocus = document.getElementById('offline-stat-focus');
                    
                    if (statPresent) statPresent.textContent = `${data.statistics.present}/${data.statistics.enrolled}`;
                    if (statDistracted) statDistracted.textContent = data.statistics.distracted;
                    if (statDrowsy) statDrowsy.textContent = data.statistics.drowsy;
                    if (statFocus) {
                        statFocus.textContent = fmtScore(data.statistics.focus_score);
                        if (data.statistics.focus_score === null) statFocus.className = 'text-muted fw-bold fs-5';
                        else if (data.statistics.focus_score >= 80) statFocus.className = 'text-success fw-bold fs-5';
                        else if (data.statistics.focus_score >= 60) statFocus.className = 'text-warning fw-bold fs-5';
                        else statFocus.className = 'text-danger fw-bold fs-5';
                    }
                    
                    // Render AI analyses
                    const analysisContainer = document.getElementById('offline-ai-analysis-container');
                    if (analysisContainer) {
                        if (data.analyses.length === 0) {
                            analysisContainer.innerHTML = '<p class="text-muted mb-0">Chờ dữ liệu phân tích lớp học...</p>';
                        } else {
                            let html = '';
                            data.analyses.forEach(val => {
                                html += `
                                    <div class="d-flex align-items-start mb-2">
                                        <i class="fa-solid fa-circle-info text-info me-2 mt-1"></i>
                                        <span>${val}</span>
                                    </div>
                                `;
                            });
                            analysisContainer.innerHTML = html;
                        }
                    }
                    
                    // Render Suggestions
                    const suggestionsContainer = document.getElementById('offline-suggestions-container');
                    if (suggestionsContainer) {
                        if (data.suggestions.length === 0) {
                            suggestionsContainer.innerHTML = '<p class="text-muted mb-0">Không có gợi ý tự động.</p>';
                        } else {
                            let html = '';
                            data.suggestions.forEach(val => {
                                html += `
                                    <div class="d-flex align-items-start mb-2">
                                        <i class="fa-solid fa-lightbulb text-warning me-2 mt-1"></i>
                                        <span>${val}</span>
                                    </div>
                                `;
                            });
                            suggestionsContainer.innerHTML = html;
                        }
                    }
                    
                    // Render logs
                    const logList = document.getElementById('offline-activity-log-list');
                    if (logList) {
                        if (data.logs.length === 0) {
                            logList.innerHTML = '<p class="text-muted text-center small py-3">Nhật ký hoạt động trống</p>';
                        } else {
                            let html = '';
                            data.logs.slice().reverse().forEach(log => {
                                html += `
                                    <div class="activity-log-item mb-2" style="border-left: 4px solid ${log.type === 'warning' ? 'var(--warning-color)' : (log.type === 'danger' ? 'var(--danger-color)' : 'var(--primary-color)')}; padding: 8px 10px; border-radius: 6px; background: rgba(255,255,255,0.02); font-size: 0.78rem;">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <span class="text-white-50 small">${fmtClock(log.time)}</span>
                                        </div>
                                        <div class="text-white font-semibold mt-1">${escapeHtml(log.message)}</div>
                                    </div>
                                `;
                            });
                            logList.innerHTML = html;
                        }
                    }
                    
                    // Update Seating Twin Grid & Camera overlays
                    renderOfflineTwinAndOverlays(data.students);
                    
                    // Update timer
                    updateOfflineClassTimer(data.offline_class_active, data.elapsed_seconds);
                }
            } catch (err) {
                console.error("Error polling offline class status:", err);
            }
        }
        
        // Render physical grid & bounding boxes
        function renderOfflineTwinAndOverlays(students) {
            const twinGrid = document.getElementById('offline-classroom-twin-grid');
            const boundingBoxContainer = document.getElementById('offline-bounding-boxes');
            
            if (twinGrid) twinGrid.innerHTML = '';
            if (boundingBoxContainer) boundingBoxContainer.innerHTML = '';
            
            // Sort students by seat row & col
            const sorted = [...students].sort((a, b) => {
                if (a.seat_row !== b.seat_row) return a.seat_row - b.seat_row;
                return a.seat_col - b.seat_col;
            });
            
            sorted.forEach(s => {
                const row = s.seat_row === null || s.seat_row === undefined ? 0 : s.seat_row;
                const col = s.seat_col === null || s.seat_col === undefined ? 0 : s.seat_col;
                const isOnline = s.online === true;
                
                // Color mapping based on student state
                let color = 'var(--success-color)';
                let colorRgb = '16, 185, 129';
                let emoji = '🟢';
                let stateText = 'Tập trung';
                
                if (!isOnline) {
                    color = '#9ca3af';
                    colorRgb = '156, 163, 175';
                    emoji = '⚪';
                    stateText = (s.labels && s.labels.visibility) || 'Chưa thấy';
                } else if (s.state === 'Sleepy') {
                    color = 'var(--warning-color)';
                    colorRgb = '245, 158, 11';
                    emoji = '😴';
                    stateText = 'Buồn ngủ';
                } else if (s.state === 'Distracted') {
                    color = '#fbbf24';
                    colorRgb = '251, 191, 36';
                    emoji = '🟡';
                    stateText = 'Phân tâm';
                } else if (s.state === 'Phone') {
                    color = 'var(--danger-color)';
                    colorRgb = '239, 68, 68';
                    emoji = '🔴';
                    stateText = 'Dùng điện thoại';
                }
                
                // 1. Draw Seating Grid Item
                if (twinGrid) {
                    const desk = document.createElement('div');
                    desk.className = 'p-2 text-center';
                    desk.style.background = `rgba(${colorRgb}, 0.08)`;
                    desk.style.border = `2px solid rgba(${colorRgb}, ${isOnline ? '0.3' : '0.15'})`;
                    desk.style.borderRadius = '8px';
                    desk.style.cursor = 'pointer';
                    desk.style.fontSize = '0.75rem';
                    desk.style.transition = 'all 0.2s';
                    desk.title = `${s.name} - Trạng thái: ${stateText}`;
                    
                    desk.innerHTML = `
                        <div class="fw-bold text-truncate" style="max-width: 70px; color: ${isOnline ? 'var(--text-primary)' : '#9ca3af'};">${s.name.split(' ').pop()}</div>
                        <div class="fs-6 mt-1">${emoji}</div>
                        <div class="mt-1" style="font-size: 0.62rem; color: var(--text-secondary); font-weight: 600;">R${row+1}-C${col+1}</div>
                    `;
                    
                    desk.addEventListener('mouseenter', () => {
                        desk.style.transform = 'translateY(-2px)';
                        desk.style.borderColor = color;
                        desk.style.boxShadow = `0 4px 10px rgba(${colorRgb}, 0.2)`;
                    });
                    desk.addEventListener('mouseleave', () => {
                        desk.style.transform = 'none';
                        desk.style.borderColor = `rgba(${colorRgb}, ${isOnline ? '0.25' : '0.15'})`;
                        desk.style.boxShadow = 'none';
                    });
                    
                    desk.addEventListener('click', () => {
                        showStudentDetail(s.name);
                    });
                    
                    twinGrid.appendChild(desk);
                }
                
                // 2. Draw Camera Bounding Box (Only if session is active AND student is online/present)
                if (boundingBoxContainer && isOfflineSessionActive && isOnline) {
                    const coords = getPerspectiveSeatCoords(row, col);
                    const box = document.createElement('div');
                    box.style.position = 'absolute';
                    box.style.border = `2px solid ${color}`;
                    box.style.borderRadius = '6px';
                    box.style.top = `${coords.top}%`;
                    box.style.left = `${coords.left}%`;
                    box.style.width = `${coords.width}%`;
                    box.style.height = `${coords.height}%`;
                    box.style.background = `rgba(${colorRgb}, 0.12)`;
                    box.style.boxShadow = `inset 0 0 8px rgba(${colorRgb}, 0.2)`;
                    box.style.transition = 'all 0.3s ease';
                    box.style.cursor = 'pointer';
                    
                    box.innerHTML = `
                        <span style="position: absolute; top: -16px; left: -2px; font-size: 0.6rem; background: ${color}; color: white; padding: 1px 4px; border-radius: 3px; white-space: nowrap; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
                            ${s.name.split(' ').pop()} ${emoji}
                        </span>
                    `;
                    
                    box.addEventListener('click', () => {
                        showStudentDetail(s.name);
                    });
                    
                    boundingBoxContainer.appendChild(box);
                }
            });
        }
        
        // Update timer
        function updateOfflineClassTimer(isActive, seconds) {
            const timerEl = document.getElementById('offline-class-timer');
            if (!timerEl) return;
            
            if (!isActive) {
                timerEl.textContent = '00:00:00';
                return;
            }
            
            const hrs = String(Math.floor(seconds / 3600)).padStart(2, '0');
            const mins = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
            const secs = String(seconds % 60).padStart(2, '0');
            timerEl.textContent = `${hrs}:${mins}:${secs}`;
        }
        
        // Bind offline control buttons
        const btnStartOffline = document.getElementById('btn-start-offline-class');
        if (btnStartOffline) {
            btnStartOffline.addEventListener('click', async () => {
                const res = await fetch('/api/teacher/start_offline_class', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ class_id: selectedClassId() }) });
                const data = await res.json();
                if (data.status === 'success') {
                    showToastNotification('Đã bắt đầu giám sát camera lớp học trực tiếp!', 'success');
                    pollOfflineClassroomData();
                }
            });
        }
        
        const btnEndOffline = document.getElementById('btn-end-offline-class');
        if (btnEndOffline) {
            btnEndOffline.addEventListener('click', async () => {
                const res = await fetch('/api/teacher/end_offline_class', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ class_id: selectedClassId() }) });
                const data = await res.json();
                if (data.status === 'success') {
                    showToastNotification('Đã dừng giám sát camera lớp học trực tiếp.', 'info');
                    pollOfflineClassroomData();
                }
            });
        }

        // === WebSocket: connect and join teacher room ===
        const wsIndicator = document.getElementById('ws-connection-indicator');
        if (typeof io !== 'undefined') {
            const teacherSocket = io();
            window.teacherSocketGlobal = teacherSocket;

            teacherSocket.on('connect', () => {
                console.log('[WS] Teacher connected:', teacherSocket.id);
                if (wsIndicator) {
                    wsIndicator.className = 'badge bg-success ms-2';
                    wsIndicator.textContent = '⚡ Trực tiếp';
                }
                teacherSocket.emit('join_teacher_room', {});
                teacherSocket.emit('request_class_snapshot', {});
            });

            teacherSocket.on('disconnect', () => {
                console.warn('[WS] Teacher disconnected – falling back to poll');
                if (wsIndicator) {
                    wsIndicator.className = 'badge bg-warning text-dark ms-2';
                    wsIndicator.textContent = '⚠ Đang kết nối lại...';
                }
                if (!teacherPollInterval) {
                    teacherPollInterval = setInterval(pollTeacherData, 3000);
                }
            });

            teacherSocket.on('joined', (data) => {
                console.log('[WS]', data.message);
                if (teacherPollInterval) {
                    clearInterval(teacherPollInterval);
                    teacherPollInterval = null;
                }
            });

            teacherSocket.on('class_snapshot', (data) => {
                const classSelect = document.getElementById('select-class-monitor');
                const classId = classSelect ? parseInt(classSelect.value) : 1;
                const filteredStudents = data.students.filter(s => s.class_id === classId);
                cachedStudents = filteredStudents;
                
                if (activeView === '2d') {
                    render2DClassroom(filteredStudents);
                } else if (activeView === 'grid') {
                    renderStudentCards(filteredStudents);
                } else if (activeView === 'list') {
                    renderStudentListRows(filteredStudents);
                } else if (activeView === '3d') {
                    render3DClassroom(filteredStudents);
                }
                renderTeacherStudentsTable();
                updateTeacherCharts(filteredStudents);
                updateClassTimer(data.class_session_active, data.elapsed_seconds);
                if (data.logs) renderTeacherAlertsTable(data.logs);
                if (data.logs) renderActivityLogs(data.logs);
                syncClassSessionUI(data.class_session_active);
                renderAttendanceTable(data.students);
                checkInterventions(filteredStudents);
                
                // Real-time classroom stats updates
                updateClassroomStatistics(filteredStudents, data.logs);
            });

            teacherSocket.on('student_update', (student) => {
                console.log('[WS] student_update:', student.name, student.state, student.focus_score);
                const classSelect = document.getElementById('select-class-monitor');
                const classId = classSelect ? parseInt(classSelect.value) : 1;
                
                const idx = cachedStudents.findIndex(s => s.name === student.name);
                if (idx >= 0) {
                    cachedStudents[idx] = { ...cachedStudents[idx], ...student };
                } else {
                    cachedStudents.push(student);
                }
                
                const filtered = cachedStudents.filter(s => s.class_id === classId);
                
                if (activeView === '2d') {
                    render2DClassroom(filtered);
                } else if (activeView === 'grid') {
                    updateSingleStudentCard(student);
                } else if (activeView === 'list') {
                    renderStudentListRows(filtered);
                } else if (activeView === '3d') {
                    render3DClassroom(filtered);
                }
                renderTeacherStudentsTable();
                updateTeacherCharts(filtered);
                flashStudentCard(student.name);
                checkInterventions(filtered);
                
                // Real-time classroom stats updates
                updateClassroomStatistics(filtered, null);
            });

            // ⚡ REALTIME: Student came online notification
            teacherSocket.on('student_came_online', (data) => {
                console.log('[WS] Student online:', data.name);
                showToastNotification(`🟢 ${data.name} vừa kết nối vào lớp!`, 'success');
                // Re-request snapshot to get updated online count
                teacherSocket.emit('request_class_snapshot', {});
            });

            // ⚡ REALTIME: Student video frame pushed from student browser
            teacherSocket.on('student_frame', (data) => {
                // Store snapshot
                studentFrames.set(data.name, data.frame);
                // Update the image in the card directly without re-rendering
                const grid = document.getElementById('student-cards-grid');
                if (!grid) return;
                const allCards = grid.querySelectorAll('.student-card');
                allCards.forEach(card => {
                    const nameEl = card.querySelector('h6');
                    if (nameEl && nameEl.textContent.trim() === data.name) {
                        const img = card.querySelector('img.student-snapshot');
                        const placeholder = card.querySelector('.student-thumb-placeholder');
                        if (img) {
                            img.src = data.frame;
                            img.style.display = 'block';
                            if (placeholder) placeholder.style.display = 'none';
                        }
                    }
                });
                // Also update detail panel if this student is selected
                if (selectedStudentName === data.name) {
                    const detailSnapshot = document.getElementById('detail-student-snapshot');
                    if (detailSnapshot) detailSnapshot.src = data.frame;
                }
            });

            // ⚡ REALTIME: Logs update pushed
            teacherSocket.on('log_update', (log) => {
                renderActivityLogs([log]);
            });

        } else {
            // socket.io not available – fallback to polling
            console.warn('[WS] socket.io not loaded, using HTTP polling');
            pollTeacherData();
            teacherPollInterval = setInterval(pollTeacherData, 3000);
        }

        // --- Teacher Settings Form Submit Handler ---
        const teacherSettingsForm = document.getElementById('teacher-settings-form');
        if (teacherSettingsForm) {
            // Load sound, notification, and auto-record settings from localStorage if they exist
            const soundEnabled = localStorage.getItem('teacherSoundEnabled') !== 'false';
            const notificationEnabled = localStorage.getItem('teacherNotificationEnabled') !== 'false';
            const autoRecordEnabled = localStorage.getItem('teacherAutoRecordEnabled') !== 'false';
            
            const soundSwitch = document.getElementById('teacher-setting-sound');
            const notifSwitch = document.getElementById('teacher-setting-notification');
            const recordSwitch = document.getElementById('teacher-setting-auto-record');
            
            if (soundSwitch) soundSwitch.checked = soundEnabled;
            if (notifSwitch) notifSwitch.checked = notificationEnabled;
            if (recordSwitch) recordSwitch.checked = autoRecordEnabled;
            
            teacherSettingsForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const displayNameInput = document.getElementById('teacher-display-name');
                const minFocusInput = document.getElementById('teacher-min-focus');
                
                const displayName = displayNameInput ? displayNameInput.value.trim() : '';
                const minFocus = minFocusInput ? parseInt(minFocusInput.value) : 65;
                
                if (!displayName) {
                    showToastNotification('Tên giáo viên không được để trống.', 'warning');
                    return;
                }
                
                try {
                    const response = await fetch('/api/teacher/settings', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            display_name: displayName,
                            min_focus_threshold: minFocus
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (result.status === 'success') {
                        // Save local storage switches
                        if (soundSwitch) localStorage.setItem('teacherSoundEnabled', soundSwitch.checked);
                        if (notifSwitch) localStorage.setItem('teacherNotificationEnabled', notifSwitch.checked);
                        if (recordSwitch) localStorage.setItem('teacherAutoRecordEnabled', recordSwitch.checked);
                        
                        // Dynamically update display name on the sidebar and topbar
                        const sidebarUser = document.getElementById('sidebar-username');
                        const topbarUser = document.getElementById('topbar-display-name');
                        const sidebarAvatar = document.getElementById('sidebar-avatar');
                        
                        if (sidebarUser) sidebarUser.textContent = displayName;
                        if (topbarUser) topbarUser.textContent = displayName;
                        if (sidebarAvatar) {
                            sidebarAvatar.textContent = displayName.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
                        }
                        
                        showToastNotification(result.message, 'success');
                    } else {
                        showToastNotification(result.message, 'danger');
                    }
                } catch (err) {
                    console.error("Lỗi cập nhật cấu hình giáo viên:", err);
                    showToastNotification('Không thể lưu cấu hình giáo viên.', 'danger');
                }
            });
        }
    }

    // AI Classroom Twin: Generate AI summary/evaluation for student
    function generateAISummary(student) {
        // Factual summary from server-recorded data only (no emotion, no invented risk).
        const labels = student.labels || {};
        const ev = student.event_counts || {};
        const parts = [];
        parts.push(`Điểm danh: <strong>${escapeHtml(labels.attendance || '—')}</strong>; khung hình: <strong>${escapeHtml(labels.visibility || '—')}</strong>.`);
        parts.push(`Điểm tập trung hiện tại: <strong>${fmtScore(student.focus_score)}</strong>, trung bình buổi: <strong>${fmtScore(student.average_focus_score)}</strong>.`);
        const evParts = Object.keys(EVENT_LABELS_VI).filter(k => ev[k]).map(k => `${EVENT_LABELS_VI[k]}: ${ev[k]}`);
        parts.push(evParts.length ? `Sự kiện kéo dài: ${evParts.join(', ')}.` : 'Chưa ghi nhận sự kiện hành vi kéo dài.');
        if (student.away_count) parts.push(`Rời chỗ ${student.away_count} lần, tổng ${Math.round((student.away_seconds || 0) / 60)} phút.`);
        return parts.join('<br>');
    }

    // Classroom stats updater
    function updateClassroomStatistics(students, logs) {
        const avgFocusEl = document.getElementById('class-avg-focus');
        const activeCountEl = document.getElementById('class-active-count');
        const alertCountEl = document.getElementById('class-alert-count');
        const riskCountEl = document.getElementById('class-risk-count');
        if (!students) return;

        const measured = students.filter(s => s.focus_score !== null && s.focus_score !== undefined && s.visibility_status === 'VISIBLE');
        if (avgFocusEl) {
            avgFocusEl.textContent = measured.length
                ? `${Math.round(measured.reduce((sum, s) => sum + s.focus_score, 0) / measured.length)}%`
                : 'N/A';
        }
        const present = students.filter(s => s.attendance_status === 'PRESENT' || s.attendance_status === 'LATE');
        if (activeCountEl) activeCountEl.textContent = `${present.length}/${students.length}`;
        const totalEvents = students.reduce((sum, s) => sum + (s.distractions || 0), 0);
        if (alertCountEl) alertCountEl.textContent = totalEvents;
        const withBehaviour = students.filter(s => (s.active_behaviors || []).length > 0);
        if (riskCountEl) riskCountEl.textContent = withBehaviour.length;
    }

    // 2D classroom seating twin layout renderer
    function render2DClassroom(students) {
        const grid = document.getElementById('classroom-seating-grid');
        if (!grid) return;
        
        grid.innerHTML = '';
        
        const sortedStudents = [...students].sort((a, b) => {
            const rollA = parseInt(a.roll) || 0;
            const rollB = parseInt(b.roll) || 0;
            if (rollA !== rollB) return rollA - rollB;
            return a.name.localeCompare(b.name);
        });
        
        sortedStudents.forEach(s => {
            const desk = document.createElement('div');
            
            let statusIndicator = '🔵'; 
            let statusLabel = 'Ngoại tuyến';
            let statusColor = '#64748b'; 
            let statusBg = 'rgba(100, 116, 139, 0.08)';
            let statusBorder = 'rgba(100, 116, 139, 0.2)';
            
            if (s.online) {
                if (s.state === 'Focused') {
                    statusIndicator = '🟢';
                    statusLabel = 'Tập trung';
                    statusColor = '#10b981'; 
                    statusBg = 'rgba(16, 185, 129, 0.08)';
                    statusBorder = 'rgba(16, 185, 129, 0.25)';
                } else if (s.state === 'Sleepy') {
                    statusIndicator = '😴';
                    statusLabel = 'Buồn ngủ';
                    statusColor = '#f59e0b'; 
                    statusBg = 'rgba(245, 158, 11, 0.08)';
                    statusBorder = 'rgba(245, 158, 11, 0.25)';
                } else if (s.state === 'Distracted') {
                    statusIndicator = '🟡';
                    statusLabel = 'Mất tập trung';
                    statusColor = '#fbbf24'; 
                    statusBg = 'rgba(251, 191, 36, 0.08)';
                    statusBorder = 'rgba(251, 191, 36, 0.25)';
                } else if (s.state === 'Phone') {
                    statusIndicator = '🔴';
                    statusLabel = 'Dùng điện thoại';
                    statusColor = '#ef4444'; 
                    statusBg = 'rgba(239, 68, 68, 0.08)';
                    statusBorder = 'rgba(239, 68, 68, 0.25)';
                } else {
                    statusIndicator = '⚪';
                    statusLabel = STATE_LABELS_VI[s.state] || 'Chưa có dữ liệu';
                    statusColor = '#94a3b8';
                    statusBg = 'rgba(148, 163, 184, 0.08)';
                    statusBorder = 'rgba(148, 163, 184, 0.25)';
                }
            }
            
            desk.className = 'student-desk-card p-3 d-flex flex-column justify-content-between';
            desk.style.background = statusBg;
            desk.style.border = `1px solid ${statusBorder}`;
            desk.style.borderRadius = '12px';
            desk.style.minHeight = '130px';
            desk.style.cursor = 'pointer';
            desk.style.transition = 'all 0.2s ease-in-out';
            desk.style.position = 'relative';
            
            desk.addEventListener('mouseenter', () => {
                desk.style.transform = 'translateY(-3px)';
                desk.style.boxShadow = `0 6px 15px rgba(0, 0, 0, 0.25), 0 0 8px ${statusColor}33`;
                desk.style.borderColor = statusColor;
            });
            
            desk.addEventListener('mouseleave', () => {
                desk.style.transform = 'none';
                desk.style.boxShadow = 'none';
                desk.style.borderColor = statusBorder;
            });
            
            const initials = s.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
            const visLabel = (s.labels && s.labels.visibility) || '—';
            const focusScore = fmtScore(s.focus_score);
            const onlineText = (s.labels && s.labels.attendance) || (s.online ? 'Trực tuyến' : 'Ngoại tuyến');
            const onlineClass = s.online ? 'text-success' : 'text-muted';
            
            desk.innerHTML = `
                <div class="d-flex justify-content-between align-items-center w-100 mb-2">
                    <span style="font-size: 1.1rem;" title="${statusLabel}">${statusIndicator}</span>
                    <span class="small ${onlineClass}" style="font-size: 0.7rem; font-weight: 600;">${onlineText}</span>
                </div>
                
                <div class="text-center mb-2">
                    <div class="fw-bold text-white text-truncate" style="font-size: 0.9rem; max-width: 140px;" title="${s.name}">${s.name}</div>
                    <div class="text-muted" style="font-size: 0.7rem;">Mã HS: ${s.roll || 'N/A'}</div>
                </div>
                
                <div class="w-100 d-flex justify-content-between align-items-center mt-2 pt-2" style="border-top: 1px solid rgba(255, 255, 255, 0.06) !important;">
                    <div class="d-flex flex-column align-items-start">
                        <span class="text-muted" style="font-size: 0.6rem; opacity: 0.7;">Độ tập trung</span>
                        <span class="fw-bold" style="color: ${statusColor}; font-size: 0.85rem;">${focusScore}</span>
                    </div>
                    <div class="d-flex flex-column align-items-end">
                        <span class="text-muted" style="font-size: 0.6rem; opacity: 0.7;">Khung hình</span>
                        <span class="text-white-50" style="font-size: 0.8rem;">${escapeHtml(visLabel)}</span>
                    </div>
                </div>
            `;
            
            desk.addEventListener('click', () => {
                showStudentDetail(s.name);
            });
            
            grid.appendChild(desk);
        });
    }

        // 3D classroom desk renderer
        function render3DClassroom(students) {
            const floor = document.getElementById('classroom-floor-grid');
            if (!floor) return;
            
            floor.innerHTML = '';
            students.forEach(s => {
                const desk = document.createElement('div');
                const cleanState = s.state ? s.state.toLowerCase() : 'focused';
                
                desk.className = `desk-3d state-${cleanState} ${s.online ? '' : 'offline'}`;
                desk.setAttribute('data-name', s.name);
                
                // initials
                const initials = s.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
                
                desk.innerHTML = `
                    <div class="score-badge-3d">${fmtScore(s.focus_score)}</div>
                    <div class="student-avatar-3d">${initials}</div>
                    <div class="student-name-3d">${s.name}</div>
                `;
                
                desk.addEventListener('click', () => {
                    showStudentDetail(s.name);
                });
                
                floor.appendChild(desk);
            });
        }

        // Attendance list renderer
        function renderAttendanceTable(students) {
            const tbody = document.getElementById('attendance-table-body');
            if (!tbody) return;
            tbody.innerHTML = '';
            const classId = selectedClassId();
            const filtered = students.filter(s => s.class_id === classId);
            if (filtered.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Không có học sinh trong lớp này</td></tr>';
                return;
            }
            const badges = {
                PRESENT: '<span class="badge bg-success-subtle text-success border border-success">Có mặt</span>',
                LATE: '<span class="badge bg-warning-subtle text-warning border border-warning">Đi muộn</span>',
                ABSENT: '<span class="badge bg-danger-subtle text-danger border border-danger">Vắng mặt</span>',
                NOT_YET: '<span class="badge bg-secondary-subtle text-secondary border border-secondary">Chưa điểm danh</span>'
            };
            filtered.forEach(s => {
                const seen = s.attendance_status === 'PRESENT' || s.attendance_status === 'LATE';
                const method = !seen ? '—' : (s.identity_confidence !== null && s.identity_confidence !== undefined
                    ? `Khuôn mặt (độ tương đồng ${s.identity_confidence})` : 'Tài khoản đăng nhập + camera cá nhân');
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><b>${escapeHtml(s.roll || 'N/A')}</b></td>
                    <td>${escapeHtml(s.name)}</td>
                    <td>${badges[s.attendance_status] || badges.NOT_YET}</td>
                    <td>${seen ? fmtClock(s.checkin_at) : '—'}</td>
                    <td><small class="text-muted">${escapeHtml(method)}</small></td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Classroom intervention checks
        function checkInterventions(students) {
            const banner = document.getElementById('banner-ai-intervention');
            const textEl = document.getElementById('intervention-text');
            if (!banner || !textEl) return;
            const measured = students.filter(s => s.focus_score !== null && s.focus_score !== undefined && s.visibility_status === 'VISIBLE');
            if (measured.length === 0) { banner.style.display = 'none'; return; }
            const avg = measured.reduce((acc, s) => acc + s.focus_score, 0) / measured.length;
            if (avg < 75) {
                banner.style.display = 'block';
                textEl.innerHTML = `Điểm tập trung trung bình của ${measured.length} học sinh đang được đo là <b>${Math.round(avg)}%</b> (dưới 75%).`;
            } else {
                banner.style.display = 'none';
            }
        }

        // Voice Assistant Setup
        const btnVoice = document.getElementById('btn-voice-assistant');
        const voiceCard = document.getElementById('voice-assistant-card');
        const voicePrompt = document.getElementById('voice-prompt-text');
        const voiceResponse = document.getElementById('voice-response-text');
        const voiceStatus = document.getElementById('voice-status');
        
        let recognition = null;
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'vi-VN';
            recognition.continuous = false;
            recognition.interimResults = false;
            
            recognition.onstart = () => {
                if (voiceStatus) {
                    voiceStatus.textContent = 'Đang nghe';
                    voiceStatus.className = 'badge bg-success small pulse-dot';
                }
                if (voicePrompt) voicePrompt.textContent = 'Đang nghe giọng nói của bạn...';
            };
            
            recognition.onerror = (e) => {
                console.error(e);
                if (voiceStatus) {
                    voiceStatus.textContent = 'Lỗi';
                    voiceStatus.className = 'badge bg-danger small';
                }
            };
            
            recognition.onend = () => {
                if (voiceStatus && voiceStatus.textContent === 'Đang nghe') {
                    voiceStatus.textContent = 'Tắt';
                    voiceStatus.className = 'badge bg-danger small';
                }
            };
            
            recognition.onresult = async (event) => {
                const speechToText = event.results[0][0].transcript;
                if (voicePrompt) voicePrompt.innerHTML = `Bạn hỏi: "<i>${speechToText}</i>"`;
                
                let reply = "Tôi không hiểu câu hỏi của bạn. Hãy thử hỏi: Lớp hôm nay thế nào?";
                
                const cleanText = speechToText.toLowerCase();
                if (cleanText.includes('lớp hôm nay thế nào') || cleanText.includes('trạng thái lớp') || cleanText.includes('tập trung') || cleanText.includes('thế nào')) {
                    const total = cachedStudents.length;
                    const online = cachedStudents.filter(s => s.online).length;
                    const sleepy = cachedStudents.filter(s => s.state === 'Sleepy').length;
                    const distracted = cachedStudents.filter(s => s.state === 'Distracted').length;
                    const phone = cachedStudents.filter(s => s.state === 'Phone').length;
                    const measuredS = cachedStudents.filter(s => s.focus_score !== null && s.focus_score !== undefined);
                    const avg = measuredS.length > 0 ? Math.round(measuredS.reduce((acc, s) => acc + s.focus_score, 0) / measuredS.length) : null;
                    
                    reply = avg === null ? 'Chưa có dữ liệu điểm tập trung. ' : `Điểm trung bình của ${measuredS.length} học sinh đang được đo là ${avg} phần trăm. `;
                    if (sleepy > 0 || phone > 0 || distracted > 0) {
                        reply += `Phát hiện ${sleepy} học sinh buồn ngủ, và ${phone} học sinh đang dùng điện thoại. `;
                    } else {
                        reply += `Hiện không có hành vi kéo dài nào được ghi nhận.`;
                    }
                }
                
                if (voiceResponse) {
                    voiceResponse.classList.remove('d-none');
                    voiceResponse.textContent = reply;
                }
                
                if ('speechSynthesis' in window) {
                    const utterance = new SpeechSynthesisUtterance(reply);
                    utterance.lang = 'vi-VN';
                    const voices = window.speechSynthesis.getVoices();
                    const viVoice = voices.find(v => v.lang.includes('vi') || v.lang.includes('VN'));
                    if (viVoice) utterance.voice = viVoice;
                    window.speechSynthesis.speak(utterance);
                }
            };
        }
        
        if (btnVoice) {
            btnVoice.addEventListener('click', () => {
                if (voiceCard) voiceCard.classList.toggle('d-none');
                if (recognition && !voiceCard.classList.contains('d-none')) {
                    recognition.start();
                }
            });
        }

    function updateTeacherRootCauseChart(rootCause) {
        const canvas = document.getElementById('classRootCauseChart');
        if (!canvas) return;
        // null => not enough data: draw nothing rather than invented percentages
        const data = rootCause ? [rootCause.phone_pct, rootCause.drowsy_pct, rootCause.distracted_pct, rootCause.away_pct] : [0, 0, 0, 0];
        const ctx = canvas.getContext('2d');
        if (classRootCauseChartObj) {
            classRootCauseChartObj.data.datasets[0].data = data;
            classRootCauseChartObj.update();
        } else {
            classRootCauseChartObj = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Điện thoại', 'Buồn ngủ', 'Quay đi chỗ khác', 'Rời chỗ'],
                    datasets: [{ data: data, backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#94a3b8'], borderWidth: 0 }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { color: getChartColors().text } } }
                }
            });
        }
    }

    async function pollTeacherData() {
        try {
            const classSelect = document.getElementById('select-class-monitor');
            const classId = classSelect ? classSelect.value : 1;
            const res = await fetch(`/api/teacher/class_status?class_id=${classId}`);
            const data = await res.json();
            if (data.status === 'success') {
                cachedStudents = data.students;
                if (activeView === '2d') {
                    render2DClassroom(data.students);
                } else if (activeView === 'grid') {
                    renderStudentCards(data.students);
                } else if (activeView === 'list') {
                    renderStudentListRows(data.students);
                } else if (activeView === '3d') {
                    render3DClassroom(data.students);
                }
                renderTeacherStudentsTable();
                updateTeacherCharts(data.students);
                updateClassTimer(data.class_session_active, data.elapsed_seconds);
                
                checkInterventions(data.students);
                renderAttendanceTable(data.students);
                
                // Update classroom stats
                updateClassroomStatistics(data.students, data.logs || null);
                
                // Keep the live start/end buttons synchronized in case of reload
                const btnStartClass = document.getElementById('btn-start-class');
                const btnEndClass = document.getElementById('btn-end-class');
                const classSessionBadge = document.getElementById('class-session-badge');
                if (data.class_session_active) {
                    if (btnStartClass) btnStartClass.style.display = 'none';
                    if (btnEndClass) btnEndClass.style.display = 'block';
                    if (classSessionBadge) {
                        classSessionBadge.className = 'badge bg-success-subtle text-success border border-success';
                        classSessionBadge.textContent = 'Đang diễn ra';
                    }
                } else {
                    if (btnStartClass) btnStartClass.style.display = 'block';
                    if (btnEndClass) btnEndClass.style.display = 'none';
                    if (classSessionBadge) {
                        classSessionBadge.className = 'badge bg-danger-subtle text-danger border border-danger';
                        classSessionBadge.textContent = 'Chưa bắt đầu';
                    }
                }
            }

            // Get teacher analytics summary
            try {
                const resSummary = await fetch(`/api/teacher/analytics_summary?class_id=${selectedClassId()}`);
                const summary = await resSummary.json();
                if (summary.status === 'success') {
                    const dangerEl = document.getElementById('danger-hour-value');
                    if (dangerEl) dangerEl.textContent = summary.danger_hour || 'Chưa xác định';
                    
                    const watchlistBody = document.getElementById('watchlist-body');
                    if (watchlistBody) {
                        if (!summary.watchlist || summary.watchlist.length === 0) {
                            watchlistBody.innerHTML = '<tr><td colspan="2" class="text-center text-muted py-2"><small>Không có học sinh cần lưu ý</small></td></tr>';
                        } else {
                            let html = '';
                            summary.watchlist.forEach(s => {
                                html += `
                                    <tr>
                                        <td>
                                            <a href="#" class="text-white text-decoration-none view-student-detail-link" onclick="event.preventDefault(); window.showStudentDetail('${s.display_name}')">
                                                <i class="fa-solid fa-user text-muted me-2"></i>${s.display_name}
                                            </a>
                                        </td>
                                        <td class="text-end text-danger fw-semibold">${s.score}</td>
                                    </tr>
                                `;
                            });
                            watchlistBody.innerHTML = html;
                        }
                    }
                    
                    updateTeacherRootCauseChart(summary.root_cause);
                }
            } catch (err) {
                console.error("Error loading teacher analytics summary:", err);
            }

            // Get activity logs
            const resLogs = await fetch(`/api/teacher/logs?class_id=${selectedClassId()}`);
            const logs = await resLogs.json();
            renderActivityLogs(logs);
            renderTeacherAlertsTable(logs);
        } catch (err) {
            console.error("Error polling teacher dashboard:", err);
        }
    }

    function renderStudentCards(students) {
        const grid = document.getElementById('student-cards-grid');
        if (!grid) return;
        
        let onlineCount = 0;
        const existingCards = grid.querySelectorAll('.student-card');
        
        if (existingCards.length === students.length) {
            students.forEach(student => {
                if (student.online) onlineCount++;
                updateSingleStudentCard(student);
            });
        } else {
            grid.innerHTML = '';
            students.forEach(student => {
                if (student.online) onlineCount++;
                
                const card = document.createElement('div');
                let stateClass = 'state-normal';
                let badgeClass = 'badge-normal';
                let stateText = 'Bình thường';
                let stateIcon = '•';
                
                if (student.state === 'Focused') {
                    stateClass = 'state-focused'; badgeClass = 'badge-focused'; stateText = 'Tập trung'; stateIcon = '✓';
                } else if (student.state === 'Sleepy') {
                    stateClass = 'state-sleepy'; badgeClass = 'badge-sleepy'; stateText = 'Buồn ngủ'; stateIcon = '💤';
                } else if (student.state === 'Distracted') {
                    stateClass = 'state-distracted'; badgeClass = 'badge-distracted'; stateText = 'Mất tập trung'; stateIcon = '⚠';
                } else if (student.state === 'Phone') {
                    stateClass = 'state-phone'; badgeClass = 'badge-phone'; stateText = 'Dùng điện thoại'; stateIcon = '📱';
                }
                
                card.className = `student-card ${stateClass}`;
                
                const initials = student.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
                const trendIcon = student.focus_score >= 75
                    ? '<i class="fa-solid fa-arrow-trend-up text-success"></i>'
                    : '<i class="fa-solid fa-arrow-trend-down text-danger"></i>';
                const scoreColor = (student.focus_score === null || student.focus_score === undefined) ? '#94a3b8' : (student.focus_score >= 80 ? 'var(--success-color)' : (student.focus_score >= 50 ? 'var(--warning-color)' : 'var(--danger-color)'));
                const onlineDotClass = student.online ? '' : 'offline';

                // Check if we have a cached frame snapshot for this student
                const cachedFrame = studentFrames.get(student.name);
                const thumbContent = cachedFrame
                    ? `<img class="student-snapshot" src="${cachedFrame}" alt="${student.name}" style="width:100%;height:100%;object-fit:cover;display:block;">`
                    : `<div class="student-thumb-placeholder">
                          <div class="initials-circle">${initials}</div>
                          <span style="font-size:0.7rem;margin-top:2px;opacity:0.6">${student.online ? 'Camera sẵn sàng...' : 'Ngoại tuyến'}</span>
                       </div>`;
                
                card.innerHTML = `
                    <div class="student-card-thumb">
                        ${thumbContent}
                        <div class="student-state-overlay">
                            <span class="student-badge ${badgeClass}">${stateIcon} ${stateText}</span>
                        </div>
                        <div class="student-online-dot ${onlineDotClass}" title="${student.online ? 'Trực tuyến' : 'Ngoại tuyến'}"></div>
                        <div class="student-score-bar">
                            <div class="student-score-bar-fill" style="width:${scoreNum(student.focus_score)}%;background:${scoreColor};"></div>
                        </div>
                    </div>
                    <div class="student-card-info">
                        <h6 class="text-primary mb-1">${student.name}</h6>
                        <div class="student-focus-row">
                            <span>Độ tập trung</span>
                            <span class="student-focus-value" style="color: ${scoreColor};">${fmtScore(student.focus_score)}</span>
                        </div>
                    </div>
                `;
                
                card.addEventListener('click', () => {
                    showStudentDetailPanel(student);
                });
                
                grid.appendChild(card);
            });
        }
        
        // Update online count indicator
        const onlineCountEl = document.getElementById('online-count');
        if (onlineCountEl) onlineCountEl.textContent = onlineCount;
    }

    function renderStudentListRows(students) {
        const tbody = document.getElementById('student-list-rows');
        if (!tbody) return;
        tbody.innerHTML = '';
        
        let onlineCount = 0;
        
        students.forEach(student => {
            if (student.online) onlineCount++;
            
            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            
            let badgeClass = 'badge bg-secondary';
            if (student.state === 'Focused') badgeClass = 'badge bg-success';
            else if (student.state === 'Sleepy') badgeClass = 'badge bg-warning text-dark';
            else if (student.state === 'Distracted' || student.state === 'Phone') badgeClass = 'badge bg-danger';
            
            const stateLabels = STATE_LABELS_VI;
            const stateLabel = stateLabels[student.state] || 'Chưa có dữ liệu';

            const statusBadge = student.online 
                ? '<span class="badge bg-success-subtle text-success border border-success">Trực tuyến</span>' 
                : '<span class="badge bg-secondary-subtle text-secondary border border-secondary">Ngoại tuyến</span>';
            const initials = student.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
            
            const scoreColor = (student.focus_score === null || student.focus_score === undefined) ? '#94a3b8' : (student.focus_score >= 80 ? 'var(--success-color)' : (student.focus_score >= 50 ? 'var(--warning-color)' : 'var(--danger-color)'));

            tr.innerHTML = `
                <td><strong>${student.roll || 'N/A'}</strong></td>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="avatar bg-primary text-white" style="width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: bold;">
                            ${initials}
                        </div>
                        <div>
                            <span class="d-block fw-semibold">${student.name}</span>
                        </div>
                    </div>
                </td>
                <td>${statusBadge} <span class="${badgeClass} ms-1">${stateLabel}</span></td>
                <td class="text-center fw-bold" style="color: ${scoreColor};">${fmtScore(student.focus_score)}</td>
                <td class="text-center text-danger fw-bold">${student.distractions || 0}</td>
                <td class="text-end">
                    <button class="btn btn-outline-primary btn-sm btn-view-detail"><i class="fa-solid fa-eye me-1"></i>Chi tiết</button>
                </td>
            `;
            
            tr.addEventListener('click', () => {
                showStudentDetailPanel(student);
            });
            
            tbody.appendChild(tr);
        });
        
        const onlineCountEl = document.getElementById('online-count');
        if (onlineCountEl) onlineCountEl.textContent = onlineCount;
    }

    function showStudentDetailPanel(student) {
        selectedStudentName = student.name;
        const panel = document.getElementById('student-detail-panel');
        if (!panel) return;
        panel.style.display = 'block';
        
        document.getElementById('detail-name').textContent = student.name;
        document.getElementById('detail-roll').textContent = student.roll;

        // Update avatar initials in placeholder
        const detailAvatar = document.getElementById('detail-avatar');
        if (detailAvatar) {
            detailAvatar.textContent = student.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        }

        // Show snapshot if available, else show placeholder
        const snapshotImg = document.getElementById('detail-student-snapshot');
        const snapshotPlaceholder = document.getElementById('detail-snapshot-placeholder');
        const liveBadge = document.getElementById('detail-live-badge');
        const cachedFrame = studentFrames.get(student.name);
        if (cachedFrame && snapshotImg) {
            snapshotImg.src = cachedFrame;
            snapshotImg.style.display = 'block';
            if (snapshotPlaceholder) snapshotPlaceholder.style.display = 'none';
            if (liveBadge) liveBadge.style.display = 'inline-block';
        } else {
            if (snapshotImg) snapshotImg.style.display = 'none';
            if (snapshotPlaceholder) snapshotPlaceholder.style.display = 'flex';
            if (liveBadge) liveBadge.style.display = 'none';
        }
        
        const badge = document.getElementById('detail-badge');
        let badgeClass = 'badge bg-secondary';
        if (student.state === 'Focused') badgeClass = 'badge bg-success';
        else if (student.state === 'Sleepy') badgeClass = 'badge bg-warning text-dark';
        else if (student.state === 'Distracted' || student.state === 'Phone') badgeClass = 'badge bg-danger';
        badge.className = badgeClass;
        
        const stateLabels = STATE_LABELS_VI;
        const stateLabel = stateLabels[student.state] || 'Chưa có dữ liệu';
        badge.textContent = stateLabel;
        
        const score = document.getElementById('detail-focus-score');
        score.textContent = fmtScore(student.focus_score);
        score.className = (student.focus_score === null || student.focus_score === undefined) ? 'text-muted font-bold' : (student.focus_score >= 80 ? 'text-success font-bold' : (student.focus_score >= 50 ? 'text-warning font-bold' : 'text-danger font-bold'));
        
        document.getElementById('detail-distractions').textContent = student.distractions;
        
        const attState = document.getElementById('detail-attention');
        attState.textContent = stateLabel;
        document.getElementById('detail-activity').textContent = (student.labels && student.labels.visibility) || '—';

        const setDetail = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        const lbl = student.labels || {};
        setDetail('detail-attendance-status', lbl.attendance || '—');
        setDetail('detail-visibility-status', lbl.visibility || '—');
        setDetail('detail-connection-status', lbl.connection || '—');
        setDetail('detail-identity-status', (lbl.identity || '—') + (student.identity_confidence ? ` (${student.identity_confidence})` : ''));
        const detailAiSummary = document.getElementById('detail-ai-summary');
        if (detailAiSummary) detailAiSummary.innerHTML = generateAISummary(student);

        // Recreate mini student history chart
        renderMiniStudentChart(student.focus_history || []);
    }

    window.showStudentDetail = function(name) {
        const student = cachedStudents.find(s => s.name === name);
        if (student) {
            showStudentDetailPanel(student);
        } else {
            showStudentDetailPanel({ name: name, roll: 'N/A', focus_score: null, distractions: 0, online: false, state: 'Unknown' });
        }
    };

    function renderMiniStudentChart(historyData) {
        const ctx = document.getElementById('mini-student-chart');
        if (!ctx) return;
        
        if (teacherMiniChart) {
            teacherMiniChart.destroy();
        }
        
        // Standard labels
        const labels = Array.from({length: historyData.length}, (_, i) => i + 1);
        
        teacherMiniChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Focus Score',
                    data: historyData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { min: 0, max: 100, ticks: { stepSize: 20 } }
                }
            }
        });
    }

    function renderActivityLogs(logs) {
        const list = document.getElementById('activity-log-list');
        if (!list) return;
        list.innerHTML = '';
        if (!logs || logs.length === 0) {
            list.innerHTML = '<div class="text-center py-3 text-muted small">Chưa có nhật ký hoạt động</div>';
            return;
        }
        logs.slice().reverse().forEach(log => {
            const item = document.createElement('div');
            let typeClass = 'log-info';
            if (log.type === 'behavior_started') typeClass = 'log-danger';
            else if (log.type === 'client_report') typeClass = 'log-warning';
            item.className = `activity-log-item ${typeClass}`;
            item.innerHTML = `
                <div class="fw-bold me-2 text-primary" style="white-space: nowrap;">[${fmtClock(log.time)}]</div>
                <div class="text-secondary">${escapeHtml(log.message)}</div>
            `;
            list.appendChild(item);
        });
    }

    function updateClassTimer(isActive, seconds) {
        const timerEl = document.getElementById('class-timer');
        if (!timerEl) return;
        
        if (!isActive) {
            timerEl.textContent = '00:00:00';
            return;
        }
        
        const hrs = String(Math.floor(seconds / 3600)).padStart(2, '0');
        const mins = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
        const secs = String(seconds % 60).padStart(2, '0');
        timerEl.textContent = `${hrs}:${mins}:${secs}`;
    }

    function initTeacherCharts() {
        const donutCtx = document.getElementById('donut-focus-distribution');
        if (donutCtx) {
            donutChartObj = new Chart(donutCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Cao (80-100%)', 'Trung bình (50-79%)', 'Thấp (0-49%)'],
                    datasets: [{
                        data: [0, 0, 0],
                        backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 8 } }
                    },
                    cutout: '65%'
                }
            });
        }

        const avgCtx = document.getElementById('line-class-average');
        if (avgCtx) {
            lineAvgChartObj = new Chart(avgCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Lớp trung bình',
                        data: [],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.05)',
                        fill: true,
                        tension: 0.3,
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { min: 0, max: 100 }
                    }
                }
            });
        }

        // Initialize Teacher Analytics page charts if they exist
        const trendCtx = document.getElementById('analytics-trend-chart');
        if (trendCtx && !analyticsTrendChart) {
            analyticsTrendChart = new Chart(trendCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Mức độ tập trung TB lớp (%)',
                        data: [],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { min: 0, max: 100 }
                    }
                }
            });
        }

        const typesCtx = document.getElementById('analytics-types-chart');
        if (typesCtx && !analyticsTypesChart) {
            analyticsTypesChart = new Chart(typesCtx, {
                type: 'bar',
                data: {
                    labels: ['Tập trung', 'Chưa đo / khuất', 'Quay đi chỗ khác', 'Buồn ngủ', 'Dùng điện thoại'],
                    datasets: [{
                        label: 'Số lượt ghi nhận',
                        data: [0, 0, 0, 0, 0],
                        backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#7c3aed']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } }
                }
            });
        }
    }

    function updateTeacherCharts(students) {
        if (!donutChartObj) return;
        
        let high = 0, med = 0, low = 0;
        let sum = 0;
        const measuredStudents = students.filter(s => s.focus_score !== null && s.focus_score !== undefined);
        measuredStudents.forEach(s => {
            sum += s.focus_score;
            if (s.focus_score >= 80) high++;
            else if (s.focus_score >= 50) med++;
            else low++;
        });
        
        // Update donut
        donutChartObj.data.datasets[0].data = [high, med, low];
        donutChartObj.update();

        // Update donut center total count
        const donutTotalStudentsEl = document.getElementById('donut-total-students');
        if (donutTotalStudentsEl) {
            donutTotalStudentsEl.textContent = `${measuredStudents.length}/${students.length} đo được`;
        }
        
        const avg = measuredStudents.length > 0 ? Math.round(sum / measuredStudents.length) : null;
        
        // Update line class average
        if (lineAvgChartObj) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});
            
            if (avg !== null) {
                lineAvgChartObj.data.labels.push(timeStr);
                lineAvgChartObj.data.datasets[0].data.push(avg);
            }
            
            if (lineAvgChartObj.data.labels.length > 15) {
                lineAvgChartObj.data.labels.shift();
                lineAvgChartObj.data.datasets[0].data.shift();
            }
            lineAvgChartObj.update();
        }

        // Update Teacher Analytics page stats & charts if initialized
        const avgScoreEl = document.getElementById('analytics-avg-score');
        if (avgScoreEl) avgScoreEl.textContent = avg === null ? 'N/A' : `${avg}%`;

        const totalDistractionsEl = document.getElementById('analytics-total-distractions');
        if (totalDistractionsEl) {
            let totalDist = 0;
            students.forEach(s => totalDist += (s.distractions || 0));
            totalDistractionsEl.textContent = totalDist;
        }

        const bestStudentEl = document.getElementById('analytics-best-student');
        if (bestStudentEl) {
            if (measuredStudents.length > 0) {
                let best = measuredStudents[0];
                measuredStudents.forEach(s => { if (s.focus_score > best.focus_score) best = s; });
                bestStudentEl.textContent = best.name;
            } else {
                bestStudentEl.textContent = 'N/A';
            }
        }

        if (analyticsTypesChart && students.length > 0) {
            let focused = 0, normal = 0, distracted = 0, sleepy = 0, phone = 0;
            students.forEach(s => {
                if (s.state === 'Focused') focused++;
                else if (s.state === 'Sleepy') sleepy++;
                else if (s.state === 'Distracted') distracted++;
                else if (s.state === 'Phone') phone++;
                else normal++;
            });
            analyticsTypesChart.data.datasets[0].data = [focused, normal, distracted, sleepy, phone];
            analyticsTypesChart.update();
        }
        
        // Also update student sidebar if selected
        if (selectedStudentName) {
            const currentStudent = students.find(s => s.name === selectedStudentName);
            if (currentStudent) {
                showStudentDetailPanel(currentStudent);
            }
        }
    }

    function renderTeacherStudentsTable() {
        const tbody = document.getElementById('teacher-students-table-body');
        if (!tbody) return;
        
        const query = document.getElementById('search-students') ? document.getElementById('search-students').value.toLowerCase() : '';
        
        tbody.innerHTML = '';
        if (cachedStudents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">Không có dữ liệu học sinh.</td></tr>';
            return;
        }

        cachedStudents.forEach(student => {
            if (query && !student.name.toLowerCase().includes(query)) return;
            
            const tr = document.createElement('tr');
            
            let badgeClass = 'badge bg-secondary';
            if (student.state === 'Focused') badgeClass = 'badge bg-success';
            else if (student.state === 'Sleepy') badgeClass = 'badge bg-warning text-dark';
            else if (student.state === 'Distracted' || student.state === 'Phone') badgeClass = 'badge bg-danger';
            
            const stateLabels = STATE_LABELS_VI;
            const stateLabel = stateLabels[student.state] || 'Chưa có dữ liệu';

            const statusBadge = student.online ? '<span class="badge bg-success-subtle text-success border border-success">Trực tuyến</span>' : '<span class="badge bg-secondary-subtle text-secondary border border-secondary">Ngoại tuyến</span>';
            const initials = student.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

            tr.innerHTML = `
                <td><strong>${student.roll || 'N/A'}</strong></td>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <div class="avatar bg-primary text-white" style="width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: bold;">
                            ${initials}
                        </div>
                        <div>
                            <span class="d-block fw-semibold">${student.name}</span>
                            <small class="text-muted">${escapeHtml(student.labels ? student.labels.attendance : '')}</small>
                        </div>
                    </div>
                </td>
                <td>${statusBadge} <span class="${badgeClass} ms-1">${stateLabel}</span></td>
                <td class="text-center fw-bold text-primary">${fmtScore(student.focus_score)}</td>
                <td class="text-center text-danger fw-bold">${student.distractions || 0}</td>
                <td>${escapeHtml(student.labels ? student.labels.visibility : '—')}</td>
                <td class="text-end">
                    <button class="btn btn-outline-primary btn-sm" onclick="showStudentDetail('${student.name}')"><i class="fa-solid fa-eye me-1"></i>Xem chi tiết</button>
                </td>
            `;
            
            const btn = tr.querySelector('.btn-view-student');
            if (btn) {
                btn.addEventListener('click', () => {
                    window.location.href = '/teacher/dashboard?view_student=' + encodeURIComponent(student.name);
                });
            }
            
            tbody.appendChild(tr);
        });
    }

    function renderTeacherAlertsTable(logs) {
        const tbody = document.getElementById('teacher-alerts-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';
        const alerts = (logs || []).filter(l => l.type === 'behavior_started' && l.episode);
        if (alerts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Chưa có cảnh báo nào được ghi nhận.</td></tr>';
            return;
        }
        const severity = { PHONE: 'Cao', DROWSY: 'Trung bình', HEAD_AWAY: 'Thấp', AWAY: 'Trung bình' };
        alerts.slice().reverse().forEach(log => {
            const kind = log.episode.type;
            const student = cachedStudents.find(s => s.student_id === log.student_id);
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${fmtClock(log.time)}</td>
                <td><strong>${escapeHtml(student ? student.name : ('#' + log.student_id))}</strong></td>
                <td><span class="badge bg-danger-subtle text-danger border border-danger">${escapeHtml(EVENT_LABELS_VI[kind] || kind)}</span></td>
                <td><span class="badge bg-secondary">${severity[kind] || '—'}</span></td>
                <td><span class="badge bg-success-subtle text-success">Đã ghi nhận</span></td>
                <td class="text-end">
                    <button class="btn btn-outline-secondary btn-sm" onclick="this.closest('tr').style.opacity=0.5; this.disabled=true;">Bỏ qua</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function initAdminDashboard() {
        const formCreateClass = document.getElementById('form-create-class');
        const formCreateUser = document.getElementById('form-create-user');
        
        if (formCreateClass) {
            formCreateClass.addEventListener('submit', async (e) => {
                e.preventDefault();
                const classInput = document.getElementById('input-class-name');
                const className = classInput.value;
                
                const res = await fetch('/api/admin/create_class', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ class_name: className })
                });
                const data = await res.json();
                showToastNotification(data.message, data.status === 'success' ? 'success' : 'danger');
                if (data.status === 'success') {
                    classInput.value = '';
                    loadAdminClasses();
                }
            });
        }

        if (formCreateUser) {
            formCreateUser.addEventListener('submit', async (e) => {
                e.preventDefault();
                const username = document.getElementById('input-username').value;
                const password = document.getElementById('input-password').value;
                const displayName = document.getElementById('input-display-name').value;
                const role = document.getElementById('select-role').value;
                const classId = document.getElementById('select-class').value;
                
                const res = await fetch('/api/admin/create_user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: username,
                        password: password,
                        display_name: displayName,
                        role: role,
                        class_id: classId
                    })
                });
                const data = await res.json();
                showToastNotification(data.message, data.status === 'success' ? 'success' : 'danger');
                if (data.status === 'success') {
                    formCreateUser.reset();
                    loadAdminUsers();
                }
            });
        }

        // Show/hide class assignment based on role
        const selectRole = document.getElementById('select-role');
        const classSelectGroup = document.getElementById('class-select-group');
        if (selectRole && classSelectGroup) {
            selectRole.addEventListener('change', () => {
                if (selectRole.value === 'admin') {
                    classSelectGroup.style.display = 'none';
                } else {
                    classSelectGroup.style.display = 'block';
                }
            });
        }

        // Handle Edit Class Form Submission
        const formEditClass = document.getElementById('form-edit-class');
        if (formEditClass) {
            formEditClass.addEventListener('submit', async (e) => {
                e.preventDefault();
                const classId = document.getElementById('edit-class-id').value;
                const className = document.getElementById('edit-class-name').value;
                
                try {
                    const res = await fetch(`/api/admin/edit_class/${classId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ class_name: className })
                    });
                    const data = await res.json();
                    showToastNotification(data.message, data.status === 'success' ? 'success' : 'danger');
                    if (data.status === 'success') {
                        const modalEl = document.getElementById('editClassModal');
                        if (modalEl) {
                            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                            modalInstance.hide();
                        }
                        loadAdminClasses();
                        loadAdminUsers();
                    }
                } catch (err) {
                    console.error("Error updating class:", err);
                    showToastNotification("Gặp lỗi khi cập nhật lớp học.", "danger");
                }
            });
        }

        // Handle Delete Class Button inside confirmation modal
        const btnConfirmDeleteClass = document.getElementById('btn-confirm-delete-class');
        if (btnConfirmDeleteClass) {
            btnConfirmDeleteClass.addEventListener('click', async () => {
                const classId = document.getElementById('delete-class-id').value;
                try {
                    const res = await fetch(`/api/admin/delete_class/${classId}`, {
                        method: 'POST'
                    });
                    const data = await res.json();
                    showToastNotification(data.message, data.status === 'success' ? 'success' : 'danger');
                    if (data.status === 'success') {
                        const modalEl = document.getElementById('deleteClassModal');
                        if (modalEl) {
                            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                            modalInstance.hide();
                        }
                        loadAdminClasses();
                        loadAdminUsers();
                    }
                } catch (err) {
                    console.error("Error deleting class:", err);
                    showToastNotification("Gặp lỗi khi xóa lớp học.", "danger");
                }
            });
        }

        // Handle Edit User Role change (show/hide class dropdown)
        const editUserRole = document.getElementById('edit-user-role');
        const editUserClassSelectGroup = document.getElementById('edit-user-class-select-group');
        if (editUserRole && editUserClassSelectGroup) {
            editUserRole.addEventListener('change', () => {
                if (editUserRole.value === 'admin') {
                    editUserClassSelectGroup.style.display = 'none';
                } else {
                    editUserClassSelectGroup.style.display = 'block';
                }
            });
        }

        // Handle Edit User Form Submission
        const formEditUser = document.getElementById('form-edit-user');
        if (formEditUser) {
            formEditUser.addEventListener('submit', async (e) => {
                e.preventDefault();
                const userId = document.getElementById('edit-user-id').value;
                const username = document.getElementById('edit-user-username').value;
                const password = document.getElementById('edit-user-password').value;
                const displayName = document.getElementById('edit-user-display-name').value;
                const role = document.getElementById('edit-user-role').value;
                const classId = document.getElementById('edit-user-select-class').value;
                
                try {
                    const res = await fetch(`/api/admin/edit_user/${userId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            username: username,
                            password: password,
                            display_name: displayName,
                            role: role,
                            class_id: classId
                        })
                    });
                    const data = await res.json();
                    showToastNotification(data.message, data.status === 'success' ? 'success' : 'danger');
                    if (data.status === 'success') {
                        const modalEl = document.getElementById('editUserModal');
                        if (modalEl) {
                            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                            modalInstance.hide();
                        }
                        loadAdminUsers();
                        loadAdminClasses();
                    }
                } catch (err) {
                    console.error("Error updating user:", err);
                    showToastNotification("Gặp lỗi khi cập nhật tài khoản.", "danger");
                }
            });
        }

        // Handle Confirm Delete User Button Click
        const btnConfirmDeleteUser = document.getElementById('btn-confirm-delete-user');
        if (btnConfirmDeleteUser) {
            btnConfirmDeleteUser.addEventListener('click', async () => {
                const userId = document.getElementById('delete-user-id').value;
                try {
                    const res = await fetch(`/api/admin/delete_user/${userId}`, {
                        method: 'POST'
                    });
                    const data = await res.json();
                    showToastNotification(data.message, data.status === 'success' ? 'success' : 'danger');
                    if (data.status === 'success') {
                        const modalEl = document.getElementById('deleteUserModal');
                        if (modalEl) {
                            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                            modalInstance.hide();
                        }
                        loadAdminUsers();
                        loadAdminClasses();
                    }
                } catch (err) {
                    console.error("Error deleting user:", err);
                    showToastNotification("Gặp lỗi khi xóa tài khoản.", "danger");
                }
            });
        }

        // Initial loads
        loadAdminClasses();
        loadAdminUsers();
    }

    async function loadAdminClasses() {
        const selectClass = document.getElementById('select-class');
        const classesTableBody = document.getElementById('admin-classes-table-body');
        if (!selectClass && !classesTableBody) return;
        
        try {
            const res = await fetch('/api/admin/classes');
            const classes = await res.json();
            
            if (selectClass) {
                selectClass.innerHTML = '<option value="">-- Không có / Khác --</option>';
                classes.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = c.class_name;
                    selectClass.appendChild(opt);
                });
            }

            const editUserSelectClass = document.getElementById('edit-user-select-class');
            if (editUserSelectClass) {
                editUserSelectClass.innerHTML = '<option value="">-- Không có / Khác --</option>';
                classes.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = c.class_name;
                    editUserSelectClass.appendChild(opt);
                });
            }
            
            if (classesTableBody) {
                classesTableBody.innerHTML = '';
                classes.forEach(c => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${c.id}</td>
                        <td><strong>${c.class_name}</strong></td>
                        <td><span class="badge bg-info-subtle text-info border border-info px-2 py-1">${c.student_count || 0} Học sinh</span></td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-outline-primary edit-class-btn me-2" data-id="${c.id}" data-name="${c.class_name}" title="Sửa">
                                <i class="fa-solid fa-pen-to-square"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger delete-class-btn" data-id="${c.id}" data-name="${c.class_name}" title="Xóa">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    `;
                    classesTableBody.appendChild(tr);
                });

                // Attach click listeners to edit buttons
                classesTableBody.querySelectorAll('.edit-class-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const classId = btn.getAttribute('data-id');
                        const className = btn.getAttribute('data-name');
                        
                        const inputId = document.getElementById('edit-class-id');
                        const inputName = document.getElementById('edit-class-name');
                        if (inputId) inputId.value = classId;
                        if (inputName) inputName.value = className;
                        
                        const modalEl = document.getElementById('editClassModal');
                        if (modalEl) {
                            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                            modalInstance.show();
                        }
                    });
                });

                // Attach click listeners to delete buttons
                classesTableBody.querySelectorAll('.delete-class-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const classId = btn.getAttribute('data-id');
                        const className = btn.getAttribute('data-name');
                        
                        const inputId = document.getElementById('delete-class-id');
                        const nameText = document.getElementById('delete-class-name-text');
                        if (inputId) inputId.value = classId;
                        if (nameText) nameText.textContent = className;
                        
                        const modalEl = document.getElementById('deleteClassModal');
                        if (modalEl) {
                            const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                            modalInstance.show();
                        }
                    });
                });
            }
        } catch (err) {
            console.error("Error loading admin classes:", err);
        }
    }

    async function loadAdminUsers() {
        const tableBody = document.getElementById('admin-users-table-body');
        if (!tableBody) return;
        
        try {
            const res = await fetch('/api/admin/users');
            const users = await res.json();
            
            tableBody.innerHTML = '';
            users.forEach(u => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${u.id}</td>
                    <td><strong>${u.username}</strong></td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            ${u.role === 'student' ? `
                                <img src="${u.has_face ? 'data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2232%22 height=%2232%22 viewBox=%220 0 32 32%22><circle cx=%2216%22 cy=%2216%22 r=%2216%22 fill=%22%23d1fae5%22/><text x=%2250%%22 y=%2250%%22 fill=%22%23059669%22 font-size=%2216%22 font-family=%22Arial%22 dy=%22.3em%22 text-anchor=%22middle%22>✓</text></svg>' : 'data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2232%22 height=%2232%22 viewBox=%220 0 32 32%22><circle cx=%2216%22 cy=%2216%22 r=%2216%22 fill=%22%23e9ecef%22/><text x=%2250%%22 y=%2250%%22 fill=%22%23adb5bd%22 font-size=%2214%22 font-family=%22Arial%22 dy=%22.3em%22 text-anchor=%22middle%22>?</text></svg>'}" 
                                     alt="Avatar" 
                                     class="rounded-circle border" 
                                     style="width: 32px; height: 32px; object-fit: cover;"
                                     onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2232%22 height=%2232%22 viewBox=%220 0 32 32%22><circle cx=%2216%22 cy=%2216%22 r=%2216%22 fill=%22%236c757d%22/><text x=%2250%%22 y=%2255%%22 fill=%22white%22 font-size=%2212%22 font-family=%22Arial%22 dy=%22.3em%22 text-anchor=%22middle%22>${u.display_name.charAt(0)}</text></svg>'">
                            ` : `
                                <div class="rounded-circle bg-light border d-flex align-items-center justify-content-center text-muted" style="width: 32px; height: 32px; font-size: 12px; font-weight: bold;">
                                    ${u.display_name.charAt(0)}
                                </div>
                            `}
                            <span>${u.display_name}</span>
                        </div>
                    </td>
                    <td><span class="badge ${u.role === 'admin' ? 'bg-danger' : (u.role === 'teacher' ? 'bg-primary' : 'bg-success')}">${u.role === 'admin' ? 'Quản trị viên' : (u.role === 'teacher' ? 'Giáo viên' : 'Học sinh')}</span></td>
                    <td>${u.class_name}</td>
                    <td class="text-end">
                        ${u.role === 'student' ? `
                        <button class="btn btn-sm ${u.has_face ? 'btn-success' : 'btn-outline-info'} register-face-btn me-2" data-id="${u.id}" data-display-name="${u.display_name}" data-has-face="${u.has_face}" title="${u.has_face ? 'Đã đăng ký khuôn mặt' : 'Chụp/Đăng ký khuôn mặt'}">
                            <i class="fa-solid ${u.has_face ? 'fa-user-check' : 'fa-camera'}"></i>
                        </button>
                        ` : ''}
                        <button class="btn btn-sm btn-outline-primary edit-user-btn me-2" data-id="${u.id}" data-username="${u.username}" data-display-name="${u.display_name}" data-role="${u.role}" data-class-id="${u.class_id || ''}" title="Sửa tài khoản">
                            <i class="fa-solid fa-user-gear"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger delete-user-btn" data-id="${u.id}" data-username="${u.username}" title="Xóa tài khoản">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </td>
                `;
                tableBody.appendChild(tr);
            });

            // Attach click listeners to register face buttons
            tableBody.querySelectorAll('.register-face-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const studentId = btn.getAttribute('data-id');
                    const studentName = btn.getAttribute('data-display-name');
                    const hasFace = btn.getAttribute('data-has-face') === 'true';
                    
                    document.getElementById('register-face-student-id').value = studentId;
                    document.getElementById('register-face-student-name').textContent = studentName;
                    
                    const badge = document.getElementById('register-face-status-badge');
                    if (badge) {
                        if (hasFace) {
                            badge.className = 'badge bg-success';
                            badge.textContent = 'Đã đăng ký';
                        } else {
                            badge.className = 'badge bg-secondary';
                            badge.textContent = 'Chưa đăng ký';
                        }
                    }
                    
                    const resetBtn = document.getElementById('btn-reset-face-data');
                    if (resetBtn) {
                        if (hasFace) {
                            resetBtn.classList.remove('d-none');
                        } else {
                            resetBtn.classList.add('d-none');
                        }
                    }
                    
                    registeredImages = [];
                    updateCapturedImagesUI();
                    
                    const faceModal = new bootstrap.Modal(document.getElementById('registerFaceModal'));
                    faceModal.show();
                    
                    startFaceRegistrationCamera();
                });
            });

            // Attach click listeners to edit buttons
            tableBody.querySelectorAll('.edit-user-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const userId = btn.getAttribute('data-id');
                    const username = btn.getAttribute('data-username');
                    const displayName = btn.getAttribute('data-display-name');
                    const role = btn.getAttribute('data-role');
                    const classId = btn.getAttribute('data-class-id');
                    
                    document.getElementById('edit-user-id').value = userId;
                    document.getElementById('edit-user-username').value = username;
                    document.getElementById('edit-user-password').value = ''; // clear password field
                    document.getElementById('edit-user-display-name').value = displayName;
                    
                    const roleSelect = document.getElementById('edit-user-role');
                    roleSelect.value = role;
                    
                    const classSelectGroup = document.getElementById('edit-user-class-select-group');
                    const classSelect = document.getElementById('edit-user-select-class');
                    if (classSelect) classSelect.value = classId;
                    
                    if (role === 'admin') {
                        if (classSelectGroup) classSelectGroup.style.display = 'none';
                    } else {
                        if (classSelectGroup) classSelectGroup.style.display = 'block';
                    }
                    
                    const modalEl = document.getElementById('editUserModal');
                    if (modalEl) {
                        const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                        modalInstance.show();
                    }
                });
            });

            // Attach click listeners to delete buttons
            tableBody.querySelectorAll('.delete-user-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const userId = btn.getAttribute('data-id');
                    const username = btn.getAttribute('data-username');
                    
                    document.getElementById('delete-user-id').value = userId;
                    document.getElementById('delete-user-username-text').textContent = username;
                    
                    const modalEl = document.getElementById('deleteUserModal');
                    if (modalEl) {
                        const modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
                        modalInstance.show();
                    }
                });
            });
        } catch (err) {
            console.error("Error loading admin users:", err);
        }
    }

    // ----------------------------------------------------------------
    // HELPER: Sync start/end class session UI
    // ----------------------------------------------------------------
    function syncClassSessionUI(active) {
        const btnStartClass = document.getElementById('btn-start-class');
        const btnEndClass = document.getElementById('btn-end-class');
        const classSessionBadge = document.getElementById('class-session-badge');
        if (active) {
            if (btnStartClass) btnStartClass.style.display = 'none';
            if (btnEndClass) btnEndClass.style.display = 'block';
            if (classSessionBadge) {
                classSessionBadge.className = 'badge bg-success-subtle text-success border border-success';
                classSessionBadge.textContent = 'Đang diễn ra';
            }
        } else {
            if (btnStartClass) btnStartClass.style.display = 'block';
            if (btnEndClass) btnEndClass.style.display = 'none';
            if (classSessionBadge) {
                classSessionBadge.className = 'badge bg-danger-subtle text-danger border border-danger';
                classSessionBadge.textContent = 'Chưa bắt đầu';
            }
        }
    }

    // ----------------------------------------------------------------
    // HELPER: Update a single student card without re-rendering all
    // ----------------------------------------------------------------
    function updateSingleStudentCard(student) {
        const grid = document.getElementById('student-cards-grid');
        if (!grid) return;
        const allCards = grid.querySelectorAll('.student-card');
        allCards.forEach(card => {
            const nameEl = card.querySelector('h6');
            if (nameEl && nameEl.textContent.trim() === student.name) {
                let stateClass = 'state-normal';
                let badgeClass = 'badge-normal';
                let stateText = 'Bình thường';
                let stateIcon = '•';
                if (student.state === 'Focused')    { stateClass = 'state-focused';    badgeClass = 'badge-focused';    stateText = 'Tập trung';        stateIcon = '✓'; }
                else if (student.state === 'Sleepy') { stateClass = 'state-sleepy';     badgeClass = 'badge-sleepy';     stateText = 'Buồn ngủ';       stateIcon = '💤'; }
                else if (student.state === 'Distracted') { stateClass = 'state-distracted'; badgeClass = 'badge-distracted'; stateText = 'Mất tập trung'; stateIcon = '⚠'; }
                else if (student.state === 'Phone')  { stateClass = 'state-phone';      badgeClass = 'badge-phone';      stateText = 'Dùng điện thoại'; stateIcon = '📱'; }
                
                card.className = `student-card ${stateClass}`;
                
                // Update state badge overlay
                const badge = card.querySelector('.student-state-overlay .student-badge');
                if (badge) { badge.className = `student-badge ${badgeClass}`; badge.textContent = `${stateIcon} ${stateText}`; }
                
                // Update focus score and bar
                const scoreColor = (student.focus_score === null || student.focus_score === undefined) ? '#94a3b8' : (student.focus_score >= 80 ? 'var(--success-color)' : (student.focus_score >= 50 ? 'var(--warning-color)' : 'var(--danger-color)'));
                const trendIcon = student.focus_score >= 75
                    ? '<i class="fa-solid fa-arrow-trend-up text-success"></i>'
                    : '<i class="fa-solid fa-arrow-trend-down text-danger"></i>';
                const scoreEl = card.querySelector('.student-focus-value');
                if (scoreEl) { scoreEl.innerHTML = `${fmtScore(student.focus_score)}`; scoreEl.style.color = scoreColor; }
                const barFill = card.querySelector('.student-score-bar-fill');
                if (barFill) { barFill.style.width = `${scoreNum(student.focus_score)}%`; barFill.style.background = scoreColor; }

                // Update online status dot
                const onlineDot = card.querySelector('.student-online-dot');
                if (onlineDot) {
                    if (student.online) {
                        onlineDot.classList.remove('offline');
                    } else {
                        onlineDot.classList.add('offline');
                    }
                    onlineDot.title = student.online ? 'Trực tuyến' : 'Ngoại tuyến';
                }
                
                // Update placeholder text if not currently showing video snapshot
                const placeholderSpan = card.querySelector('.student-thumb-placeholder span');
                if (placeholderSpan) {
                    placeholderSpan.textContent = student.online ? 'Camera sẵn sàng...' : 'Ngoại tuyến';
                }
            }
        });
    }

    // ----------------------------------------------------------------
    // HELPER: Flash a student card to signal real-time update
    // ----------------------------------------------------------------
    function flashStudentCard(name) {
        const grid = document.getElementById('student-cards-grid');
        if (!grid) return;
        const allCards = grid.querySelectorAll('.student-card');
        allCards.forEach(card => {
            const nameEl = card.querySelector('h6');
            if (nameEl && nameEl.textContent.trim() === name) {
                card.style.transition = 'box-shadow 0.2s ease';
                card.style.boxShadow = '0 0 0 3px #3b82f6aa';
                setTimeout(() => { card.style.boxShadow = ''; }, 800);
            }
        });
    }

    // ----------------------------------------------------------------
    // HELPER: Toast notification
    // ----------------------------------------------------------------
    function showToastNotification(message, type = 'info') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
            document.body.appendChild(container);
        }
        const colorMap = { success: '#10b981', warning: '#f59e0b', danger: '#ef4444', info: '#3b82f6' };
        const toast = document.createElement('div');
        toast.style.cssText = `background:${colorMap[type]||'#3b82f6'};color:#fff;padding:12px 18px;border-radius:10px;font-size:0.88rem;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,0.2);opacity:0;transform:translateY(12px);transition:all 0.3s ease;max-width:320px;`;
        toast.textContent = message;
        container.appendChild(toast);
        requestAnimationFrame(() => { toast.style.opacity = '1'; toast.style.transform = 'translateY(0)'; });
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(12px)';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // ----------------------------------------------------------------
    // STUDENT WebSocket: push focus data + video frames to server
    // ----------------------------------------------------------------
    function initStudentSocket() {
        if (typeof io === 'undefined') return;
        const studentSocket = io();
        window.studentSocketGlobal = studentSocket;
        // Identity comes from the authenticated server session; the browser
        // never sends its name, state, score or frames.
        studentSocket.on('class_started', (data) => {
            showToastNotification(`📢 ${data.message}`, 'info');
        });
        studentSocket.on('class_ended', (data) => {
            showToastNotification(`🔔 ${data.message}`, 'warning');
        });
        studentSocket.on('error', (err) => {
            console.warn('[WS] server rejected:', err);
        });
    }

    // --- Init Phase ---
    const role = window.userRole || 'student';
    if (role === 'teacher') {
        initTeacherDashboard();
    } else if (role === 'admin') {
        initAdminDashboard();
    } else {
        // Student init
        loadSettings();
        handlePageRouting();
        initSessionState();
        updateGauge(null);
        
        // Listen for stats period dropdown changes
        const selectPeriod = document.getElementById('select-stats-period');
        if (selectPeriod) {
            selectPeriod.addEventListener('change', loadSessionHistory);
        }
        
        // Connect student WebSocket (receive-only; server is authoritative)
        initStudentSocket();
        
        // Tab switching detection for Anti-Cheating
        tabSwitchCount = 0;
        document.addEventListener('visibilitychange', () => {
            const switchBtn = document.getElementById('switch-anti-cheating');
            if (switchBtn && switchBtn.checked && document.visibilityState === 'hidden') {
                tabSwitchCount++;
                showToastNotification(`⚠ Phát hiện chuyển tab trình duyệt (${tabSwitchCount} lần)!`, 'danger');
                if (window.studentSocketGlobal && window.studentSocketGlobal.connected) {
                    window.studentSocketGlobal.emit('student_tab_switch', {});
                }
            }
        });
        
        // Checkbox listener to show status label and style card
        const switchBtn = document.getElementById('switch-anti-cheating');
        if (switchBtn) {
            // Apply initial state
            updateAntiCheatingUI(switchBtn.checked);
            
            switchBtn.addEventListener('change', () => {
                updateAntiCheatingUI(switchBtn.checked);
                if (switchBtn.checked) {
                    showToastNotification("🛡 Chế độ Chống Gian lận đã kích hoạt!", "success");
                } else {
                    showToastNotification("⚠ Chế độ Chống Gian lận đã tắt!", "warning");
                }
            });
        }
    }

    // Face Registration Helpers
    let faceStream = null;
    let registeredImages = [];

    let autoCaptureInterval = null;
    let isProcessingAutoCapture = false;

    function startAutoCaptureLoop() {
        stopAutoCaptureLoop();
        
        const autoSwitch = document.getElementById('switch-auto-capture');
        if (!autoSwitch || !autoSwitch.checked) return;
        
        const scanBox = document.getElementById('face-scan-box');
        const scanStatus = document.getElementById('face-scan-status');
        if (scanBox) scanBox.classList.remove('d-none');
        if (scanStatus) scanStatus.classList.remove('d-none');
        
        autoCaptureInterval = setInterval(async () => {
            const video = document.getElementById('register-face-video');
            const canvas = document.getElementById('register-face-canvas');
            if (!video || !canvas || !faceStream || isProcessingAutoCapture) return;
            
            if (registeredImages.length >= 10) {
                stopAutoCaptureLoop();
                showToastNotification("Đã tự động thu thập đủ 10 ảnh khuôn mặt chất lượng cao!", "success");
                return;
            }
            
            isProcessingAutoCapture = true;
            try {
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
                
                const res = await fetch('/api/admin/detect_face', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: dataUrl })
                });
                const data = await res.json();
                
                if (data.status === 'success') {
                    registeredImages.push(dataUrl);
                    updateCapturedImagesUI();
                    
                    if (scanBox) {
                        scanBox.style.borderColor = '#198754';
                        scanBox.style.boxShadow = 'inset 0 0 25px rgba(25,135,84,0.6)';
                        setTimeout(() => {
                            scanBox.style.borderColor = 'var(--bs-primary)';
                            scanBox.style.boxShadow = 'inset 0 0 20px rgba(13,110,253,0.3)';
                        }, 250);
                    }
                    
                    const statusText = document.getElementById('face-scan-status');
                    if (statusText) {
                        statusText.innerHTML = `<i class="fa-solid fa-circle-check text-success me-1"></i> Đã chụp ảnh (${registeredImages.length}/10)`;
                        setTimeout(() => {
                            if (autoCaptureInterval) {
                                statusText.innerHTML = `<span class="spinner-grow spinner-grow-sm text-primary me-1" role="status" aria-hidden="true"></span> Đang dò tìm khuôn mặt...`;
                            }
                        }, 600);
                    }
                }
            } catch (err) {
                console.error("Auto detect face error:", err);
            } finally {
                isProcessingAutoCapture = false;
            }
        }, 800);
    }

    function stopAutoCaptureLoop() {
        if (autoCaptureInterval) {
            clearInterval(autoCaptureInterval);
            autoCaptureInterval = null;
        }
        isProcessingAutoCapture = false;
        
        const scanBox = document.getElementById('face-scan-box');
        const scanStatus = document.getElementById('face-scan-status');
        if (scanBox) scanBox.classList.add('d-none');
        if (scanStatus) scanStatus.classList.add('d-none');
    }

    async function startFaceRegistrationCamera() {
        const video = document.getElementById('register-face-video');
        if (!video) return;
        try {
            faceStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            video.srcObject = faceStream;
            video.play();
            document.getElementById('btn-toggle-camera').innerHTML = '<i class="fa-solid fa-video-slash me-1"></i> Tắt Camera';
            startAutoCaptureLoop();
        } catch (err) {
            console.error("Lỗi camera đăng ký:", err);
            showToastNotification("Không thể truy cập camera. Vui lòng upload ảnh.", "warning");
        }
    }

    function stopFaceRegistrationCamera() {
        stopAutoCaptureLoop();
        if (faceStream) {
            faceStream.getTracks().forEach(track => track.stop());
            faceStream = null;
        }
        const video = document.getElementById('register-face-video');
        if (video) video.srcObject = null;
        const toggleBtn = document.getElementById('btn-toggle-camera');
        if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-video me-1"></i> Bật Camera';
    }

    function captureFacePhoto() {
        const video = document.getElementById('register-face-video');
        const canvas = document.getElementById('register-face-canvas');
        if (!video || !canvas || !faceStream) return;
        
        if (registeredImages.length >= 10) {
            showToastNotification("Bạn chỉ có thể chụp tối đa 10 ảnh.", "warning");
            return;
        }
        
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
        registeredImages.push(dataUrl);
        updateCapturedImagesUI();
    }

    function updateCapturedImagesUI() {
        const grid = document.getElementById('captured-images-grid');
        const noImagesText = document.getElementById('no-images-text');
        const capturedCount = document.getElementById('captured-count');
        const submitBtn = document.getElementById('btn-submit-register-face');
        
        if (!grid) return;
        grid.innerHTML = '';
        capturedCount.textContent = registeredImages.length;
        
        if (registeredImages.length === 0) {
            if (noImagesText) noImagesText.style.display = 'block';
            if (submitBtn) submitBtn.disabled = true;
        } else {
            if (noImagesText) noImagesText.style.display = 'none';
            if (submitBtn) submitBtn.disabled = (registeredImages.length < 5);
            
            registeredImages.forEach((img, idx) => {
                const col = document.createElement('div');
                col.className = 'col-4 position-relative mb-2';
                col.innerHTML = `
                    <div class="ratio ratio-1x1 border rounded overflow-hidden">
                        <img src="${img}" style="object-fit: cover; width: 100%; height: 100%;">
                    </div>
                    <button type="button" class="btn btn-danger btn-sm p-0 position-absolute top-0 end-0 rounded-circle m-1" style="width: 20px; height: 20px; line-height: 18px;" onclick="removeCapturedFaceImage(${idx})">
                        <i class="fa-solid fa-xmark" style="font-size: 0.7rem;"></i>
                    </button>
                `;
                grid.appendChild(col);
            });
        }
    }

    window.removeCapturedFaceImage = function(idx) {
        registeredImages.splice(idx, 1);
        updateCapturedImagesUI();
    };

    const captureBtn = document.getElementById('btn-capture-face');
    if (captureBtn) captureBtn.addEventListener('click', captureFacePhoto);
    
    const toggleCamBtn = document.getElementById('btn-toggle-camera');
    if (toggleCamBtn) {
        toggleCamBtn.addEventListener('click', () => {
            if (faceStream) stopFaceRegistrationCamera();
            else startFaceRegistrationCamera();
        });
    }

    const autoSwitch = document.getElementById('switch-auto-capture');
    if (autoSwitch) {
        autoSwitch.addEventListener('change', () => {
            if (autoSwitch.checked) {
                if (faceStream) startAutoCaptureLoop();
            } else {
                stopAutoCaptureLoop();
            }
        });
    }

    const cancelRegisterBtn = document.getElementById('btn-cancel-register-face');
    if (cancelRegisterBtn) cancelRegisterBtn.addEventListener('click', stopFaceRegistrationCamera);
    
    const closeRegisterModalBtn = document.getElementById('btn-close-register-face-modal');
    if (closeRegisterModalBtn) closeRegisterModalBtn.addEventListener('click', stopFaceRegistrationCamera);

    const registerModalEl = document.getElementById('registerFaceModal');
    if (registerModalEl) {
        registerModalEl.addEventListener('hidden.bs.modal', stopFaceRegistrationCamera);
    }

    const uploadFilesInput = document.getElementById('upload-face-files');
    if (uploadFilesInput) {
        uploadFilesInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            files.forEach(file => {
                if (registeredImages.length >= 10) return;
                const reader = new FileReader();
                reader.onload = (event) => {
                    registeredImages.push(event.target.result);
                    updateCapturedImagesUI();
                };
                reader.readAsDataURL(file);
            });
            uploadFilesInput.value = '';
        });
    }

    const submitRegisterBtn = document.getElementById('btn-submit-register-face');
    if (submitRegisterBtn) {
        submitRegisterBtn.addEventListener('click', async () => {
            const studentId = document.getElementById('register-face-student-id').value;
            submitRegisterBtn.disabled = true;
            submitRegisterBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i> Đang xử lý...';
            
            try {
                const res = await fetch('/api/admin/register_face', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: studentId,
                        images: registeredImages
                    })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    showToastNotification(data.message, 'success');
                    loadAdminUsers();
                    const modalEl = document.getElementById('registerFaceModal');
                    const modal = bootstrap.Modal.getInstance(modalEl);
                    if (modal) modal.hide();
                } else {
                    showToastNotification(data.message, 'danger');
                }
            } catch (err) {
                console.error("Lỗi đăng ký khuôn mặt:", err);
                showToastNotification("Đăng ký thất bại. Lỗi kết nối.", "danger");
            } finally {
                submitRegisterBtn.disabled = false;
                submitRegisterBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up me-1"></i> Đăng ký & Trích xuất đặc trưng';
            }
        });
    }

    const resetFaceDataBtn = document.getElementById('btn-reset-face-data');
    if (resetFaceDataBtn) {
        resetFaceDataBtn.addEventListener('click', async () => {
            const studentId = document.getElementById('register-face-student-id').value;
            if (!confirm("Bạn có chắc chắn muốn xóa dữ liệu đặc trưng khuôn mặt của học sinh này không? Cần chụp lại để hệ thống có thể nhận diện.")) {
                return;
            }
            
            resetFaceDataBtn.disabled = true;
            resetFaceDataBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i> Đang xóa...';
            
            try {
                const res = await fetch('/api/admin/reset_face', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: studentId })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    showToastNotification(data.message, 'success');
                    loadAdminUsers();
                    
                    const badge = document.getElementById('register-face-status-badge');
                    if (badge) {
                        badge.className = 'badge bg-secondary';
                        badge.textContent = 'Chưa đăng ký';
                    }
                    resetFaceDataBtn.classList.add('d-none');
                    
                    registeredImages = [];
                    updateCapturedImagesUI();
                } else {
                    showToastNotification(data.message, 'danger');
                }
            } catch (err) {
                console.error("Lỗi xóa dữ liệu khuôn mặt:", err);
                showToastNotification("Xóa thất bại. Lỗi kết nối.", "danger");
            } finally {
                resetFaceDataBtn.disabled = false;
                resetFaceDataBtn.innerHTML = '<i class="fa-solid fa-trash me-1"></i> Xóa dữ liệu cũ';
            }
        });
    }

    const fullscreenBtn = document.getElementById('btn-fullscreen-offline-camera');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', () => {
            const container = document.getElementById('offline-video-container');
            if (!container) return;
            
            if (!document.fullscreenElement) {
                container.requestFullscreen().then(() => {
                    fullscreenBtn.innerHTML = '<i class="fa-solid fa-compress text-white"></i>';
                }).catch(err => {
                    console.error("Error enabling fullscreen:", err);
                });
            } else {
                document.exitFullscreen().then(() => {
                    fullscreenBtn.innerHTML = '<i class="fa-solid fa-expand text-white"></i>';
                });
            }
        });
    }
    
    document.addEventListener('fullscreenchange', () => {
        const fullscreenBtn = document.getElementById('btn-fullscreen-offline-camera');
        if (fullscreenBtn) {
            if (document.fullscreenElement) {
                fullscreenBtn.innerHTML = '<i class="fa-solid fa-compress text-white"></i>';
            } else {
                fullscreenBtn.innerHTML = '<i class="fa-solid fa-expand text-white"></i>';
            }
        }
    });

    // Global simulator helper
    window.showMobileSimulator = function() {
        if (typeof bootstrap !== 'undefined') {
            const modal = new bootstrap.Modal(document.getElementById('mobileModal'));
            modal.show();
        }
    };
});
