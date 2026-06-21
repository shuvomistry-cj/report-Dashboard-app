from flask import Flask, render_template, request, jsonify, send_file
from flask import make_response
from datetime import datetime, date
import sqlite3
import os
import json
import time
from io import BytesIO

# Try to import Playwright for PDF export
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not available. PDF export will be disabled.")

# Try to import psycopg2 for PostgreSQL
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dashboard-secret-key')

# Database configuration: PostgreSQL on Render (if DATABASE_URL exists), SQLite locally
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None and PSYCOPG2_AVAILABLE
DATABASE = 'dashboard.db'

def get_db_connection(max_retries=5, retry_delay=1):
    """Get database connection - PostgreSQL on Render, SQLite locally
    Includes retry logic for connection pool exhaustion at startup"""
    if USE_POSTGRES:
        for attempt in range(max_retries):
            try:
                conn = psycopg2.connect(DATABASE_URL, 
                                      connect_timeout=5,
                                      application_name="dashboard_app")
                conn.autocommit = False
                return conn
            except psycopg2.OperationalError as e:
                if "max clients reached" in str(e).lower() and attempt < max_retries - 1:
                    print(f"Connection pool exhausted, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                raise e
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

def close_db_connection(conn):
    """Safely close database connection"""
    try:
        if not conn:
            return
        if USE_POSTGRES:
            if not conn.closed:
                conn.close()
        else:
            conn.close()
    except Exception as e:
        print(f"Warning: database connection could not be closed: {e}")

def get_placeholder():
    """Return the right placeholder syntax for the database"""
    return '%s' if USE_POSTGRES else '?'

def format_query(query):
    """Convert ? placeholders to %s for PostgreSQL"""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query

def execute_insert_or_replace(c, table, columns, values, unique_column='date'):
    """Execute INSERT OR REPLACE for SQLite, INSERT ON CONFLICT for PostgreSQL"""
    if USE_POSTGRES:
        # PostgreSQL: INSERT ... ON CONFLICT DO UPDATE
        placeholders = ', '.join(['%s'] * len(values))
        col_list = ', '.join(columns)
        updates = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != unique_column])
        query = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT ({unique_column}) DO UPDATE SET {updates}"
        c.execute(query, values)
    else:
        # SQLite: INSERT OR REPLACE
        placeholders = ', '.join(['?'] * len(values))
        col_list = ', '.join(columns)
        query = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
        c.execute(query, values)

def get_lastrowid(c):
    """Get last inserted row id"""
    if USE_POSTGRES:
        c.execute("SELECT LASTVAL()")
        return c.fetchone()[0]
    return c.lastrowid

