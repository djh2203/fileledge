# database.py
import sqlite3
import datetime

DATABASE = 'uploads.db'

def init_db():
    """初始化数据库：创建所需的表（如果不存在）"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # 文件表（增加 user_id）
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

    # 文件夹表（增加 user_id）
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
def create_user(username, password_hash):
    """创建新用户，返回新用户的 id，如果用户名已存在则返回 None"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    created_at = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
        ''', (username, password_hash, created_at))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        # 用户名重复
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    """根据用户名查找用户，返回 (id, username, password_hash, created_at) 或 None"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, created_at FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_user_by_id(user_id):
    """根据用户 ID 查找用户"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row


# ---------- 文件操作（全部加上 user_id） ----------
def add_file_record(original_name, stored_name, size, mime_type, saved_path, relative_path, user_id):
    """插入一条文件上传记录"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    upload_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    cursor.execute('''
        INSERT INTO files
        (original_filename, stored_filename, file_size, file_type, upload_time, file_path, relative_path, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (original_name, stored_name, size, mime_type, upload_time, saved_path, relative_path, user_id))
    conn.commit()
    conn.close()

def get_files_by_path(relative_path, user_id):
    """返回指定路径下的所有文件记录（仅限当前用户）"""
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
    """根据 ID 获取文件记录（不验证用户，调用方需要自己检查权限）"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_files():
    """返回所有文件记录（兼容旧调用，之后不会被用到）"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


# ---------- 文件夹操作（加上 user_id） ----------
def add_folder(folder_path, user_id):
    """插入文件夹记录"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    created_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    cursor.execute('''
        INSERT OR IGNORE INTO folders (folder_path, created_time, user_id) VALUES (?, ?, ?)
    ''', (folder_path, created_time, user_id))
    conn.commit()
    conn.close()

def get_folders(relative_path, user_id):
    """返回指定路径下的直接子文件夹（仅限当前用户）"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # 先获取当前用户的所有文件夹，再在 Python 里过滤
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