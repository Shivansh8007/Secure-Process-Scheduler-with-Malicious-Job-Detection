// JobSentinel Frontend Controller
const API_URL = (window.location.origin.includes(":8000") || window.location.origin.includes("localhost"))
    ? window.location.origin.replace(/:[0-9]+$/, ":8000")
    : "http://127.0.0.1:8000";

let allJobs = [];
let allHistory = [];
let allAuditLogs = [];

// Format timestamps
function formatTime(isoString) {
    if (!isoString) return "-";
    try {
        const d = new Date(isoString);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
        return isoString;
    }
}

// Format duration
function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return "-";
    return Number(seconds).toFixed(2) + "s";
}

// Status badge helper
function getStatusBadge(status) {
    const s = String(status || "").toUpperCase();
    let badgeClass = "badge-pending";
    if (s === "RUNNING") badgeClass = "badge-running";
    else if (s === "COMPLETED") badgeClass = "badge-completed";
    else if (s === "FAILED") badgeClass = "badge-failed";
    else if (s === "QUARANTINED") badgeClass = "badge-quarantined";
    else if (s === "SCHEDULED") badgeClass = "badge-scheduled";

    return `<span class="badge ${badgeClass}">${s}</span>`;
}

// Load Dashboard Data
async function loadDashboard() {
    try {
        const [statsRes, jobsRes] = await Promise.all([
            fetch(`${API_URL}/dashboard/stats`),
            fetch(`${API_URL}/jobs`)
        ]);

        if (!statsRes.ok || !jobsRes.ok) {
            throw new Error("Failed to fetch dashboard data");
        }

        const stats = await statsRes.json();
        allJobs = await jobsRes.json();

        // Update statistics
        if (document.getElementById("totalJobs")) document.getElementById("totalJobs").textContent = stats.total ?? 0;
        if (document.getElementById("runningJobs")) document.getElementById("runningJobs").textContent = stats.running ?? 0;
        if (document.getElementById("completedJobs")) document.getElementById("completedJobs").textContent = stats.completed ?? 0;
        if (document.getElementById("quarantinedJobs")) document.getElementById("quarantinedJobs").textContent = stats.quarantined ?? 0;

        // Pending queue
        if (document.getElementById("queueNumber")) document.getElementById("queueNumber").textContent = stats.pending ?? 0;
        if (document.getElementById("queueProgress")) {
            const pct = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;
            document.getElementById("queueProgress").style.width = pct + "%";
        }

        // Render Recent Jobs table (first 5 jobs)
        const table = document.getElementById("jobsTable");
        if (table) {
            table.innerHTML = "";
            const recent = allJobs.slice(0, 5);
            if (recent.length === 0) {
                table.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#64748b;">No jobs in database yet.</td></tr>';
            } else {
                recent.forEach(job => {
                    const row = document.createElement("tr");
                    row.innerHTML = `
                        <td><strong>#${job.job_id}</strong></td>
                        <td>${getStatusBadge(job.status)}</td>
                        <td><code>${job.command ? job.command.slice(0, 30) : '-'}</code></td>
                        <td>${formatDuration(job.burst_time)}</td>
                        <td>${job.arrival_time ?? 0}s</td>
                    `;
                    table.appendChild(row);
                });
            }
        }
    } catch (error) {
        console.error("Dashboard error:", error);
    }
}

// Load Queue Data
async function loadQueue() {
    try {
        const [statsRes, jobsRes] = await Promise.all([
            fetch(`${API_URL}/dashboard/stats`),
            fetch(`${API_URL}/jobs`)
        ]);

        if (statsRes.ok) {
            const stats = await statsRes.json();
            if (document.getElementById("queuePending")) document.getElementById("queuePending").textContent = stats.pending ?? 0;
            if (document.getElementById("queueRunning")) document.getElementById("queueRunning").textContent = stats.running ?? 0;
            if (document.getElementById("queueCompleted")) document.getElementById("queueCompleted").textContent = stats.completed ?? 0;
            if (document.getElementById("queueFailed")) document.getElementById("queueFailed").textContent = stats.failed ?? 0;
        }

        if (jobsRes.ok) {
            allJobs = await jobsRes.json();
            renderQueueTable();
        }
    } catch (err) {
        console.error("Queue load error:", err);
    }
}

