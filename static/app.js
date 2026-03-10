// Daily Work Progress Dashboard - Main JavaScript

// Global state
let currentDate = new Date().toISOString().split('T')[0];
let employees = [];
let tasks = [];

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    initializeDatePickers();
    loadDashboard(currentDate);
    loadEmployees();
    loadTasks(currentDate);
    loadDashboardHistory();
    setupEventListeners();
});

// Tab Navigation
function initializeTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            
            // Remove active from all
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Add active to selected
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');
            
            // Refresh data when switching tabs
            if (tabId === 'dashboard') {
                const dateInput = document.getElementById('dashboard-date');
                loadDashboard(dateInput.value || currentDate);
            } else if (tabId === 'tasks') {
                loadTasks(document.getElementById('task-filter-date').value || currentDate);
            } else if (tabId === 'create-dashboard') {
                const createDate = document.getElementById('create-date').value || currentDate;
                loadDashboardStatsForDate(createDate);
            } else if (tabId === 'history') {
                loadDashboardHistory();
            }
        });
    });
}

// Initialize date pickers with today's date
function initializeDatePickers() {
    const today = new Date().toISOString().split('T')[0];
    
    document.getElementById('dashboard-date').value = today;
    document.getElementById('create-date').value = today;
    document.getElementById('task-date').value = today;
    document.getElementById('task-filter-date').value = today;
    
    // Set header date
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('current-date').textContent = new Date().toLocaleDateString('en-US', options);
}