def init_db():
    """Initialize database tables - with retry for connection pool issues"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Use appropriate syntax for PostgreSQL vs SQLite
            if USE_POSTGRES:
                # PostgreSQL syntax
                c.execute('''CREATE TABLE IF NOT EXISTS employees (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    designation TEXT NOT NULL,
                    employee_type TEXT NOT NULL,
                    initials TEXT NOT NULL,
                    color TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS daily_stats (
                    id SERIAL PRIMARY KEY,
                    date DATE UNIQUE NOT NULL,
                    total_people INTEGER DEFAULT 0,
                    active_today INTEGER DEFAULT 0,
                    on_leave INTEGER DEFAULT 0,
                    tasks_closed INTEGER DEFAULT 0,
                    total_assigned INTEGER DEFAULT 0,
                    completed_today INTEGER DEFAULT 0,
                    pending_attention INTEGER DEFAULT 0,
                    in_progress_count INTEGER DEFAULT 0,
                    tasks_updated INTEGER DEFAULT 0,
                    verified_by_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS employee_daily_stats (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    employee_id INTEGER NOT NULL,
                    assigned INTEGER DEFAULT 0,
                    done INTEGER DEFAULT 0,
                    pending INTEGER DEFAULT 0,
                    in_progress INTEGER DEFAULT 0,
                    completion_rate INTEGER DEFAULT 0,
                    task_updated INTEGER DEFAULT 0,
                    verify_pending INTEGER DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees (id),
                    UNIQUE(date, employee_id)
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    details TEXT,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    deadline TEXT,
                    priority TEXT DEFAULT 'Medium',
                    notes TEXT,
                    verified INTEGER DEFAULT 0,
                    date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (employee_id) REFERENCES employees (id)
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS dashboard_employee_status (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    employee_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees (id),
                    UNIQUE(date, employee_id, status)
                )''')
            else:
                # SQLite syntax
                c.execute('''CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    designation TEXT NOT NULL,
                    employee_type TEXT NOT NULL,
                    initials TEXT NOT NULL,
                    color TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    total_people INTEGER DEFAULT 0,
                    active_today INTEGER DEFAULT 0,
                    on_leave INTEGER DEFAULT 0,
                    tasks_closed INTEGER DEFAULT 0,
                    total_assigned INTEGER DEFAULT 0,
                    completed_today INTEGER DEFAULT 0,
                    pending_attention INTEGER DEFAULT 0,
                    in_progress_count INTEGER DEFAULT 0,
                    tasks_updated INTEGER DEFAULT 0,
                    verified_by_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS employee_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    employee_id INTEGER NOT NULL,
                    assigned INTEGER DEFAULT 0,
                    done INTEGER DEFAULT 0,
                    pending INTEGER DEFAULT 0,
                    in_progress INTEGER DEFAULT 0,
                    completion_rate INTEGER DEFAULT 0,
                    task_updated INTEGER DEFAULT 0,
                    verify_pending INTEGER DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees (id),
                    UNIQUE(date, employee_id)
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    details TEXT,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    deadline TEXT,
                    priority TEXT DEFAULT 'Medium',
                    notes TEXT,
                    verified INTEGER DEFAULT 0,
                    date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (employee_id) REFERENCES employees (id)
                )''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS dashboard_employee_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    employee_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees (id),
                    UNIQUE(date, employee_id, status)
                )''')

            # Bring older databases forward without deleting or recreating tables.
            if USE_POSTGRES:
                c.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'Active'")
                c.execute("""SELECT column_name FROM information_schema.columns
                             WHERE table_name = 'daily_stats'""")
                daily_stats_columns = [row[0] for row in c.fetchall()]
                if 'verified_by_admin' not in daily_stats_columns:
                    if 'verified_by_lead' in daily_stats_columns:
                        c.execute("ALTER TABLE daily_stats RENAME COLUMN verified_by_lead TO verified_by_admin")
                    else:
                        c.execute("ALTER TABLE daily_stats ADD COLUMN verified_by_admin INTEGER DEFAULT 0")
            else:
                c.execute("PRAGMA table_info(employees)")
                employee_columns = [row[1] for row in c.fetchall()]
                if 'status' not in employee_columns:
                    c.execute("ALTER TABLE employees ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")
                c.execute("PRAGMA table_info(daily_stats)")
                daily_stats_columns = [row[1] for row in c.fetchall()]
                if 'verified_by_admin' not in daily_stats_columns:
                    if 'verified_by_lead' in daily_stats_columns:
                        c.execute("ALTER TABLE daily_stats RENAME COLUMN verified_by_lead TO verified_by_admin")
                    else:
                        c.execute("ALTER TABLE daily_stats ADD COLUMN verified_by_admin INTEGER DEFAULT 0")
            
            conn.commit()
            close_db_connection(conn)
            print("Database initialized successfully")
            return True
        except psycopg2.OperationalError as e:
            if "max clients reached" in str(e).lower() and attempt < max_retries - 1:
                print(f"Database init retry {attempt + 1}/{max_retries}...")
                time.sleep(2)
                continue
            print(f"Database initialization failed: {e}")
            return False
    return False

# Initialize database
init_db()

@app.route('/')
def index():
    return render_template('index.html')

# ============ EMPLOYEE APIs ============
@app.route('/api/employees', methods=['GET', 'POST'])
def employees():
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        department = data.get('department')
        designation = data.get('designation')
        employee_type = data.get('employee_type')
        status = data.get('status', 'Active')
        if not all([name, department, designation, employee_type]):
            close_db_connection(conn)
            return jsonify({'success': False, 'error': 'All employee fields are required'}), 400
        if status not in ('Active', 'Left'):
            close_db_connection(conn)
            return jsonify({'success': False, 'error': 'Invalid employee status'}), 400
        initials = ''.join([n[0] for n in name.split()[:2]]).upper()
        colors = ['#3498db', '#9b59b6', '#2ecc71', '#f39c12', '#e74c3c', '#1abc9c', '#34495e', '#16a085']
        color = colors[hash(name) % len(colors)]
        
        ph = get_placeholder()
        c.execute(format_query(f'''INSERT INTO employees (name, department, designation, employee_type, initials, color, status)
                     VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})'''),
                  (name, department, designation, employee_type, initials, color, status))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'success': True, 'message': 'Employee added successfully'})
    
    c.execute('''SELECT id, name, department, designation, employee_type, initials, color, status
                 FROM employees ORDER BY name''')
    employees = [{'id': row[0], 'name': row[1], 'department': row[2], 'designation': row[3], 
                  'employee_type': row[4], 'initials': row[5], 'color': row[6],
                  'status': row[7]} for row in c.fetchall()]
    close_db_connection(conn)
    return jsonify(employees)

@app.route('/api/employees/<int:emp_id>', methods=['PUT', 'DELETE'])
def employee_detail(emp_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(format_query('SELECT id FROM employees WHERE id = ?'), (emp_id,))
        if not c.fetchone():
            close_db_connection(conn)
            return jsonify({'success': False, 'error': 'Employee not found'}), 404

        if request.method == 'PUT':
            data = request.get_json() or {}
            name = (data.get('name') or '').strip()
            department = (data.get('department') or '').strip()
            designation = (data.get('designation') or '').strip()
            employee_type = data.get('employee_type')
            status = data.get('status', 'Active')
            if not all([name, department, designation, employee_type]):
                close_db_connection(conn)
                return jsonify({'success': False, 'error': 'All employee fields are required'}), 400
            if status not in ('Active', 'Left'):
                close_db_connection(conn)
                return jsonify({'success': False, 'error': 'Invalid employee status'}), 400

            initials = ''.join(part[0] for part in name.split()[:2]).upper()
            c.execute(format_query('''UPDATE employees
                        SET name = ?, department = ?, designation = ?, employee_type = ?,
                            initials = ?, status = ?
                        WHERE id = ?'''),
                      (name, department, designation, employee_type, initials, status, emp_id))
            conn.commit()
            close_db_connection(conn)
            return jsonify({'success': True, 'message': 'Employee updated successfully'})

        # Remove dependent records first so deletion behaves consistently in
        # SQLite and PostgreSQL and never leaves orphaned employee data.
        deleted = {}
        for table in ('tasks', 'employee_daily_stats', 'dashboard_employee_status'):
            c.execute(format_query(f'DELETE FROM {table} WHERE employee_id = ?'), (emp_id,))
            deleted[table] = c.rowcount
        c.execute(format_query('DELETE FROM employees WHERE id = ?'), (emp_id,))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'success': True, 'deleted_related_records': deleted})
    except Exception as e:
        conn.rollback()
        close_db_connection(conn)
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ DAILY STATS APIs ============
@app.route('/api/daily-stats/<date_str>', methods=['GET', 'POST', 'PUT'])
def daily_stats(date_str):
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST' or request.method == 'PUT':
        data = request.get_json()
        try:
            columns = ['date', 'total_people', 'active_today', 'on_leave', 'tasks_closed', 'total_assigned',
                     'completed_today', 'pending_attention', 'in_progress_count', 'tasks_updated', 'verified_by_admin']
            values = (date_str, data.get('total_people', 0), data.get('active_today', 0),
                     data.get('on_leave', 0), data.get('tasks_closed', 0), data.get('total_assigned', 0),
                     data.get('completed_today', 0), data.get('pending_attention', 0),
                     data.get('in_progress_count', 0), data.get('tasks_updated', 0),
                     data.get('verified_by_admin', 0))
            execute_insert_or_replace(c, 'daily_stats', columns, values, unique_column='date')
            conn.commit()
            close_db_connection(conn)
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            close_db_connection(conn)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    c.execute(format_query('SELECT * FROM daily_stats WHERE date = ?'), (date_str,))
    row = c.fetchone()
    close_db_connection(conn)
    
    if row:
        return jsonify({
            'id': row[0], 'date': row[1], 'total_people': row[2], 'active_today': row[3],
            'on_leave': row[4], 'tasks_closed': row[5], 'total_assigned': row[6],
            'completed_today': row[7], 'pending_attention': row[8], 'in_progress_count': row[9],
            'tasks_updated': row[10], 'verified_by_admin': row[11]
        })
    return jsonify(None)

# ============ EMPLOYEE DAILY STATS APIs ============
@app.route('/api/employee-daily-stats/<date_str>')
def employee_daily_stats(date_str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(format_query('''SELECT eds.*, e.name, e.designation, e.initials, e.color 
                  FROM employee_daily_stats eds
                  JOIN employees e ON eds.employee_id = e.id
                  WHERE eds.date = ?'''), (date_str,))
    rows = c.fetchall()
    close_db_connection(conn)
    
    stats = []
    for row in rows:
        stats.append({
            'id': row[0], 'employee_id': row[2], 'assigned': row[3], 'done': row[4],
            'pending': row[5], 'in_progress': row[6], 'completion_rate': row[7],
            'task_updated': row[8], 'verify_pending': row[9],
            'name': row[10], 'designation': row[11], 'initials': row[12], 'color': row[13]
        })
    return jsonify(stats)

@app.route('/api/employee-daily-stats', methods=['POST'])
def save_employee_daily_stats():
    data = request.get_json()
    conn = get_db_connection()
    c = conn.cursor()
    
    for stat in data:
        columns = ['date', 'employee_id', 'assigned', 'done', 'pending', 'in_progress', 'completion_rate', 'task_updated', 'verify_pending']
        values = (stat['date'], stat['employee_id'], stat['assigned'], stat['done'],
                 stat['pending'], stat['in_progress'], stat['completion_rate'],
                 stat.get('task_updated', 0), stat.get('verify_pending', 0))
        execute_insert_or_replace(c, 'employee_daily_stats', columns, values, unique_column='date, employee_id')
    
    conn.commit()
    close_db_connection(conn)
    return jsonify({'success': True})

# ============ TASK APIs ============
@app.route('/api/tasks', methods=['GET', 'POST'])
def tasks():
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.get_json() or {}
        task_items = data.get('tasks')
        if task_items is None:
            task_items = [data]
        if not isinstance(task_items, list) or not task_items:
            close_db_connection(conn)
            return jsonify({'success': False, 'error': 'Add at least one task'}), 400

        employee_id = data.get('employee_id')
        task_date = data.get('date')
        notes = data.get('notes', '')
        verified = data.get('verified', 'No')
        if not employee_id or not task_date:
            close_db_connection(conn)
            return jsonify({'success': False, 'error': 'Employee and date are required'}), 400

        c.execute(format_query("SELECT id FROM employees WHERE id = ? AND status = 'Active'"), (employee_id,))
        if not c.fetchone():
            close_db_connection(conn)
            return jsonify({'success': False, 'error': 'Select an active employee'}), 400

        allowed_statuses = ('Pending', 'In Progress', 'Done', 'Deadline Extended')
        allowed_priorities = ('Low', 'Medium', 'High')
        created_ids = []
        try:
            for item in task_items:
                task_name = (item.get('task_name') or '').strip()
                status = item.get('status', 'Pending')
                priority = item.get('priority', 'Medium')
                deadline = item.get('deadline') or task_date
                if not task_name:
                    raise ValueError('Every task must have a task name')
                if status not in allowed_statuses:
                    raise ValueError(f'Invalid task status: {status}')
                if priority not in allowed_priorities:
                    raise ValueError(f'Invalid task priority: {priority}')

                c.execute(format_query('''INSERT INTO tasks
                            (employee_id, task_name, details, status, deadline, priority, notes, verified, date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'''),
                          (employee_id, task_name, item.get('details', ''), status, deadline,
                           priority, notes, 1 if verified == 'Yes' else 0, task_date))
                created_ids.append(get_lastrowid(c))
            conn.commit()
            close_db_connection(conn)
            return jsonify({'success': True, 'ids': created_ids, 'count': len(created_ids)})
        except (ValueError, KeyError) as e:
            conn.rollback()
            close_db_connection(conn)
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            conn.rollback()
            close_db_connection(conn)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # GET with filters
    date_filter = request.args.get('date', date.today().isoformat())
    emp_filter = request.args.get('employee_id')
    
    if emp_filter:
        c.execute(format_query('''SELECT t.*, e.name as employee_name, e.designation 
                      FROM tasks t 
                      JOIN employees e ON t.employee_id = e.id
                      WHERE t.date = ? AND t.employee_id = ? 
                      ORDER BY t.created_at DESC'''), (date_filter, emp_filter))
    else:
        c.execute(format_query('''SELECT t.*, e.name as employee_name, e.designation 
                      FROM tasks t 
                      JOIN employees e ON t.employee_id = e.id
                      WHERE t.date = ? 
                      ORDER BY t.created_at DESC'''), (date_filter,))
    
    rows = c.fetchall()
    close_db_connection(conn)
    
    tasks_list = []
    for row in rows:
        tasks_list.append({
            'id': row[0], 'employee_id': row[1], 'task_name': row[2], 'details': row[3],
            'status': row[4], 'deadline': row[5], 'priority': row[6], 'notes': row[7],
            'verified': row[8], 'date': row[9], 'created_at': row[10], 'updated_at': row[11],
            'employee_name': row[12], 'designation': row[13]
        })
    return jsonify(tasks_list)

@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
def task_detail(task_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'PUT':
        data = request.get_json()
        c.execute(format_query("SELECT id FROM employees WHERE id = ? AND status = 'Active'"),
                  (data.get('employee_id'),))
        if not c.fetchone():
            close_db_connection(conn)
            return jsonify({'success': False, 'error': 'Select an active employee'}), 400
        # Handle empty deadline for PostgreSQL
        deadline = data.get('deadline') if data.get('deadline') else None
        
        # Only update editable fields, preserve original date (don't update date field)
        c.execute(format_query('''UPDATE tasks SET employee_id=?, task_name=?, details=?, status=?, 
                    deadline=?, priority=?, notes=?, verified=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?'''),
                  (data['employee_id'], data['task_name'], data.get('details', ''),
                   data.get('status', 'Pending'), deadline,
                   data.get('priority', 'Medium'), data.get('notes', ''),
                   1 if data.get('verified') == 'Yes' else 0, task_id))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        c.execute(format_query('DELETE FROM tasks WHERE id = ?'), (task_id,))
        conn.commit()
        close_db_connection(conn)
        return jsonify({'success': True})

@app.route('/api/tasks/<int:task_id>/update-status', methods=['PUT'])
def update_task_status(task_id):
    data = request.get_json()
    conn = get_db_connection()
    c = conn.cursor()
    # Handle empty deadline for PostgreSQL
    deadline = data.get('deadline') if data.get('deadline') else None
    c.execute(format_query('''UPDATE tasks SET status=?, deadline=?, verified=?, updated_at=CURRENT_TIMESTAMP
                 WHERE id=?'''),
              (data.get('status'), deadline, 1 if data.get('verified') == 'Yes' else 0, task_id))
    conn.commit()
    close_db_connection(conn)
    return jsonify({'success': True})

# ============ DASHBOARD DATA API ============
@app.route('/api/dashboard/<date_str>')
def get_dashboard(date_str):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get daily stats
    c.execute(format_query('SELECT * FROM daily_stats WHERE date = ?'), (date_str,))
    stats_row = c.fetchone()
    
    # Get task counts by status for deadline extended calculation
    c.execute(format_query('''SELECT status, COUNT(*) FROM tasks WHERE date = ? GROUP BY status'''), (date_str,))
    task_counts = {row[0]: row[1] for row in c.fetchall()}
    deadline_extended_count = task_counts.get('Deadline Extended', 0)
    
    # Get employee stats with tasks (including deadline extended count)
    c.execute(format_query('''SELECT 
                    eds.id, eds.date, eds.employee_id, eds.assigned, eds.done, eds.pending, 
                    eds.in_progress, eds.completion_rate, eds.task_updated, eds.verify_pending,
                    e.name, e.designation, e.initials, e.color,
                    SUM(CASE WHEN t.status = 'Deadline Extended' THEN 1 ELSE 0 END) as deadline_extended
                  FROM employee_daily_stats eds
                  JOIN employees e ON eds.employee_id = e.id
                  LEFT JOIN tasks t ON e.id = t.employee_id AND t.date = ?
                  WHERE eds.date = ?
                  GROUP BY eds.id, e.name, e.designation, e.initials, e.color'''), (date_str, date_str))
    emp_stats = c.fetchall()
    
    # Get pending, in-progress, and deadline extended tasks
    c.execute(format_query('''SELECT t.*, e.name as employee_name 
                  FROM tasks t 
                  JOIN employees e ON t.employee_id = e.id
                  WHERE t.date = ? AND t.status IN ('In Progress', 'Pending', 'Deadline Extended')
                  ORDER BY CASE t.priority 
                    WHEN 'High' THEN 1 
                    WHEN 'Medium' THEN 2 
                    WHEN 'Low' THEN 3 
                  END'''), (date_str,))
    pending_tasks = c.fetchall()
    
    close_db_connection(conn)
    
    dashboard = {
        'stats': None,
        'employee_breakdown': [],
        'pending_tasks': []
    }
    
    if stats_row:
        dashboard['stats'] = {
            'total_people': stats_row[2], 'active_today': stats_row[3], 'on_leave': stats_row[4],
            'tasks_closed': stats_row[5], 'total_assigned': stats_row[6],
            'completed_today': stats_row[7], 'pending_attention': stats_row[8],
            'in_progress_count': stats_row[9], 'tasks_updated': stats_row[10], 
            'verified_by_admin': stats_row[11], 'deadline_extended_count': deadline_extended_count
        }
    
    for row in emp_stats:
        dashboard['employee_breakdown'].append({
            'employee_id': row[2], 'assigned': row[3], 'done': row[4], 'pending': row[5],
            'in_progress': row[6], 'completion_rate': row[7], 'task_updated': row[8],
            'verify_pending': row[9], 'name': row[10], 'designation': row[11],
            'initials': row[12], 'color': row[13], 'deadline_extended': row[14] or 0
        })
    
    for row in pending_tasks:
        dashboard['pending_tasks'].append({
            'id': row[0], 'employee_name': row[11], 'task_name': row[2],
            'status': row[4], 'deadline': row[5], 'priority': row[6], 'notes': row[7]
        })
    
    return jsonify(dashboard)

# ============ PDF EXPORT APIs ============
@app.route('/api/export/dashboard/<date_str>')
def export_dashboard_pdf(date_str):
    if not PLAYWRIGHT_AVAILABLE:
        return jsonify({'error': 'PDF export not available. Install Playwright to enable PDF export.'}), 503
    
    dashboard = get_dashboard(date_str).get_json()
    
    # Render HTML template
    html_content = render_template('dashboard_pdf.html', 
                                   date=date_str, 
                                   dashboard=dashboard)
    
    # Use Playwright to convert HTML to PDF
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        pdf = page.pdf(format='A4', print_background=True)
        browser.close()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=dashboard_{date_str}.pdf'
    return response

@app.route('/api/export/tasks')
def export_tasks_pdf():
    """Export tasks to PDF with optional filters"""
    if not PLAYWRIGHT_AVAILABLE:
        return jsonify({'error': 'PDF export not available. Install Playwright to enable PDF export.'}), 503
    
    # Get filter parameters
    date_filter = request.args.get('date', '')
    employee_filter = request.args.get('employee_id', '')
    status_filter = request.args.get('status', '')
    
    # Build query based on filters
    conn = get_db_connection()
    c = conn.cursor()
    
    query = '''SELECT t.*, e.name as employee_name, e.designation 
               FROM tasks t 
               JOIN employees e ON t.employee_id = e.id
               WHERE 1=1'''
    params = []
    
    if date_filter:
        query += ' AND t.date = ?'
        params.append(date_filter)
    if employee_filter:
        query += ' AND t.employee_id = ?'
        params.append(employee_filter)
    if status_filter:
        query += ' AND t.status = ?'
        params.append(status_filter)
    
    query += ' ORDER BY t.created_at DESC'
    
    c.execute(format_query(query), tuple(params))
    rows = c.fetchall()
    close_db_connection(conn)
    
    tasks = []
    for row in rows:
        tasks.append({
            'id': row[0], 'employee_id': row[1], 'task_name': row[2], 'details': row[3],
            'status': row[4], 'deadline': row[5], 'priority': row[6], 'notes': row[7],
            'verified': row[8], 'date': row[9], 'created_at': row[10],
            'employee_name': row[12], 'designation': row[13]
        })
    
    # Render HTML template for tasks
    html_content = render_template('tasks_pdf.html', 
                                   tasks=tasks,
                                   date_filter=date_filter,
                                   employee_filter=employee_filter,
                                   status_filter=status_filter)
    
    # Use Playwright to convert HTML to PDF
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        pdf = page.pdf(format='A4', print_background=True)
        browser.close()
    
    # Build filename based on filters
    filename_parts = ['tasks']
    if date_filter:
        filename_parts.append(date_filter)
    if employee_filter:
        filename_parts.append(f'emp{employee_filter}')
    if status_filter:
        filename_parts.append(status_filter.replace(' ', '_'))
    
    filename = '_'.join(filename_parts) + '.pdf'
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@app.route('/api/export/dashboard-bulk')
def export_dashboard_bulk():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(format_query('''SELECT * FROM daily_stats 
                  WHERE date BETWEEN ? AND ? 
                  ORDER BY date DESC'''), (start_date, end_date))
    rows = c.fetchall()
    close_db_connection(conn)
    
    dashboards = []
    for row in rows:
        dashboards.append({
            'date': row[1], 'total_people': row[2], 'active_today': row[3], 'on_leave': row[4],
            'tasks_closed': row[5], 'total_assigned': row[6], 'completed_today': row[7],
            'pending_attention': row[8], 'in_progress_count': row[9], 'tasks_updated': row[10],
            'verified_by_admin': row[11]
        })
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#3498db'),
        spaceAfter=20,
        alignment=1
    )
    
    elements.append(Paragraph(f"Dashboard Reports: {start_date} to {end_date}", title_style))
    elements.append(Spacer(1, 20))
    
    # Summary table for all dashboards
    summary_data = [['Date', 'Total', 'Active', 'On Leave', 'Completed', 'Pending', 'In Progress']]
    for d in dashboards:
        summary_data.append([
            d['date'], str(d['total_people']), str(d['active_today']), str(d['on_leave']),
            str(d['completed_today']), str(d['pending_attention']), str(d['in_progress_count'])
        ])
    
    summary_table = Table(summary_data, colWidths=[70, 50, 50, 50, 70, 70, 70])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor('#ecf0f1')])
    ]))
    
    elements.append(summary_table)
    
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=dashboards_{start_date}_to_{end_date}.pdf'
    return response

# ============ AUTO-CALCULATED DASHBOARD STATS API ============
@app.route('/api/dashboard-stats/<date_str>')
def get_dashboard_stats(date_str):
    """Get auto-calculated statistics for dashboard creation"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Left employees remain in history but are excluded from new dashboards.
    c.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active'")
    total_people = c.fetchone()[0]
    
    # Get task counts by status for the date
    c.execute(format_query('''SELECT status, COUNT(*) FROM tasks WHERE date = ? GROUP BY status'''), (date_str,))
    task_counts = {row[0]: row[1] for row in c.fetchall()}
    
    total_assigned = sum(task_counts.values())
    completed_today = task_counts.get('Done', 0)
    pending_attention = task_counts.get('Pending', 0)
    in_progress_count = task_counts.get('In Progress', 0)
    deadline_extended_count = task_counts.get('Deadline Extended', 0)
    tasks_closed = completed_today  # Tasks marked as done are considered closed
    
    # Get employee task breakdown
    c.execute(format_query('''SELECT 
                    e.id, e.name, e.designation, e.initials, e.color,
                    COUNT(t.id) as assigned,
                    SUM(CASE WHEN t.status = 'Done' THEN 1 ELSE 0 END) as done,
                    SUM(CASE WHEN t.status = 'Pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN t.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress
                 FROM employees e
                 LEFT JOIN tasks t ON e.id = t.employee_id AND t.date = ?
                 WHERE e.status = 'Active'
                 GROUP BY e.id'''), (date_str,))
    
    employee_stats = []
    for row in c.fetchall():
        assigned = row[5] or 0
        done = row[6] or 0
        completion_rate = round((done / assigned * 100)) if assigned > 0 else 0
        employee_stats.append({
            'employee_id': row[0],
            'name': row[1],
            'designation': row[2],
            'initials': row[3],
            'color': row[4],
            'assigned': assigned,
            'done': done,
            'pending': row[7] or 0,
            'in_progress': row[8] or 0,
            'completion_rate': completion_rate
        })
    
    close_db_connection(conn)
    
    return jsonify({
        'total_people': total_people,
        'total_assigned': total_assigned,
        'completed_today': completed_today,
        'pending_attention': pending_attention,
        'in_progress_count': in_progress_count,
        'deadline_extended_count': deadline_extended_count,
        'tasks_closed': tasks_closed,
        'employee_stats': employee_stats
    })