// Filter and render Queue Table
function renderQueueTable() {
    const tableBody = document.getElementById("queueTableBody");
    if (!tableBody) return;

    const searchTerm = (document.getElementById("jobSearch")?.value || "").toLowerCase().trim();
    const statusFilter = document.getElementById("statusFilter")?.value || "ALL";

    let filtered = allJobs.filter(job => {
        const matchesId = String(job.job_id).toLowerCase().includes(searchTerm) ||
                          String(job.command || "").toLowerCase().includes(searchTerm);
        const matchesStatus = (statusFilter === "ALL") || (String(job.status).toUpperCase() === statusFilter);
        return matchesId && matchesStatus;
    });

    tableBody.innerHTML = "";
    if (filtered.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#64748b;padding:24px;">No jobs match criteria.</td></tr>';
        return;
    }

    filtered.forEach(job => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>#${job.job_id}</strong></td>
            <td><code>${job.command || '-'}</code></td>
            <td>${job.arrival_time ?? 0}s</td>
            <td>${formatDuration(job.burst_time)}</td>
            <td><span style="font-weight:600;color:${job.priority === 1 ? '#38bdf8' : '#94a3b8'};">P${job.priority ?? 1}</span></td>
            <td><small style="color:#a5b4fc;">${job.algorithm || '-'}</small></td>
            <td>${getStatusBadge(job.status)}</td>
        `;
        tableBody.appendChild(row);
    });
}

// Run Scheduler
async function runScheduler() {
    const runBtn = document.getElementById("runSchedulerBtn");
    const algoSelect = document.getElementById("algorithmSelect");
    const algorithm = algoSelect ? algoSelect.value : "FCFS";

    if (runBtn) {
        runBtn.disabled = true;
        runBtn.textContent = "⏳ Running...";
    }

    try {
        const res = await fetch(`${API_URL}/jobs/schedule`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                algorithm: algorithm,
                execute_jobs: true,
                worker_id: "worker-1"
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert("Scheduler Notice: " + (err.detail || JSON.stringify(err)));
        } else {
            const data = await res.json();
            console.log("Scheduler executed:", data);
        }

        await loadQueue();
        await loadDashboard();
    } catch (err) {
        alert("Scheduler failed: " + err.message);
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.textContent = "▶ Run Scheduler";
        }
    }
}

// Load Execution History
async function loadHistory() {
    try {
        const res = await fetch(`${API_URL}/history`);
        if (!res.ok) throw new Error("Failed to load history");

        allHistory = await res.json();
        renderHistoryTable();
    } catch (err) {
        console.error("History load error:", err);
    }
}

// Render History Table
function renderHistoryTable() {
    const tableBody = document.getElementById("historyTable");
    if (!tableBody) return;

    const searchTerm = (document.getElementById("historySearch")?.value || "").toLowerCase().trim();
    const statusFilter = document.getElementById("historyStatusFilter")?.value || "ALL";

    let filtered = allHistory.filter(h => {
        const matchesId = String(h.job_id).toLowerCase().includes(searchTerm) ||
                          String(h.worker_id || "").toLowerCase().includes(searchTerm);
        const matchesStatus = (statusFilter === "ALL") || (String(h.status).toUpperCase() === statusFilter);
        return matchesId && matchesStatus;
    });

    tableBody.innerHTML = "";
    if (filtered.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#64748b;padding:24px;">No execution history records found.</td></tr>';
        return;
    }

    filtered.forEach(h => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>#${h.job_id}</strong></td>
            <td><span style="color:#60a5fa;">${h.worker_id || 'worker-1'}</span></td>
            <td>${getStatusBadge(h.status)}</td>
            <td>${formatTime(h.started_at)}</td>
            <td>${formatTime(h.completed_at)}</td>
            <td>${formatDuration(h.execution_time)}</td>
            <td><small style="color:#cbd5e1;" title="${h.output || h.error_message || ''}">${(h.output || h.error_message || '-').slice(0, 45)}</small></td>
        `;
        tableBody.appendChild(row);
    });
}