// ============ DASHBOARD APIs ============
async function loadDashboard(date) {
    try {
        const response = await fetch(`/api/dashboard/${date}`);
        const data = await response.json();
        
        updateDashboardUI(data);
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function updateDashboardUI(data) {
    // Update summary cards
    if (data.stats) {
        document.getElementById('stat-total').textContent = data.stats.total_people;
        document.getElementById('stat-active').textContent = data.stats.active_today;
        document.getElementById('stat-leave').textContent = data.stats.on_leave;
        document.getElementById('stat-closed').textContent = data.stats.tasks_closed;
        
        // Update EOD summary
        document.getElementById('eod-total').textContent = data.stats.total_assigned;
        document.getElementById('eod-completed').textContent = data.stats.completed_today;
        document.getElementById('eod-pending').textContent = data.stats.pending_attention;
        document.getElementById('eod-inprogress').textContent = data.stats.in_progress_count;
        document.getElementById('eod-deadline-extended').textContent = data.stats.deadline_extended_count || 0;
        document.getElementById('eod-updated').textContent = data.stats.tasks_updated;
        document.getElementById('eod-verified').textContent = data.stats.verified_by_admin;
    }
    
    // Update employee breakdown
    const empContainer = document.getElementById('employee-breakdown');
    empContainer.innerHTML = '';
    
    data.employee_breakdown.forEach(emp => {
        const card = createEmployeeCard(emp);
        empContainer.appendChild(card);
    });
    
    // Update pending tasks table
    const tasksBody = document.getElementById('pending-tasks-body');
    tasksBody.innerHTML = '';
    
    data.pending_tasks.forEach(task => {
        const row = createTaskRow(task);
        tasksBody.appendChild(row);
    });
}

function createEmployeeCard(emp) {
    const completionRate = emp.completion_rate || 0;
    const badgeClass = completionRate >= 90 ? 'badge-green' : completionRate >= 50 ? 'badge-yellow' : 'badge-orange';
    const progressClass = completionRate >= 80 ? 'green' : '';
    
    const card = document.createElement('div');
    card.className = 'employee-card';
    card.innerHTML = `
        <div class="employee-header">
            <div class="emp-info">
                <div class="emp-avatar" style="background: ${emp.color}">${emp.initials}</div>
                <div>
                    <div class="emp-name">${emp.name}</div>
                    <div class="emp-role">${emp.designation}</div>
                </div>
            </div>
            <span class="completion-badge ${badgeClass}">${completionRate}% Done</span>
        </div>
        <div class="task-stats">
            <div class="task-stat">
                <div class="task-stat-value">${emp.assigned}</div>
                <div class="task-stat-label">Assigned</div>
            </div>
            <div class="task-stat">
                <div class="task-stat-value done">${emp.done}</div>
                <div class="task-stat-label">Done</div>
            </div>
            <div class="task-stat">
                <div class="task-stat-value pending">${emp.pending}</div>
                <div class="task-stat-label">Pending</div>
            </div>
            <div class="task-stat">
                <div class="task-stat-value inprogress">${emp.in_progress}</div>
                <div class="task-stat-label">In Prog</div>
            </div>
        </div>
        <div class="progress-section">
            <div class="progress-label">TASK COMPLETION: ${emp.done}/${emp.assigned}</div>
            <div class="progress-bar">
                <div class="progress-fill ${progressClass}" style="width: ${completionRate}%"></div>
            </div>
        </div>
        <div class="status-tags">
            ${emp.task_updated 
                ? '<span class="status-tag tag-green">✓ Task/s Updated</span>' 
                : '<span class="status-tag tag-red">✗ No Tasks Updated</span>'}
            ${emp.verify_pending 
                ? '<span class="status-tag tag-red">⚠ Verify Pending</span>' 
                : '<span class="status-tag tag-green">✓ Tasks Verified</span>'}
            ${emp.deadline_extended > 0 
                ? `<span class="status-tag tag-yellow">⏱ Deadline Extended ${emp.deadline_extended}</span>` 
                : ''}
        </div>
    `;
    return card;
}

function createTaskRow(task) {
    const row = document.createElement('tr');
    const statusClass = task.status === 'In Progress' ? 'status-inprogress' : 
                       task.status === 'Pending' ? 'status-pending' :
                       task.status === 'Done' ? 'status-done' : 'status-extended';
    const priorityClass = `priority-${task.priority.toLowerCase()}`;
    
    row.innerHTML = `
        <td>${task.employee_name}</td>
        <td>${task.task_name}</td>
        <td><span class="status-badge ${statusClass}">${task.status}</span></td>
        <td>${task.deadline || '-'}</td>
        <td class="${priorityClass}">${task.priority}</td>
        <td>${task.notes || '-'}</td>
    `;
    return row;
}

// ============ EMPLOYEE APIs ============
async function loadEmployees() {
    try {
        const response = await fetch('/api/employees');
        employees = await response.json();
        updateEmployeeList();
        updateEmployeeSelects();
    } catch (error) {
        console.error('Error loading employees:', error);
    }
}

function updateEmployeeList() {
    const tbody = document.getElementById('employee-list');
    tbody.innerHTML = '';
    
    employees.forEach(emp => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><div class="emp-avatar" style="background: ${emp.color}; width: 32px; height: 32px; font-size: 12px;">${emp.initials}</div></td>
            <td>${emp.name}</td>
            <td>${emp.department}</td>
            <td>${emp.designation}</td>
            <td>${emp.employee_type}</td>
            <td class="actions">
                <button class="btn-small btn-delete" onclick="deleteEmployee(${emp.id})">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function updateEmployeeSelects() {
    // Update all employee dropdowns
    const selects = ['task-employee', 'task-filter-employee', 'edit-task-employee'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (select) {
            const currentValue = select.value;
            select.innerHTML = selectId.includes('filter') ? '<option value="">All Employees</option>' : '<option value="">Select Employee</option>';
            employees.forEach(emp => {
                const option = document.createElement('option');
                option.value = emp.id;
                option.textContent = `${emp.name} - ${emp.designation}`;
                select.appendChild(option);
            });
            if (currentValue) select.value = currentValue;
        }
    });
}

async function addEmployee() {
    const name = document.getElementById('emp-name').value.trim();
    const department = document.getElementById('emp-department').value.trim();
    const designation = document.getElementById('emp-designation').value.trim();
    const type = document.getElementById('emp-type').value;
    
    if (!name || !department || !designation || !type) {
        showMessage('employee-message', 'Please fill all required fields', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/employees', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, department, designation, employee_type: type })
        });
        
        const data = await response.json();
        if (data.success) {
            showMessage('employee-message', 'Employee added successfully!', 'success');
            document.getElementById('emp-name').value = '';
            document.getElementById('emp-department').value = '';
            document.getElementById('emp-designation').value = '';
            document.getElementById('emp-type').value = '';
            loadEmployees();
        } else {
            showMessage('employee-message', data.error || 'Failed to add employee', 'error');
        }
    } catch (error) {
        showMessage('employee-message', 'Error adding employee', 'error');
    }
}

async function deleteEmployee(id) {
    if (!confirm('Are you sure you want to delete this employee?')) return;
    
    try {
        const response = await fetch(`/api/employees/${id}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            loadEmployees();
        }
    } catch (error) {
        console.error('Error deleting employee:', error);
    }
}

// ============ DASHBOARD CREATION APIs ============
let dashboardStats = {}; // Store auto-calculated stats
let activeEmployees = [];
let onLeaveEmployees = [];

async function loadDashboardStatsForDate(date) {
    if (!date) return;
    
    try {
        // Get auto-calculated stats from tasks
        const response = await fetch(`/api/dashboard-stats/${date}`);
        dashboardStats = await response.json();
        
        // Update preview displays
        document.getElementById('preview-total-people').textContent = dashboardStats.total_people;
        document.getElementById('preview-total-assigned').textContent = dashboardStats.total_assigned;
        document.getElementById('preview-completed').textContent = dashboardStats.completed_today;
        document.getElementById('preview-pending').textContent = dashboardStats.pending_attention;
        document.getElementById('preview-inprogress').textContent = dashboardStats.in_progress_count;
        document.getElementById('preview-deadline-extended').textContent = dashboardStats.deadline_extended_count || 0;
        document.getElementById('preview-tasks-closed').textContent = dashboardStats.tasks_closed;
        
        // Load employee status (Active/On Leave)
        const statusResponse = await fetch(`/api/dashboard-employee-status/${date}`);
        const statusData = await statusResponse.json();
        activeEmployees = statusData.active_employees || [];
        onLeaveEmployees = statusData.on_leave_employees || [];
        
        // Update employee dropdowns
        updateEmployeeDropdowns();
        
        // Update employee stat cards with auto-calculated data
        updateEmployeeStatCards(dashboardStats.employee_stats);
        
        // Update preview counts
        updatePreviewCounts();
        
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
    }
}

function updateEmployeeDropdowns() {
    const activeSelect = document.getElementById('active-employees');
    const onLeaveSelect = document.getElementById('onleave-employees');
    
    // Clear existing options (keep first placeholder)
    activeSelect.innerHTML = '';
    onLeaveSelect.innerHTML = '';
    
    employees.forEach(emp => {
        const activeOption = document.createElement('option');
        activeOption.value = emp.id;
        activeOption.textContent = `${emp.name} - ${emp.designation}`;
        if (activeEmployees.includes(emp.id)) {
            activeOption.selected = true;
        }
        activeSelect.appendChild(activeOption);
        
        const onLeaveOption = document.createElement('option');
        onLeaveOption.value = emp.id;
        onLeaveOption.textContent = `${emp.name} - ${emp.designation}`;
        if (onLeaveEmployees.includes(emp.id)) {
            onLeaveOption.selected = true;
        }
        onLeaveSelect.appendChild(onLeaveOption);
    });
}

function updateEmployeeStatCards(employeeStats) {
    const container = document.getElementById('employee-stats-container');
    container.innerHTML = '';
    
    employeeStats.forEach(stat => {
        const card = document.createElement('div');
        card.className = 'emp-stat-card';
        card.dataset.employeeId = stat.employee_id;
        card.innerHTML = `
            <div class="emp-stat-header">
                <div class="emp-avatar" style="background: ${stat.color}; width: 28px; height: 28px; font-size: 11px;">${stat.initials}</div>
                <span class="emp-stat-title">${stat.name} - ${stat.designation}</span>
            </div>
            <div class="emp-stat-grid">
                <div class="form-group">
                    <label>Assigned</label>
                    <div class="stat-display ${stat.assigned === 0 ? 'zero' : ''}">${stat.assigned}</div>
                </div>
                <div class="form-group">
                    <label>Done</label>
                    <div class="stat-display ${stat.done === 0 ? 'zero' : ''}" style="color: #2ecc71;">${stat.done}</div>
                </div>
                <div class="form-group">
                    <label>Pending</label>
                    <div class="stat-display ${stat.pending === 0 ? 'zero' : ''}" style="color: #e74c3c;">${stat.pending}</div>
                </div>
                <div class="form-group">
                    <label>In Progress</label>
                    <div class="stat-display ${stat.in_progress === 0 ? 'zero' : ''}" style="color: #f1c40f;">${stat.in_progress}</div>
                </div>
            </div>
            <div style="margin-top: 10px; display: flex; gap: 15px;">
                <label class="checkbox-group">
                    <input type="checkbox" class="emp-task-updated" onchange="updatePreviewCounts()"> Task Updated
                </label>
                <label class="checkbox-group">
                    <input type="checkbox" class="emp-verify-pending" onchange="updatePreviewCounts()"> Verify Pending
                </label>
            </div>
        `;
        container.appendChild(card);
    });
}

function updatePreviewCounts() {
    // Count selected employees
    const activeSelect = document.getElementById('active-employees');
    const onLeaveSelect = document.getElementById('onleave-employees');
    
    const activeCount = Array.from(activeSelect.selectedOptions).filter(o => o.value).length;
    const onLeaveCount = Array.from(onLeaveSelect.selectedOptions).filter(o => o.value).length;
    
    document.getElementById('preview-active-count').textContent = `${activeCount} selected`;
    document.getElementById('preview-onleave-count').textContent = `${onLeaveCount} selected`;
    
    // Count checkboxes
    let tasksUpdatedCount = 0;
    let verifyPendingCount = 0;
    
    document.querySelectorAll('.emp-stat-card').forEach(card => {
        if (card.querySelector('.emp-task-updated').checked) tasksUpdatedCount++;
        if (card.querySelector('.emp-verify-pending').checked) verifyPendingCount++;
    });
    
    document.getElementById('preview-tasks-updated').textContent = tasksUpdatedCount;
    document.getElementById('preview-verified').textContent = dashboardStats.total_people - verifyPendingCount;
}

async function saveDashboard() {
    const date = document.getElementById('create-date').value;
    if (!date) {
        showMessage('dashboard-message', 'Please select a date', 'error');
        return;
    }
    
    // Get selected employees
    const activeSelect = document.getElementById('active-employees');
    const onLeaveSelect = document.getElementById('onleave-employees');
    
    const selectedActive = Array.from(activeSelect.selectedOptions).map(o => parseInt(o.value)).filter(v => v);
    const selectedOnLeave = Array.from(onLeaveSelect.selectedOptions).map(o => parseInt(o.value)).filter(v => v);
    
    // Validate no overlap
    const overlap = selectedActive.filter(id => selectedOnLeave.includes(id));
    if (overlap.length > 0) {
        showMessage('dashboard-message', 'Employees cannot be both Active and On Leave', 'error');
        return;
    }
    
    // Collect employee status
    const employeeStatus = [];
    selectedActive.forEach(id => employeeStatus.push({ employee_id: id, status: 'Active' }));
    selectedOnLeave.forEach(id => employeeStatus.push({ employee_id: id, status: 'On Leave' }));
    
    // Count checkboxes
    let tasksUpdatedCount = 0;
    let verifyPendingCount = 0;
    
    // Collect employee stats with checkboxes
    const empStats = [];
    document.querySelectorAll('.emp-stat-card').forEach(card => {
        const empId = parseInt(card.dataset.employeeId);
        const stat = dashboardStats.employee_stats.find(s => s.employee_id === empId);
        
        const taskUpdated = card.querySelector('.emp-task-updated').checked ? 1 : 0;
        const verifyPending = card.querySelector('.emp-verify-pending').checked ? 1 : 0;
        
        if (taskUpdated) tasksUpdatedCount++;
        if (verifyPending) verifyPendingCount++;
        
        empStats.push({
            date: date,
            employee_id: empId,
            assigned: stat ? stat.assigned : 0,
            done: stat ? stat.done : 0,
            pending: stat ? stat.pending : 0,
            in_progress: stat ? stat.in_progress : 0,
            completion_rate: stat ? stat.completion_rate : 0,
            task_updated: taskUpdated,
            verify_pending: verifyPending
        });
    });
    
    // Collect daily stats (auto-calculated)
    const stats = {
        total_people: dashboardStats.total_people,
        active_today: selectedActive.length,
        on_leave: selectedOnLeave.length,
        tasks_closed: dashboardStats.tasks_closed,
        total_assigned: dashboardStats.total_assigned,
        completed_today: dashboardStats.completed_today,
        pending_attention: dashboardStats.pending_attention,
        in_progress_count: dashboardStats.in_progress_count,
        tasks_updated: tasksUpdatedCount,
        verified_by_admin: dashboardStats.total_people - verifyPendingCount
    };
    
    try {
        // Save daily stats
        const statsResponse = await fetch(`/api/daily-stats/${date}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(stats)
        });
        
        // Save employee stats
        const empResponse = await fetch('/api/employee-daily-stats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(empStats)
        });
        
        // Save employee status (Active/On Leave)
        const statusResponse = await fetch(`/api/dashboard-employee-status/${date}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(employeeStatus)
        });
        
        const statsData = await statsResponse.json();
        const empData = await empResponse.json();
        const statusData = await statusResponse.json();
        
        if (statsData.success && empData.success && statusData.success) {
            showMessage('dashboard-message', 'Dashboard saved successfully!', 'success');
        } else {
            showMessage('dashboard-message', 'Error saving dashboard', 'error');
        }
    } catch (error) {
        showMessage('dashboard-message', 'Error saving dashboard', 'error');
    }
}

// Handle mutual exclusivity between Active and On Leave
function handleEmployeeSelection() {
    const activeSelect = document.getElementById('active-employees');
    const onLeaveSelect = document.getElementById('onleave-employees');
    
    activeSelect.addEventListener('change', () => {
        const activeSelected = Array.from(activeSelect.selectedOptions).map(o => o.value);
        // Remove from on-leave if selected in active
        Array.from(onLeaveSelect.options).forEach(opt => {
            if (activeSelected.includes(opt.value)) {
                opt.selected = false;
            }
        });
        updatePreviewCounts();
    });
    
    onLeaveSelect.addEventListener('change', () => {
        const onLeaveSelected = Array.from(onLeaveSelect.selectedOptions).map(o => o.value);
        // Remove from active if selected in on-leave
        Array.from(activeSelect.options).forEach(opt => {
            if (onLeaveSelected.includes(opt.value)) {
                opt.selected = false;
            }
        });
        updatePreviewCounts();
    });
}

// ============ TASK APIs ============
let allTasks = []; // Store all tasks for filtering

async function loadTasks(date, employeeId = null) {
    try {
        let url = `/api/tasks?date=${date}`;
        if (employeeId) url += `&employee_id=${employeeId}`;
        
        const response = await fetch(url);
        allTasks = await response.json();
        tasks = [...allTasks]; // Copy for display
        updateTaskList();
        updateEmployeeFilterDropdown();
        updateShowingCount();
    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

function updateTaskList() {
    const tbody = document.getElementById('task-list');
    tbody.innerHTML = '';
    
    tasks.forEach(task => {
        const row = document.createElement('tr');
        row.className = 'task-row';
        row.dataset.taskId = task.id;
        const verifiedClass = task.verified ? 'verified-yes' : 'verified-no';
        const verifiedText = task.verified ? 'Yes' : 'No';
        
        // Format created_at date
        const createdAt = task.created_at ? new Date(task.created_at).toLocaleString() : '-';
        
        row.innerHTML = `
            <td class="col-employee">${task.employee_name || 'Unknown'}</td>
            <td class="col-created">${createdAt}</td>
            <td class="col-task-name">${task.task_name}</td>
            <td class="col-status"><span class="status-badge status-${task.status.toLowerCase().replace(' ', '-')}">${task.status}</span></td>
            <td class="col-deadline">${task.deadline || '-'}</td>
            <td class="col-priority priority-${task.priority.toLowerCase()}">${task.priority}</td>
            <td class="col-verified ${verifiedClass}">${verifiedText}</td>
            <td class="actions">
                <button class="btn-small btn-edit" onclick="editTask(${task.id})">Edit</button>
                <button class="btn-small btn-update" onclick="quickUpdateTask(${task.id})">Update</button>
                <button class="btn-small btn-delete" onclick="deleteTask(${task.id})">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
    
    updateShowingCount();
}

function updateEmployeeFilterDropdown() {
    const filterSelect = document.getElementById('filter-employee');
    const currentValue = filterSelect.value;
    
    // Get unique employees from tasks
    const employeeMap = new Map();
    allTasks.forEach(task => {
        if (task.employee_id && task.employee_name) {
            employeeMap.set(task.employee_id, task.employee_name);
        }
    });
    
    // Clear and rebuild options
    filterSelect.innerHTML = '<option value="">All Employees</option>';
    employeeMap.forEach((name, id) => {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = name;
        filterSelect.appendChild(option);
    });
    
    filterSelect.value = currentValue;
}

function updateShowingCount() {
    const showing = tasks.length;
    const total = allTasks.length;
    document.getElementById('showing-count').textContent = `Showing ${showing} of ${total} tasks`;
}

// ============ COLUMN FILTERING ============
function applyColumnFilters() {
    const filters = {
        employee: document.getElementById('filter-employee').value,
        created: document.getElementById('filter-created').value.toLowerCase(),
        taskName: document.getElementById('filter-task-name').value.toLowerCase(),
        status: document.getElementById('filter-status').value,
        deadline: document.getElementById('filter-deadline').value.toLowerCase(),
        priority: document.getElementById('filter-priority').value,
        verified: document.getElementById('filter-verified').value
    };
    
    tasks = allTasks.filter(task => {
        // Employee filter
        if (filters.employee && task.employee_id != filters.employee) return false;
        
        // Created date filter
        if (filters.created) {
            const createdStr = task.created_at ? new Date(task.created_at).toLocaleString().toLowerCase() : '';
            if (!createdStr.includes(filters.created)) return false;
        }
        
        // Task name filter
        if (filters.taskName && !task.task_name.toLowerCase().includes(filters.taskName)) return false;
        
        // Status filter
        if (filters.status && task.status !== filters.status) return false;
        
        // Deadline filter
        if (filters.deadline && !(task.deadline || '').toLowerCase().includes(filters.deadline)) return false;
        
        // Priority filter
        if (filters.priority && task.priority !== filters.priority) return false;
        
        // Verified filter
        if (filters.verified) {
            const isVerified = task.verified ? 'Yes' : 'No';
            if (isVerified !== filters.verified) return false;
        }
        
        return true;
    });
    
    updateTaskList();
}

function applySearch() {
    const searchTerm = document.getElementById('search-all').value.toLowerCase();
    
    if (!searchTerm) {
        tasks = [...allTasks];
    } else {
        tasks = allTasks.filter(task => {
            const searchableText = [
                task.employee_name,
                task.created_at ? new Date(task.created_at).toLocaleString() : '',
                task.task_name,
                task.status,
                task.deadline,
                task.priority,
                task.notes,
                task.details
            ].join(' ').toLowerCase();
            
            return searchableText.includes(searchTerm);
        });
    }
    
    updateTaskList();
    highlightSearchMatches(searchTerm);
}

function highlightSearchMatches(searchTerm) {
    if (!searchTerm) return;
    
    const rows = document.querySelectorAll('#task-list tr');
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        cells.forEach(cell => {
            const text = cell.textContent;
            const regex = new RegExp(`(${searchTerm})`, 'gi');
            if (regex.test(text)) {
                cell.innerHTML = text.replace(regex, '<span class="highlight">$1</span>');
            }
        });
    });
}

