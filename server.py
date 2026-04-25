import os
import re
import json
import database
from datetime import datetime
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for, jsonify
import secrets
from werkzeug.exceptions import RequestEntityTooLarge



database.init_db()   # 启动时确保表存在

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)   # 每次启动自动生成新的，或者固定写一个

# ---------- 从 config.json 读取最大文件大小限制 ----------
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
max_mb = config.get('max_file_size_mb', 100)
app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024  # 转换为字节
# --------------------------------------------------------

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def is_safe_path(user_path):
    """确保路径安全，防止路径穿越"""
    # 标准化路径
    abs_base = os.path.abspath(UPLOAD_FOLDER)
    abs_user = os.path.abspath(os.path.join(abs_base, user_path))
    return abs_user.startswith(abs_base)

def normalize_path(path):
    """标准化路径：确保以 / 开头和结尾"""
    if not path:
        return ''
    path = path.replace('\\', '/')
    # 防止 .. 穿越
    parts = [p for p in path.split('/') if p and p != '..']
    result = '/'.join(parts)
    if result and not result.endswith('/'):
        result += '/'
    return result

@app.route('/')
def index():
    current_path = normalize_path(request.args.get('path', ''))
    if not is_safe_path(current_path):
        return "非法路径", 400

    folders = database.get_folders(current_path)
    files = database.get_files_by_path(current_path)
    return render_template('index.html',
                           files=files,
                           folders=folders,
                           current_path=current_path,
                           max_content_length=app.config['MAX_CONTENT_LENGTH'])


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理上传的文件并保存到服务器"""
    current_path = normalize_path(request.form.get('path', ''))

    if not is_safe_path(current_path):
        return jsonify(success=False, message='非法路径'), 400

    if 'file' not in request.files:
        return jsonify(success=False, message='没有选择文件'), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, message='文件名为空'), 400

    original_name = file.filename
    # 获取原始扩展名（带点，如 ".png"）
    _, ext = os.path.splitext(file.filename)
    # 生成时间戳字符串，例如 "20260414153012"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    stored_filename = timestamp + ext

    # 确保目标目录存在
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_path)
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, stored_filename)
    file.save(file_path)
    size = os.path.getsize(file_path)
    database.add_file_record(original_name, stored_filename, size, file.mimetype, file_path, current_path)
    return jsonify(success=True, message=f'文件 "{original_name}" 上传成功！'), 200

@app.route('/files')
def list_files():
    current_path = normalize_path(request.args.get('path', ''))
    if not is_safe_path(current_path):
        return "非法路径", 400

    folders = database.get_folders(current_path)
    files = database.get_files_by_path(current_path)
    return render_template('files.html', files=files, folders=folders, current_path=current_path)

@app.route('/create-folder', methods=['POST'])
def create_folder():
    parent_path = normalize_path(request.form.get('path', ''))
    folder_name = request.form.get('folder_name', '').strip()

    if not folder_name:
        return jsonify(success=False, message='文件夹名不能为空'), 400

    # 检查非法字符
    if re.search(r'[/\\:*?"<>|]', folder_name):
        return jsonify(success=False, message='文件夹名包含非法字符'), 400

    new_path = parent_path + folder_name + '/'

    if not is_safe_path(new_path):
        return jsonify(success=False, message='非法路径'), 400

    # 物理创建目录
    full_dir = os.path.join(app.config['UPLOAD_FOLDER'], new_path)
    os.makedirs(full_dir, exist_ok=True)

    # 数据库记录
    database.add_folder(new_path)

    return jsonify(success=True, message='文件夹创建成功！'), 200


@app.route('/download/<int:file_id>')
def download_file(file_id):
    # 1. 根据 ID 获取文件记录
    record = database.get_file_by_id(file_id)
    if record is None:
        return "文件不存在", 404

    # record 结构：(id, original_filename, stored_filename, size, type, upload_time, path, relative_path)
    stored_filename = record[2]          # 存储文件名
    original_filename = record[1]        # 用户上传时的原始文件名
    relative_path = record[7] if len(record) > 7 else ''  # 相对路径

    # 拼接完整目录
    file_dir = os.path.join(app.config['UPLOAD_FOLDER'], relative_path)

    # 发送文件
    return send_from_directory(
        file_dir,
        stored_filename,
        as_attachment=True,
        download_name=original_filename
    )

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify(success=False, message=f"文件过大，请上传小于 {max_mb} MB 的文件~"), 413

if __name__ == '__main__':
    app.run(debug=True)