// Load Security Audit Logs
async function loadSecurity() {
    try {
        const [statsRes, auditRes] = await Promise.all([
            fetch(`${API_URL}/dashboard/stats`),
            fetch(`${API_URL}/audit-logs`)
        ]);

        if (statsRes.ok) {
            const stats = await statsRes.json();
            if (document.getElementById("securityQuarantined")) document.getElementById("securityQuarantined").textContent = stats.quarantined ?? 0;
            if (document.getElementById("securityFailed")) document.getElementById("securityFailed").textContent = stats.failed ?? 0;
        }

        if (auditRes.ok) {
            allAuditLogs = await auditRes.json();
            if (document.getElementById("auditRecords")) document.getElementById("auditRecords").textContent = allAuditLogs.length;
            if (document.getElementById("securityEvents")) document.getElementById("securityEvents").textContent = allAuditLogs.filter(a => a.event_type.includes("FAIL") || a.event_type.includes("QUARANTINE")).length;

            const tableBody = document.getElementById("securityTable");
            if (tableBody) {
                tableBody.innerHTML = "";
                if (allAuditLogs.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#64748b;padding:24px;">No audit events recorded yet.</td></tr>';
                } else {
                    allAuditLogs.slice(0, 50).forEach(log => {
                        const row = document.createElement("tr");
                        row.innerHTML = `
                            <td>#${log.id}</td>
                            <td><strong>#${log.job_id}</strong></td>
                            <td><span style="color:#f59e0b;font-weight:600;font-size:0.8rem;">${log.event_type}</span></td>
                            <td><small style="color:#e2e8f0;">${log.message}</small></td>
                            <td>${formatTime(log.timestamp)}</td>
                        `;
                        tableBody.appendChild(row);
                    });
                }
            }
        }
    } catch (err) {
        console.error("Security load error:", err);
    }
}

// Workers Page Data
async function loadWorkers() {
    try {
        const [statsRes, jobsRes] = await Promise.all([
            fetch(`${API_URL}/dashboard/stats`),
            fetch(`${API_URL}/jobs`)
        ]);

        const stats = statsRes.ok ? await statsRes.json() : { running: 0 };
        const jobs = jobsRes.ok ? await jobsRes.json() : [];
        const runningJobs = jobs.filter(j => j.status === "RUNNING");

        const workerBusy = runningJobs.length;
        const workerTotal = 3;
        const workerIdle = Math.max(0, workerTotal - workerBusy);

        if (document.getElementById("workerTotal")) document.getElementById("workerTotal").textContent = workerTotal;
        if (document.getElementById("workerBusy")) document.getElementById("workerBusy").textContent = workerBusy;
        if (document.getElementById("workerIdle")) document.getElementById("workerIdle").textContent = workerIdle;
        if (document.getElementById("workerOffline")) document.getElementById("workerOffline").textContent = "0";

        const workersTable = document.getElementById("workersTable");
        if (workersTable) {
            workersTable.innerHTML = "";
            for (let i = 1; i <= workerTotal; i++) {
                const wid = `WORKER-0${i}`;
                const assignedJob = runningJobs[i - 1];
                const isBusy = !!assignedJob;

                const row = document.createElement("tr");
                row.innerHTML = `
                    <td><strong>${wid}</strong></td>
                    <td><span class="badge ${isBusy ? 'badge-running' : 'badge-completed'}">${isBusy ? 'BUSY' : 'IDLE'}</span></td>
                    <td>${assignedJob ? '#' + assignedJob.job_id : 'None'}</td>
                    <td>${new Date().toLocaleTimeString()}</td>
                `;
                workersTable.appendChild(row);
            }
        }
    } catch (err) {
        console.error("Workers load error:", err);
    }
}