# ============ DASHBOARD EMPLOYEE STATUS APIs ============
@app.route('/api/dashboard-employee-status/<date_str>', methods=['GET', 'POST'])
def dashboard_employee_status(date_str):
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.get_json() or []
        try:
            employee_ids = [item.get('employee_id') for item in data]
            if any(item.get('status') not in ('Active', 'On Leave') for item in data):
                raise ValueError('Invalid attendance status')

            if employee_ids:
                placeholders = ', '.join([get_placeholder()] * len(employee_ids))
                c.execute(format_query(
                    f"SELECT id FROM employees WHERE status = 'Active' AND id IN ({placeholders})"
                ), tuple(employee_ids))
                active_ids = {row[0] for row in c.fetchall()}
                if active_ids != set(employee_ids):
                    raise ValueError('Left employees cannot be added to attendance or leave')

            c.execute(format_query('DELETE FROM dashboard_employee_status WHERE date = ?'), (date_str,))
            for item in data:
                c.execute(format_query('''INSERT INTO dashboard_employee_status (date, employee_id, status)
                            VALUES (?, ?, ?)'''),
                          (date_str, item['employee_id'], item['status']))
            conn.commit()
            close_db_connection(conn)
            return jsonify({'success': True})
        except (ValueError, KeyError) as e:
            conn.rollback()
            close_db_connection(conn)
            return jsonify({'success': False, 'error': str(e)}), 400
        except Exception as e:
            conn.rollback()
            close_db_connection(conn)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # GET - return active and on leave employee lists
    c.execute(format_query('''SELECT des.employee_id, des.status
                  FROM dashboard_employee_status des
                  JOIN employees e ON e.id = des.employee_id
                  WHERE des.date = ? AND e.status = 'Active' '''), (date_str,))
    rows = c.fetchall()
    close_db_connection(conn)
    
    active_employees = [row[0] for row in rows if row[1] == 'Active']
    on_leave_employees = [row[0] for row in rows if row[1] == 'On Leave']
    
    return jsonify({
        'active_employees': active_employees,
        'on_leave_employees': on_leave_employees
    })

# ============ DASHBOARD HISTORY ============
@app.route('/api/dashboard-history')
def dashboard_history():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    if start_date and end_date:
        c.execute(format_query('''SELECT * FROM daily_stats 
                      WHERE date BETWEEN ? AND ? 
                      ORDER BY date DESC'''), (start_date, end_date))
    else:
        c.execute('SELECT * FROM daily_stats ORDER BY date DESC')
    
    rows = c.fetchall()
    close_db_connection(conn)
    
    history = []
    for row in rows:
        history.append({
            'id': row[0], 'date': row[1], 'total_people': row[2], 'active_today': row[3],
            'on_leave': row[4], 'tasks_closed': row[5], 'total_assigned': row[6],
            'completed_today': row[7], 'pending_attention': row[8], 'in_progress_count': row[9],
            'tasks_updated': row[10], 'verified_by_admin': row[11]
        })
    return jsonify(history)

@app.route('/api/debug/db-status')
def db_status():
    """Debug endpoint to check database connection"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT version()")
        version = c.fetchone()[0]
        close_db_connection(conn)
        return jsonify({
            'connected': True,
            'database_type': 'PostgreSQL' if USE_POSTGRES else 'SQLite',
            'version': version
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