function clearAllFilters() {
    document.getElementById('filter-employee').value = '';
    document.getElementById('filter-created').value = '';
    document.getElementById('filter-task-name').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-deadline').value = '';
    document.getElementById('filter-priority').value = '';
    document.getElementById('filter-verified').value = '';
    document.getElementById('search-all').value = '';
    
    tasks = [...allTasks];
    updateTaskList();
}

async function saveTask() {
    const taskData = {
        employee_id: document.getElementById('task-employee').value,
        date: document.getElementById('task-date').value,
        task_name: document.getElementById('task-name').value.trim(),
        details: document.getElementById('task-details').value.trim(),
        status: document.getElementById('task-status').value,
        deadline: document.getElementById('task-deadline').value,
        priority: document.getElementById('task-priority').value,
        notes: document.getElementById('task-notes').value.trim(),
        verified: document.getElementById('task-verified').value
    };
    
    // Validate deadline is required when status is "Deadline Extended"
    if (taskData.status === 'Deadline Extended' && !taskData.deadline) {
        showMessage('task-message', 'Deadline is required when status is "Deadline Extended"', 'error');
        document.getElementById('task-deadline').focus();
        return;
    }
    
    if (!taskData.employee_id || !taskData.task_name || !taskData.date) {
        showMessage('task-message', 'Please fill required fields (Employee, Task Name, Date)', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });
        
        const data = await response.json();
        if (data.success) {
            showMessage('task-message', 'Task created successfully!', 'success');
            resetTaskForm();
            loadTasks(document.getElementById('task-filter-date').value);
        } else {
            showMessage('task-message', data.error || 'Failed to create task', 'error');
        }
    } catch (error) {
        showMessage('task-message', 'Error creating task', 'error');
    }
}