// Event Listeners Initialization
document.addEventListener("DOMContentLoaded", () => {
    // Refresh button
    document.getElementById("refreshBtn")?.addEventListener("click", loadDashboard);
    document.getElementById("refreshQueue")?.addEventListener("click", loadQueue);
    document.getElementById("refreshHistory")?.addEventListener("click", loadHistory);
    document.getElementById("runSchedulerBtn")?.addEventListener("click", runScheduler);

    // Queue Filters
    document.getElementById("jobSearch")?.addEventListener("input", renderQueueTable);
    document.getElementById("statusFilter")?.addEventListener("change", renderQueueTable);

    // History Filters
    document.getElementById("historySearch")?.addEventListener("input", renderHistoryTable);
    document.getElementById("historyStatusFilter")?.addEventListener("change", renderHistoryTable);

    // Modal controls
    const openJobModalBtn = document.getElementById("openJobModal");
    const closeJobModalBtn = document.getElementById("closeJobModal");
    const jobModal = document.getElementById("jobModal");

    if (openJobModalBtn && jobModal) {
        openJobModalBtn.addEventListener("click", () => {
            jobModal.classList.remove("hidden");
        });
    }

    if (closeJobModalBtn && jobModal) {
        closeJobModalBtn.addEventListener("click", () => {
            jobModal.classList.add("hidden");
        });
    }

    // Modal form submit
    const jobForm = document.getElementById("jobForm");
    if (jobForm) {
        jobForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const idVal = document.getElementById("jobId")?.value.trim();
            const cmdVal = document.getElementById("jobCommand")?.value.trim();
            const burstVal = parseFloat(document.getElementById("burstTime")?.value || "1");
            const priorityVal = parseInt(document.getElementById("priority")?.value || "1");

            const payload = {
                job_id: idVal ? (isNaN(Number(idVal)) ? idVal : Number(idVal)) : undefined,
                command: cmdVal,
                burst_time: burstVal,
                priority: priorityVal
            };

            try {
                const res = await fetch(`${API_URL}/jobs`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    if (jobModal) jobModal.classList.add("hidden");
                    jobForm.reset();
                    await loadQueue();
                    await loadDashboard();
                } else {
                    const err = await res.json();
                    alert("Submission failed: " + (err.detail || JSON.stringify(err)));
                }
            } catch (err) {
                alert("Error submitting job: " + err.message);
            }
        });
    }

    // Comparison Event Handlers
    const runCompareBtn = document.getElementById("runComparisonBtn");
    if (runCompareBtn) runCompareBtn.addEventListener("click", loadComparison);

    const refreshCompareBtn = document.getElementById("refreshCompareBtn");
    if (refreshCompareBtn) refreshCompareBtn.addEventListener("click", loadComparison);

    const compareScopeSelect = document.getElementById("compareScope");
    if (compareScopeSelect) {
        compareScopeSelect.addEventListener("change", function () {
            const customContainer = document.getElementById("customProcessesContainer");
            if (this.value === "custom") {
                if (customContainer) customContainer.classList.remove("hidden");
                initCustomProcessesTable();
            } else {
                if (customContainer) customContainer.classList.add("hidden");
            }
            loadComparison();
        });
    }

    const addRowBtn = document.getElementById("addCustomProcessRowBtn");
    if (addRowBtn) addRowBtn.addEventListener("click", () => addCustomProcessRow());

    const goToCompareBtn = document.getElementById("goToCompareBtn");
    if (goToCompareBtn) {
        goToCompareBtn.addEventListener("click", () => {
            const compNav = document.querySelector('.sidebar-nav .nav-link[data-page="comparison"]');
            if (compNav) compNav.click();
        });
    }

    // Sidebar navigation
    const navLinks = document.querySelectorAll(".sidebar-nav .nav-link");
    navLinks.forEach(link => {
        link.addEventListener("click", function (event) {
            event.preventDefault();
            const page = this.dataset.page;

            document.querySelectorAll(".page-section").forEach(section => {
                section.style.display = "none";
                section.classList.remove("active");
            });

            // Match both pageName and page-name
            const targetId = `${page}Page`;
            const selectedPage = document.getElementById(targetId) || document.getElementById(`${page}-page`);

            if (selectedPage) {
                selectedPage.style.display = "block";
                selectedPage.classList.add("active");
            } else {
                console.error(`Page not found: ${targetId}`);
            }

            navLinks.forEach(nav => nav.classList.remove("active"));
            this.classList.add("active");

            if (page === 'dashboard') loadDashboard();
            if (page === 'queue') loadQueue();
            if (page === 'workers') loadWorkers();
            if (page === 'history') loadHistory();
            if (page === 'security') loadSecurity();
            if (page === 'comparison') loadComparison();
        });
    });

    // Initial Load
    loadDashboard();
});

/* ===== ALGORITHM COMPARISON MODULE ===== */

let currentComparisonData = null;

const PROCESS_COLORS = [
    "#3b82f6", // blue
    "#10b981", // emerald
    "#f59e0b", // amber
    "#8b5cf6", // violet
    "#ec4899", // pink
    "#06b6d4", // cyan
    "#f97316", // orange
    "#84cc16", // lime
    "#14b8a6", // teal
    "#a855f7"  // purple
];

function getProcessColor(jobId, allJobIds) {
    const idx = allJobIds.indexOf(String(jobId));
    if (idx >= 0) return PROCESS_COLORS[idx % PROCESS_COLORS.length];
    let hash = 0;
    const str = String(jobId);
    for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
    }
    return PROCESS_COLORS[Math.abs(hash) % PROCESS_COLORS.length];
}

