# server.py
import os
import re
import json
import secrets
import database
from datetime import datetime
from functools import wraps
from flask import (
    Flask, request, render_template, send_from_directory,
    redirect, url_for, jsonify, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge

database.init_db()   # 启动时确保表存在

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)   # 生产环境请改为固定强密码

# ---------- 从 config.json 读取最大文件大小限制 ----------
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
max_mb = config.get('max_file_size_mb', 100)
app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------- 辅助函数 ----------
def is_safe_path(user_path):
    abs_base = os.path.abspath(app.config['UPLOAD_FOLDER'])
    abs_user = os.path.abspath(os.path.join(abs_base, user_path))
    return abs_user.startswith(abs_base)

def normalize_path(path):
    if not path:
        return ''
    path = path.replace('\\', '/')
    parts = [p for p in path.split('/') if p and p != '..']
    result = '/'.join(parts)
    if result and not result.endswith('/'):
        result += '/'
    return result

def login_required(view_func):
    """装饰器：要求用户已登录"""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapper

# ---------- 简单 CSRF 保护 ----------
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

def verify_csrf_token(token):
    return token and token == session.get('csrf_token')

# 使 csrf_token 在所有模板中可用
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())


# ---------- 认证相关路由 ----------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 验证 CSRF
        if not verify_csrf_token(request.form.get('csrf_token')):
            return jsonify(success=False, message='非法请求'), 400

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        # 基础校验
        if not username or not password:
            return jsonify(success=False, message='用户名和密码不能为空'), 400
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            return jsonify(success=False, message='用户名需为3-20位字母、数字或下划线'), 400
        if len(password) < 6:
            return jsonify(success=False, message='密码至少6位'), 400
        if password != confirm:
            return jsonify(success=False, message='两次密码不一致'), 400

        # 创建用户
        password_hash = generate_password_hash(password)
        user_id = database.create_user(username, password_hash)
        if user_id is None:
            return jsonify(success=False, message='用户名已存在'), 400

        # 自动登录
        session.clear()
        session['user_id'] = user_id
        session['username'] = username
        return jsonify(success=True, message='注册成功！'), 200

    # GET 请求显示注册页面
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not verify_csrf_token(request.form.get('csrf_token')):
            return jsonify(success=False, message='非法请求'), 400

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = database.get_user_by_username(username)
        if user is None or not check_password_hash(user[2], password):
            # 统一返回错误，防止用户枚举
            return jsonify(success=False, message='用户名或密码错误'), 401

        # 登录成功
        session.clear()
        session['user_id'] = user[0]
        session['username'] = user[1]
        return jsonify(success=True, message='登录成功！'), 200

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------- 文件管理路由（全部需要登录） ----------
@app.route('/')
@login_required
def index():
    current_path = normalize_path(request.args.get('path', ''))
    if not is_safe_path(current_path):
        return "非法路径", 400

    user_id = session['user_id']
    folders = database.get_folders(current_path, user_id)
    files = database.get_files_by_path(current_path, user_id)
    return render_template('index.html',
                           files=files,
                           folders=folders,
                           current_path=current_path,
                           max_content_length=app.config['MAX_CONTENT_LENGTH'],
                           username=session['username'])


@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if not verify_csrf_token(request.form.get('csrf_token')):
        return jsonify(success=False, message='非法请求'), 400

    current_path = normalize_path(request.form.get('path', ''))
    if not is_safe_path(current_path):
        return jsonify(success=False, message='非法路径'), 400

    if 'file' not in request.files:
        return jsonify(success=False, message='没有选择文件'), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, message='文件名为空'), 400

    original_name = file.filename
    _, ext = os.path.splitext(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    stored_filename = timestamp + ext

    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_path)
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, stored_filename)
    file.save(file_path)
    size = os.path.getsize(file_path)

    database.add_file_record(
        original_name, stored_filename, size,
        file.mimetype, file_path, current_path,
        session['user_id']
    )
    return jsonify(success=True, message=f'文件 "{original_name}" 上传成功！'), 200


@app.route('/files')
@login_required
def list_files():
    current_path = normalize_path(request.args.get('path', ''))
    if not is_safe_path(current_path):
        return "非法路径", 400

    user_id = session['user_id']
    folders = database.get_folders(current_path, user_id)
    files = database.get_files_by_path(current_path, user_id)
    return render_template('files.html',
                           files=files,
                           folders=folders,
                           current_path=current_path,
                           username=session['username'])


@app.route('/create-folder', methods=['POST'])
@login_required
def create_folder():
    if not verify_csrf_token(request.form.get('csrf_token')):
        return jsonify(success=False, message='非法请求'), 400

    parent_path = normalize_path(request.form.get('path', ''))
    folder_name = request.form.get('folder_name', '').strip()

    if not folder_name:
        return jsonify(success=False, message='文件夹名不能为空'), 400
    if re.search(r'[/\\:*?"<>|]', folder_name):
        return jsonify(success=False, message='文件夹名包含非法字符'), 400

    new_path = parent_path + folder_name + '/'
    if not is_safe_path(new_path):
        return jsonify(success=False, message='非法路径'), 400

    full_dir = os.path.join(app.config['UPLOAD_FOLDER'], new_path)
    os.makedirs(full_dir, exist_ok=True)

    database.add_folder(new_path, session['user_id'])
    return jsonify(success=True, message='文件夹创建成功！'), 200


@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    record = database.get_file_by_id(file_id)
    if record is None:
        return "文件不存在", 404

    # 权限检查：文件必须属于当前用户
    # record 字段索引：0:id,1:original,2:stored,3:size,4:type,5:upload_time,6:path,7:relative_path,8:user_id
    if len(record) > 8 and record[8] != session['user_id']:
        return "无权访问该文件", 403

    stored_filename = record[2]
    original_filename = record[1]
    relative_path = record[7] if len(record) > 7 else ''

    file_dir = os.path.join(app.config['UPLOAD_FOLDER'], relative_path)
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