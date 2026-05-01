# server.py
import os
import re
import json
import secrets
import shutil
import time
import requests
import threading
import database
from datetime import datetime
from functools import wraps
from flask import (
    Flask, request, render_template, send_from_directory,
    redirect, url_for, jsonify, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_compress import Compress

# ---------- 自动管理 SECRET_KEY ----------
SECRET_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'secret_config.py')


def load_or_create_secret_key():
    # 1. 优先使用环境变量（便于生产部署覆盖）
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key

    # 2. 如果配置文件存在，解析读取
    if os.path.exists(SECRET_CONFIG_FILE):
        try:
            with open(SECRET_CONFIG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 匹配格式：SECRET_KEY = 'xxxxxxxx'
                    if line.startswith("SECRET_KEY = '") and line.endswith("'"):
                        return line[len("SECRET_KEY = '"):-1]
            # 未找到有效行，视为损坏，删除后重新生成
            print(f"[WARN] 配置文件 {SECRET_CONFIG_FILE} 格式无效，将重新生成")
            os.remove(SECRET_CONFIG_FILE)
        except Exception as e:
            print(f"[ERROR] 读取配置文件失败: {e}，将重新生成")
            try:
                os.remove(SECRET_CONFIG_FILE)
            except OSError:
                pass

    # 3. 生成新密钥并写入文件
    new_key = secrets.token_hex(24)
    try:
        with open(SECRET_CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write("# 自动生成的 Flask 密钥，请勿泄露\n")
            f.write(f"SECRET_KEY = '{new_key}'\n")
        print(f"[INFO] 已自动生成密钥文件：{SECRET_CONFIG_FILE}")
    except IOError as e:
        print(f"[ERROR] 无法写入密钥文件 {SECRET_CONFIG_FILE}: {e}")
        print("[WARN] 本次使用临时密钥，用户会话重启后可能失效")
        return secrets.token_hex(24)

    return new_key


database.init_db()

app = Flask(__name__)
# 暴力破解防护：记录 {用户名: (失败次数, 首次失败时间戳)}
LOGIN_FAILS = {}
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
Compress(app)
app.secret_key = load_or_create_secret_key()

# ---------- 读取最大文件大小限制 ----------
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
max_mb = config.get('max_file_size_mb', 100)
app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------- 读取用户 webhook 映射 ----------
WEBHOOKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webhooks.json')
user_webhooks = {}
try:
    with open(WEBHOOKS_FILE, 'r', encoding='utf-8') as f:
        user_webhooks = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    print("[WARN] webhooks.json 不存在或格式错误，将不发送任何通知")

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

def send_webhook_message(username, action, filename, size=None):
    """异步发送通知到对应用户的企业微信 webhook"""
    webhook_url = user_webhooks.get(username)
    if not webhook_url:
        return  # 该用户未配置 webhook，不发送

    # 格式化文件大小
    if size is not None:
        if size >= 1048576:
            size_str = f" · {size / 1048576:.1f} MB"
        elif size >= 1024:
            size_str = f" · {size / 1024:.1f} KB"
        else:
            size_str = f" · {size} 字节"
    else:
        size_str = ""
    msg = f"📁 文件{action}\n\n用户：{username}\n文件：{filename}{size_str}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"

    def _send():
        try:
            requests.post(
                webhook_url,
                json={"msgtype": "text", "text": {"content": msg}},
                timeout=5
            )
        except Exception as e:
            print(f"[WARN] 企业微信通知发送失败 ({username}): {e}")

    threading.Thread(target=_send, daemon=True).start()

# ---------- 登录与管理员装饰器 ----------
def login_required(view_func):
    """要求用户已登录"""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapper

def admin_required(view_func):
    """要求当前用户为管理员"""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return "无权访问", 403
        return view_func(*args, **kwargs)
    return wrapper

# ---------- CSRF 保护 ----------
def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

def verify_csrf_token(token):
    return token and token == session.get('csrf_token')

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())


# ---------- 初始化钩子：若无任何用户，强制跳转到 /init ----------
@app.before_request
def before_request():
    # 允许访问静态文件、login、init、about 页面本身
    if request.endpoint in ('login', 'init', 'about', 'static'):
        return
    # 如果数据库中没有用户，并且访问的不是 /init，则重定向
    if database.get_user_count() == 0 and request.endpoint != 'init':
        return redirect(url_for('init'))


# ---------- 认证相关 ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not verify_csrf_token(request.form.get('csrf_token')):
            return jsonify(success=False, message='非法请求'), 400

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # ----- 暴力破解防护 -----
        # 检查是否已被临时锁定（5次失败后锁定15分钟）
        if username in LOGIN_FAILS:
            fail_count, first_fail_time = LOGIN_FAILS[username]
            if fail_count >= 5:
                elapsed = time.time() - first_fail_time
                if elapsed < 900:  # 15分钟 = 900秒
                    time.sleep(1)
                    return jsonify(success=False, message='尝试次数过多，请15分钟后再试'), 429
                else:
                    # 锁定时间已过，清除记录
                    del LOGIN_FAILS[username]

        # ----- 验证用户 -----
        user = database.get_user_by_username(username)
        if user is None or not check_password_hash(user[2], password):
            # 登录失败：更新失败次数
            now = time.time()
            if username not in LOGIN_FAILS:
                LOGIN_FAILS[username] = (1, now)
            else:
                fail_count, first_fail_time = LOGIN_FAILS[username]
                if now - first_fail_time > 900:
                    # 重置计数器
                    LOGIN_FAILS[username] = (1, now)
                else:
                    LOGIN_FAILS[username] = (fail_count + 1, first_fail_time)

            # 延迟1秒返回，增加暴力破解成本
            time.sleep(1)
            return jsonify(success=False, message='用户名或密码错误'), 401

        # 登录成功：清除失败记录
        if username in LOGIN_FAILS:
            del LOGIN_FAILS[username]

        session.clear()
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['role'] = user[3]
        return jsonify(success=True, message='登录成功！'), 200

    # GET 请求
    return render_template('login.html')


@app.route('/init', methods=['GET', 'POST'])
def init():
    """初始化管理员账户（仅在数据库无任何用户时可用）"""
    # 如果已有用户，则拒绝服务
    if database.get_user_count() > 0:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if not verify_csrf_token(request.form.get('csrf_token')):
            return jsonify(success=False, message='非法请求'), 400

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if not username or not password:
            return jsonify(success=False, message='用户名和密码不能为空'), 400
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            return jsonify(success=False, message='用户名需3-20位字母、数字或下划线'), 400
        if len(password) < 6:
            return jsonify(success=False, message='密码至少6位'), 400
        if password != confirm:
            return jsonify(success=False, message='两次密码不一致'), 400

        password_hash = generate_password_hash(password)
        user_id = database.create_user(username, password_hash, role='admin')
        if user_id is None:
            return jsonify(success=False, message='用户名已存在'), 400

        # 自动登录
        session.clear()
        session['user_id'] = user_id
        session['username'] = username
        session['role'] = 'admin'
        return jsonify(success=True, message='管理员注册成功！'), 200

    return render_template('init.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/about')
def about():
    """关于页面 - 项目宣传页"""
    return render_template('about.html')


@app.route('/admin', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_panel():
    """管理员创建普通用户的面板"""
    if request.method == 'POST':
        if not verify_csrf_token(request.form.get('csrf_token')):
            return jsonify(success=False, message='非法请求'), 400

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if not username or not password:
            return jsonify(success=False, message='用户名和密码不能为空'), 400
        if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
            return jsonify(success=False, message='用户名需3-20位字母、数字或下划线'), 400
        if len(password) < 6:
            return jsonify(success=False, message='密码至少6位'), 400
        if password != confirm:
            return jsonify(success=False, message='两次密码不一致'), 400

        password_hash = generate_password_hash(password)
        user_id = database.create_user(username, password_hash, role='user')
        if user_id is None:
            return jsonify(success=False, message='用户名已存在'), 400

        return jsonify(success=True, message=f'用户 "{username}" 创建成功！'), 200

    # GET 请求：显示管理页面（含用户列表）
    users = database.get_all_users()
    return render_template('admin.html', users=users)


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
                           username=session['username'],
                           role=session.get('role'))


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

    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(session['user_id']), current_path)
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, stored_filename)
    file.save(file_path)
    size = os.path.getsize(file_path)

    database.add_file_record(
        original_name, stored_filename, size,
        file.mimetype, file_path, current_path,
        session['user_id']
    )
    # 发送企业微信通知
    send_webhook_message(session['username'], '上传', original_name, size)
    return jsonify(success=True, message=f'文件 "{original_name}" 上传成功！'), 200


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

    full_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(session['user_id']), new_path)
    os.makedirs(full_dir, exist_ok=True)

    database.add_folder(new_path, session['user_id'])
    return jsonify(success=True, message='文件夹创建成功！'), 200


