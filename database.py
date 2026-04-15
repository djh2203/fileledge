# database.py
import sqlite3
import datetime

DATABASE = 'uploads.db'

def init_db():
    """初始化数据库：创建 files 表（如果不存在）"""
    # 1. 连接数据库（文件不存在时会自动创建）
    conn = sqlite3.connect(DATABASE)
    # 2. 创建一个“游标”对象，用来执行 SQL 语句
    cursor = conn.cursor()
    # 3. 执行建表语句
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT,
            upload_time TEXT NOT NULL,
            file_path TEXT NOT NULL
        )
    ''')
    # 4. 提交事务（把改动真正保存到文件）
    conn.commit()
    # 5. 关闭连接
    conn.close()
    
def add_file_record(original_name, stored_name, size, mime_type, saved_path):
    """插入一条文件上传记录"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # 获取当前时间（ISO 格式字符串）
    upload_time = datetime.datetime.now().isoformat()
    # 执行插入语句，用 ? 作为占位符（防 SQL 注入）
    cursor.execute('''
        INSERT INTO files 
        (original_filename, stored_filename, file_size, file_type, upload_time, file_path)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (original_name, stored_name, size, mime_type, upload_time, saved_path))
    conn.commit()
    conn.close()

