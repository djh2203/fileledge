# database.py
import os
import sqlite3
import datetime

DATABASE = os.path.join('instance', 'uploads.db')

def init_db():
    """初始化数据库：创建所需的表（如果不存在）"""
    os.makedirs('instance', exist_ok=True)   # 自动创建 instance 目录
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")   # 开启外键约束

    # 用户表（增加 role 字段）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    ''')

    # 文件表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT,
            upload_time TEXT NOT NULL,
            file_path TEXT NOT NULL,
            relative_path TEXT NOT NULL DEFAULT '',
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # 文件夹表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_path TEXT NOT NULL,
            created_time TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(folder_path, user_id)
        )
    ''')

    conn.commit()
    conn.close()


# ---------- 用户相关操作 ----------
def get_user_count():
    """返回用户总数（用于判断是否已初始化）"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def create_user(username, password_hash, role='user'):
    """
    创建新用户，返回新用户的 id，如果用户名已存在则返回 None
    role 默认为 'user'，初始化管理员时可传入 'admin'
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash, role, created_at))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    """根据用户名查找用户，返回 (id, username, password_hash, role, created_at) 或 None"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, password_hash, role, created_at FROM users WHERE username = ?",
        (username,)
    )
    row = cursor.fetchone()
    conn.close()
    return row

def get_user_by_id(user_id):
    """根据用户 ID 查找用户，返回 (id, username, password_hash, role, created_at) 或 None"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, password_hash, role, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_users():
    """获取所有用户列表（管理员查看用），不返回密码哈希"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return rows


# ---------- 文件操作 ----------
def add_file_record(original_name, stored_name, size, mime_type, saved_path, relative_path, user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    upload_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute('''
        INSERT INTO files
        (original_filename, stored_filename, file_size, file_type, upload_time, file_path, relative_path, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (original_name, stored_name, size, mime_type, upload_time, saved_path, relative_path, user_id))
    conn.commit()
    conn.close()

def get_files_by_path(relative_path, user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM files WHERE relative_path = ? AND user_id = ? ORDER BY id DESC",
        (relative_path, user_id)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_file_by_id(file_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_files():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_file_by_id_admin(file_id):
    """获取任意用户的文件记录（管理员用）"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def delete_file_record(file_id):
    """删除一条文件记录，返回 (stored_filename, relative_path, user_id) 或 None"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT stored_filename, relative_path, user_id FROM files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return None
    cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    return row   # (stored_name, relative_path, user_id)


def delete_folder_and_files(folder_path, user_id):
    """
    删除指定用户下某个文件夹及其所有子文件/子文件夹（数据库记录）
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # 删除所有以该路径开头的文件夹
    cursor.execute(
        "DELETE FROM folders WHERE folder_path LIKE ? AND user_id = ?",
        (folder_path + '%', user_id)
    )
    # 删除所有以该路径开头的文件
    cursor.execute(
        "DELETE FROM files WHERE relative_path LIKE ? AND user_id = ?",
        (folder_path + '%', user_id)
    )
    conn.commit()
    conn.close()


# ---------- 文件夹操作 ----------
def add_folder(folder_path, user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    created_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute('''
        INSERT OR IGNORE INTO folders (folder_path, created_time, user_id) VALUES (?, ?, ?)
    ''', (folder_path, created_time, user_id))
    conn.commit()
    conn.close()

def get_folders(relative_path, user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT folder_path FROM folders WHERE user_id = ?",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    subfolders = []
    for row in rows:
        path = row[0]
        if not path.startswith(relative_path):
            continue
        rest = path[len(relative_path):]
        if not rest or rest == '/':
            continue
        parts = rest.strip('/').split('/')
        if parts and parts[0]:
            name = parts[0]
            full_path = relative_path + name + '/'
            if name not in [s['name'] for s in subfolders]:
                subfolders.append({'name': name, 'path': full_path})
    return subfolders