@app.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    record = database.get_file_by_id(file_id)
    if record is None:
        return "文件不存在", 404

    # 权限：文件必须属于当前用户
    if len(record) > 8 and record[8] != session['user_id']:
        return "无权访问该文件", 403

    stored_filename = record[2]
    original_filename = record[1]
    relative_path = record[7] if len(record) > 7 else ''

    user_id = record[8] if len(record) > 8 else session['user_id']
    file_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id), relative_path)
    return send_from_directory(
        file_dir,
        stored_filename,
        as_attachment=True,
        download_name=original_filename
    )


@app.route('/admin/user/<int:user_id>/files')
@login_required
@admin_required
def admin_user_files(user_id):
    """管理员以只读方式查看某用户的文件（也可以删除）"""
    current_path = normalize_path(request.args.get('path', ''))
    if not is_safe_path(current_path):
        return "非法路径", 400

    user = database.get_user_by_id(user_id)
    if user is None:
        return "用户不存在", 404

    folders = database.get_folders(current_path, user_id)
    files = database.get_files_by_path(current_path, user_id)
    return render_template('admin_user_files.html',
                           files=files,
                           folders=folders,
                           current_path=current_path,
                           view_user_id=user_id,
                           view_username=user[1])


@app.route('/admin/delete/file/<int:file_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_file(file_id):
    if not verify_csrf_token(request.form.get('csrf_token')):
        return jsonify(success=False, message='非法请求'), 400

    record = database.get_file_by_id_admin(file_id)
    if record is None:
        return jsonify(success=False, message='文件不存在'), 404

    # record: (id, original, stored, size, type, time, path, relative_path, user_id)
    stored_name = record[2]
    relative_path = record[7]
    user_id = record[8]

    # 删除物理文件
    file_full = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id), relative_path, stored_name)
    try:
        os.remove(file_full)
    except FileNotFoundError:
        pass

    # 删除数据库记录
    database.delete_file_record(file_id)
    return jsonify(success=True, message='文件已删除'), 200


@app.route('/admin/delete/folder', methods=['POST'])
@login_required
@admin_required
def admin_delete_folder():
    if not verify_csrf_token(request.form.get('csrf_token')):
        return jsonify(success=False, message='非法请求'), 400

    folder_path = request.form.get('folder_path', '')
    user_id_str = request.form.get('user_id', '')
    if not folder_path or not user_id_str:
        return jsonify(success=False, message='参数错误'), 400
    user_id = int(user_id_str)

    # 物理删除整个目录树
    full_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id), folder_path)
    if os.path.exists(full_dir):
        shutil.rmtree(full_dir)

    # 删除数据库中的文件夹和其下所有文件
    database.delete_folder_and_files(folder_path, user_id)
    return jsonify(success=True, message='文件夹已删除'), 200


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify(success=False, message=f"文件过大，请上传小于 {max_mb} MB 的文件~"), 413


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)