function editTask(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    document.getElementById('edit-task-id').value = task.id;
    document.getElementById('edit-task-employee').value = task.employee_id;
    document.getElementById('edit-task-date').value = task.date;
    document.getElementById('edit-task-name').value = task.task_name;
    document.getElementById('edit-task-status').value = task.status;
    document.getElementById('edit-task-deadline').value = task.deadline || '';
    document.getElementById('edit-task-priority').value = task.priority;
    document.getElementById('edit-task-details').value = task.details || '';
    document.getElementById('edit-task-notes').value = task.notes || '';
    document.getElementById('edit-task-verified').value = task.verified ? 'Yes' : 'No';
    
    document.getElementById('edit-task-modal').style.display = 'flex';
}

async function updateTask() {
    const taskId = document.getElementById('edit-task-id').value;
    const status = document.getElementById('edit-task-status').value;
    const deadline = document.getElementById('edit-task-deadline').value;
    
    // Validate deadline is required when status is "Deadline Extended"
    if (status === 'Deadline Extended' && !deadline) {
        alert('Deadline is required when status is "Deadline Extended"');
        document.getElementById('edit-task-deadline').focus();
        return;
    }
    
    const taskData = {
        employee_id: document.getElementById('edit-task-employee').value,
        date: document.getElementById('edit-task-date').value,
        task_name: document.getElementById('edit-task-name').value.trim(),
        details: document.getElementById('edit-task-details').value.trim(),
        status: status,
        deadline: deadline,
        priority: document.getElementById('edit-task-priority').value,
        notes: document.getElementById('edit-task-notes').value.trim(),
        verified: document.getElementById('edit-task-verified').value
    };
    
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });
        
        const data = await response.json();
        if (data.success) {
            document.getElementById('edit-task-modal').style.display = 'none';
            loadTasks(document.getElementById('task-filter-date').value);
        }
    } catch (error) {
        console.error('Error updating task:', error);
    }
}