async function loadComparison() {
    const scopeSelect = document.getElementById("compareScope");
    const scope = scopeSelect ? scopeSelect.value : "pending";
    const quantumInput = document.getElementById("compareQuantum");
    const quantum = quantumInput ? parseFloat(quantumInput.value) || 2.0 : 2.0;

    const runBtn = document.getElementById("runComparisonBtn");
    const refreshBtn = document.getElementById("refreshCompareBtn");
    if (runBtn) { runBtn.disabled = true; runBtn.textContent = "⏳ Calculating..."; }
    if (refreshBtn) { refreshBtn.disabled = true; }

    try {
        let res;
        if (scope === "custom") {
            const customProcesses = getCustomProcessesFromTable();
            if (customProcesses.length === 0) {
                alert("Please add at least one process in the custom simulator table.");
                return;
            }
            res = await fetch(`${API_URL}/jobs/schedule/compare/custom`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    quantum: quantum,
                    processes: customProcesses
                })
            });
        } else if (scope === "sample") {
            const benchmarkPayload = {
                quantum: quantum,
                processes: [
                    { job_id: "P1", command: "python matrix_mult.py", arrival_time: 0.0, burst_time: 5.0, priority: 2 },
                    { job_id: "P2", command: "python quick_cache.py", arrival_time: 1.0, burst_time: 2.0, priority: 1 },
                    { job_id: "P3", command: "python db_ingest.py", arrival_time: 2.0, burst_time: 8.0, priority: 3 },
                    { job_id: "P4", command: "python log_aggregate.py", arrival_time: 3.0, burst_time: 3.0, priority: 2 }
                ]
            };
            res = await fetch(`${API_URL}/jobs/schedule/compare/custom`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(benchmarkPayload)
            });
        } else {
            res = await fetch(`${API_URL}/jobs/schedule/compare?quantum=${encodeURIComponent(quantum)}&scope=${encodeURIComponent(scope)}`);
        }

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to fetch algorithm comparison");
        }

        currentComparisonData = await res.json();
        renderComparisonUI(currentComparisonData);
    } catch (err) {
        console.error("Comparison load error:", err);
        const tbody = document.getElementById("algoComparisonTableBody");
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#ef4444;">Error loading comparison: ${err.message}</td></tr>`;
        }
    } finally {
        if (runBtn) { runBtn.disabled = false; runBtn.textContent = "⚡ Run Comparison"; }
        if (refreshBtn) { refreshBtn.disabled = false; }
    }
}