async function quickUpdateTask(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    const newStatus = prompt('Update Status:', task.status);
    if (newStatus === null) return;
    
    const newDeadline = prompt('Update Deadline:', task.deadline || '');
    if (newDeadline === null) return;
    
    const newVerified = confirm('Mark as Verified?') ? 'Yes' : 'No';
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/update-status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: newStatus,
                deadline: newDeadline,
                verified: newVerified
            })
        });
        
        const data = await response.json();
        if (data.success) {
            loadTasks(document.getElementById('task-filter-date').value);
        }
    } catch (error) {
        console.error('Error updating task:', error);
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    
    try {
        const response = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            loadTasks(document.getElementById('task-filter-date').value);
        }
    } catch (error) {
        console.error('Error deleting task:', error);
    }
}

function resetTaskForm() {
    document.getElementById('task-employee').value = '';
    document.getElementById('task-name').value = '';
    document.getElementById('task-details').value = '';
    document.getElementById('task-status').value = 'Pending';
    document.getElementById('task-deadline').value = '';
    document.getElementById('task-priority').value = 'Medium';
    document.getElementById('task-notes').value = '';
    document.getElementById('task-verified').value = 'No';
}

// ============ HISTORY APIs ============
function isToday(dateString) {
    const today = new Date().toISOString().split('T')[0];
    return dateString === today;
}