function renderComparisonUI(data) {
    if (!data) return;

    // 1. Recommendation Banner
    const recText = document.getElementById("recommendationText");
    const recSub = document.getElementById("recommendationSub");
    if (recText && data.recommended_algorithm) {
        const bestItem = (data.comparison_table || []).find(r => r.algorithm === data.recommended_algorithm) || {};
        recText.innerHTML = `🏆 <strong>${data.recommended_algorithm}</strong> achieved the optimal scheduling efficiency`;
        recSub.textContent = `Lowest Average Waiting Time: ${bestItem.average_waiting_time ?? '-'}s | Average Turnaround Time: ${bestItem.average_turnaround_time ?? '-'}s (Evaluated on ${data.total_jobs} processes, RR Quantum = ${data.quantum_used_for_rr}s).`;
    }

    // 2. Overall Summary Table (Rubric Requirement)
    const summaryTbody = document.getElementById("algoComparisonTableBody");
    if (summaryTbody && Array.isArray(data.comparison_table)) {
        summaryTbody.innerHTML = "";
        
        const minWT = Math.min(...data.comparison_table.map(x => x.average_waiting_time));
        const minTAT = Math.min(...data.comparison_table.map(x => x.average_turnaround_time));

        data.comparison_table.forEach((row, idx) => {
            const isBest = row.algorithm === data.recommended_algorithm;
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>
                    <strong>${row.algorithm}</strong>
                    ${isBest ? '<span class="best-algo-badge" style="margin-left: 8px;">★ Best</span>' : ''}
                </td>
                <td class="${row.average_waiting_time === minWT ? 'best-metric' : ''}">
                    <strong>${row.average_waiting_time.toFixed(2)}s</strong>
                </td>
                <td class="${row.average_turnaround_time === minTAT ? 'best-metric' : ''}">
                    <strong>${row.average_turnaround_time.toFixed(2)}s</strong>
                </td>
                <td>${row.average_response_time.toFixed(2)}s</td>
                <td>${Number(row.throughput).toFixed(4)} jobs/s</td>
                <td>${Number(row.cpu_utilization).toFixed(1)}%</td>
                <td>#${idx + 1}</td>
            `;
            summaryTbody.appendChild(tr);
        });
    }

    // 3. Gantt Chart Timelines
    renderGanttCharts(data);

    // 4. Per-Process Comparison Matrix ("Along Processes")
    renderProcessComparisonMatrix(data);
}

function renderGanttCharts(data) {
    const container = document.getElementById("ganttChartsContainer");
    if (!container) return;

    container.innerHTML = "";
    const ganttData = data.gantt_charts || {};
    const algos = ["FCFS", "SJF", "ROUND_ROBIN", "PRIORITY"];

    const allJobIds = Array.from(new Set(
        (data.process_comparison || []).map(p => String(p.job_id))
    ));

    let maxTime = 1;
    for (const algo of algos) {
        const slices = ganttData[algo] || [];
        for (const s of slices) {
            if (s.end_time > maxTime) maxTime = s.end_time;
        }
    }

    algos.forEach(algo => {
        const slices = ganttData[algo] || [];
        const card = document.createElement("div");
        card.className = "gantt-algo-card";

        const summaryRow = (data.comparison_table || []).find(r => r.algorithm === algo) || {};

        card.innerHTML = `
            <div class="gantt-algo-header">
                <div class="gantt-algo-name">
                    <span>${algo}</span>
                    ${algo === data.recommended_algorithm ? '<span class="best-algo-badge">Recommended</span>' : ''}
                </div>
                <div class="gantt-algo-stats">
                    Avg WT: <strong>${summaryRow.average_waiting_time ?? '-'}s</strong> | Avg TAT: <strong>${summaryRow.average_turnaround_time ?? '-'}s</strong>
                </div>
            </div>
            <div class="gantt-timeline-track" id="ganttTrack_${algo}"></div>
        `;

        container.appendChild(card);

        const track = card.querySelector(`#ganttTrack_${algo}`);
        if (slices.length === 0) {
            track.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;width:100%;color:#64748b;font-size:12px;">No slices recorded</div>`;
        } else {
            slices.forEach(slice => {
                const widthPct = Math.max(3, (slice.duration / maxTime) * 100);
                const color = getProcessColor(slice.job_id, allJobIds);
                const sliceDiv = document.createElement("div");
                sliceDiv.className = "gantt-slice";
                sliceDiv.style.width = `${widthPct}%`;
                sliceDiv.style.backgroundColor = color;
                sliceDiv.title = `Process ${slice.job_id}: [${slice.start_time}s - ${slice.end_time}s] (${slice.duration}s)`;
                sliceDiv.innerHTML = `<div>${slice.job_id}</div><span>${slice.duration}s</span>`;
                track.appendChild(sliceDiv);
            });
        }
    });

    // Render Color Legend for Processes
    if (allJobIds.length > 0) {
        const legendDiv = document.createElement("div");
        legendDiv.className = "gantt-legend";
        allJobIds.forEach(jid => {
            const color = getProcessColor(jid, allJobIds);
            const item = document.createElement("div");
            item.className = "gantt-legend-item";
            item.innerHTML = `<span class="gantt-color-dot" style="background-color: ${color}"></span> <strong>${jid}</strong>`;
            legendDiv.appendChild(item);
        });
        container.appendChild(legendDiv);
    }
}

function renderProcessComparisonMatrix(data) {
    const tbody = document.getElementById("processComparisonTableBody");
    if (!tbody) return;

    tbody.innerHTML = "";
    const processes = data.process_comparison || [];

    if (processes.length === 0) {
        tbody.innerHTML = `<tr><td colspan="16" style="text-align: center; color: #64748b;">No processes available to compare.</td></tr>`;
        return;
    }

    processes.forEach(proc => {
        const algos = proc.algorithms || {};
        const fcfs = algos.FCFS || {};
        const sjf = algos.SJF || {};
        const rr = algos.ROUND_ROBIN || {};
        const prio = algos.PRIORITY || {};

        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>#${proc.job_id}</strong></td>
            <td>${proc.arrival_time}s</td>
            <td><strong>${proc.burst_time}s</strong></td>
            <td>${proc.priority}</td>
            
            <!-- Waiting Time: FCFS, SJF, RR, Priority -->
            <td style="border-left: 2px solid #334155;">${fcfs.waiting_time !== undefined ? fcfs.waiting_time + 's' : '-'}</td>
            <td>${sjf.waiting_time !== undefined ? sjf.waiting_time + 's' : '-'}</td>
            <td>${rr.waiting_time !== undefined ? rr.waiting_time + 's' : '-'}</td>
            <td style="border-right: 2px solid #334155;">${prio.waiting_time !== undefined ? prio.waiting_time + 's' : '-'}</td>

            <!-- Turnaround Time: FCFS, SJF, RR, Priority -->
            <td>${fcfs.turnaround_time !== undefined ? fcfs.turnaround_time + 's' : '-'}</td>
            <td>${sjf.turnaround_time !== undefined ? sjf.turnaround_time + 's' : '-'}</td>
            <td>${rr.turnaround_time !== undefined ? rr.turnaround_time + 's' : '-'}</td>
            <td style="border-right: 2px solid #334155;">${prio.turnaround_time !== undefined ? prio.turnaround_time + 's' : '-'}</td>

            <!-- Execution Order: FCFS, SJF, RR, Priority -->
            <td>#${fcfs.order ?? '-'}</td>
            <td>#${sjf.order ?? '-'}</td>
            <td>#${rr.order ?? '-'}</td>
            <td>#${prio.order ?? '-'}</td>
        `;
        tbody.appendChild(row);
    });
}

function initCustomProcessesTable() {
    const tbody = document.getElementById("customProcessesTbody");
    if (!tbody || tbody.children.length > 0) return;

    const defaults = [
        { id: "P1", arrival: 0.0, burst: 6.0, priority: 2 },
        { id: "P2", arrival: 1.0, burst: 2.0, priority: 1 },
        { id: "P3", arrival: 2.0, burst: 8.0, priority: 3 },
        { id: "P4", arrival: 3.0, burst: 3.0, priority: 2 }
    ];

    defaults.forEach(p => addCustomProcessRow(p.id, p.arrival, p.burst, p.priority));
}

function addCustomProcessRow(id = "", arrival = 0, burst = 2, priority = 1) {
    const tbody = document.getElementById("customProcessesTbody");
    if (!tbody) return;

    const rowCount = tbody.children.length + 1;
    const processId = id || `P${rowCount}`;

    const tr = document.createElement("tr");
    tr.innerHTML = `
        <td><input type="text" class="custom-proc-id" value="${processId}" style="width: 80px; padding: 4px 8px; background: #0b1120; border: 1px solid #1f2d47; border-radius: 4px; color: #fff;"></td>
        <td><input type="number" class="custom-proc-arrival" value="${arrival}" min="0" step="0.5" style="width: 70px; padding: 4px 8px; background: #0b1120; border: 1px solid #1f2d47; border-radius: 4px; color: #fff;"></td>
        <td><input type="number" class="custom-proc-burst" value="${burst}" min="0.1" step="0.5" style="width: 70px; padding: 4px 8px; background: #0b1120; border: 1px solid #1f2d47; border-radius: 4px; color: #fff;"></td>
        <td><input type="number" class="custom-proc-prio" value="${priority}" min="1" max="10" style="width: 60px; padding: 4px 8px; background: #0b1120; border: 1px solid #1f2d47; border-radius: 4px; color: #fff;"></td>
        <td><button type="button" class="text-btn remove-custom-row" style="color: #ef4444; font-size: 14px; background: none; border: none; cursor: pointer;">✕</button></td>
    `;

    tr.querySelector(".remove-custom-row").addEventListener("click", () => tr.remove());
    tbody.appendChild(tr);
}

function getCustomProcessesFromTable() {
    const tbody = document.getElementById("customProcessesTbody");
    if (!tbody) return [];

    const processes = [];
    const rows = tbody.querySelectorAll("tr");
    rows.forEach(tr => {
        const id = tr.querySelector(".custom-proc-id")?.value.trim();
        const arrival = parseFloat(tr.querySelector(".custom-proc-arrival")?.value) || 0;
        const burst = parseFloat(tr.querySelector(".custom-proc-burst")?.value) || 1;
        const priority = parseInt(tr.querySelector(".custom-proc-prio")?.value) || 1;
        if (id) {
            processes.push({
                job_id: id,
                arrival_time: arrival,
                burst_time: burst,
                priority: priority,
                command: `Task ${id}`
            });
        }
    });
    return processes;
}