async function loadDashboardHistory() {
    const startDate = document.getElementById('history-start-date').value;
    const endDate = document.getElementById('history-end-date').value;
    
    try {
        let url = '/api/dashboard-history';
        if (startDate && endDate) {
            url += `?start_date=${startDate}&end_date=${endDate}`;
        }
        
        const response = await fetch(url);
        const history = await response.json();
        
        const tbody = document.getElementById('history-list');
        tbody.innerHTML = '';
        
        history.forEach(item => {
            const row = document.createElement('tr');
            const canEdit = isToday(item.date);
            row.innerHTML = `
                <td>${item.date}</td>
                <td>${item.total_people}</td>
                <td>${item.active_today}</td>
                <td>${item.on_leave}</td>
                <td>${item.tasks_closed}</td>
                <td>${item.completed_today}</td>
                <td>${item.pending_attention}</td>
                <td>${item.in_progress_count}</td>
                <td class="actions">
                    <button class="btn-small btn-edit" onclick="viewDashboard('${item.date}')">View</button>
                    ${canEdit ? `<button class="btn-small btn-primary" onclick="editDashboard('${item.date}')">Edit</button>` : ''}
                    <button class="btn-small btn-export" onclick="exportDashboard('${item.date}')">PDF</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// ============ EXPORT APIs ============
function exportDashboard(date) {
    window.open(`/api/export/dashboard/${date}`, '_blank');
}

function exportBulkDashboard() {
    const startDate = document.getElementById('history-start-date').value;
    const endDate = document.getElementById('history-end-date').value;
    
    if (!startDate || !endDate) {
        alert('Please select both start and end dates for bulk export');
        return;
    }
    
    window.open(`/api/export/dashboard-bulk?start_date=${startDate}&end_date=${endDate}`, '_blank');
}

function editDashboard(date) {
    document.getElementById('create-date').value = date;
    
    // Switch to create dashboard tab
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="create-dashboard"]').classList.add('active');
    document.getElementById('create-dashboard').classList.add('active');
    
    // Load the dashboard data for editing
    loadDashboardStatsForDate(date);
}

function viewDashboard(date) {
    document.getElementById('dashboard-date').value = date;
    
    // Switch to dashboard tab
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="dashboard"]').classList.add('active');
    document.getElementById('dashboard').classList.add('active');
    
    loadDashboard(date);
}

// ============ UTILITY FUNCTIONS ============
function showMessage(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `message ${type}`;
    
    setTimeout(() => {
        element.textContent = '';
        element.className = 'message';
    }, 3000);
}

// ============ EVENT LISTENERS ============
function setupEventListeners() {
    // Dashboard date change
    document.getElementById('dashboard-date').addEventListener('change', (e) => {
        loadDashboard(e.target.value);
    });
    
    // Export PDF
    document.getElementById('export-pdf').addEventListener('click', () => {
        const date = document.getElementById('dashboard-date').value;
        exportDashboard(date);
    });
    
    // Add Employee
    document.getElementById('add-employee').addEventListener('click', addEmployee);
    
    // Save Dashboard
    document.getElementById('save-dashboard').addEventListener('click', saveDashboard);
    
    // Toggle Task Form
    document.getElementById('toggle-task-form').addEventListener('click', () => {
        const container = document.getElementById('task-form-container');
        container.style.display = container.style.display === 'none' ? 'block' : 'none';
    });
    
    // Save Task
    document.getElementById('save-task').addEventListener('click', saveTask);
    
    // Cancel Task
    document.getElementById('cancel-task').addEventListener('click', () => {
        document.getElementById('task-form-container').style.display = 'none';
        resetTaskForm();
    });
    
    // Task filters
    document.getElementById('apply-filters').addEventListener('click', () => {
        const date = document.getElementById('task-filter-date').value;
        const empId = document.getElementById('task-filter-employee').value;
        loadTasks(date, empId || null);
    });
    
    // Update Task (Modal)
    document.getElementById('update-task-btn').addEventListener('click', updateTask);
    document.getElementById('close-edit-modal').addEventListener('click', () => {
        document.getElementById('edit-task-modal').style.display = 'none';
    });
    
    // History filters
    document.getElementById('apply-history-filters').addEventListener('click', loadDashboardHistory);
    document.getElementById('export-bulk').addEventListener('click', exportBulkDashboard);
    
    // Create Dashboard date change - load auto-calculated stats
    document.getElementById('create-date').addEventListener('change', async (e) => {
        const date = e.target.value;
        if (!date) return;
        await loadDashboardStatsForDate(date);
    });
    
    // Handle mutual exclusivity for Active/On Leave selection
    handleEmployeeSelection();
    
    // Column filters for task list
    document.getElementById('filter-employee').addEventListener('change', applyColumnFilters);
    document.getElementById('filter-created').addEventListener('input', applyColumnFilters);
    document.getElementById('filter-task-name').addEventListener('input', applyColumnFilters);
    document.getElementById('filter-status').addEventListener('change', applyColumnFilters);
    document.getElementById('filter-deadline').addEventListener('input', applyColumnFilters);
    document.getElementById('filter-priority').addEventListener('change', applyColumnFilters);
    document.getElementById('filter-verified').addEventListener('change', applyColumnFilters);
    document.getElementById('clear-filters').addEventListener('click', clearAllFilters);
    
    // Global search
    document.getElementById('search-all').addEventListener('input', applySearch);
    
    // Status change handlers for deadline validation UI
    document.getElementById('task-status').addEventListener('change', function() {
        const isExtended = this.value === 'Deadline Extended';
        document.getElementById('deadline-required').style.display = isExtended ? 'inline' : 'none';
        document.getElementById('deadline-hint').style.display = isExtended ? 'block' : 'none';
    });
    
    document.getElementById('edit-task-status').addEventListener('change', function() {
        const isExtended = this.value === 'Deadline Extended';
        document.getElementById('edit-deadline-required').style.display = isExtended ? 'inline' : 'none';
        document.getElementById('edit-deadline-hint').style.display = isExtended ? 'block' : 'none';
    });
}
