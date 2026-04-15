import os
import json
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
import database
from datetime import datetime
from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for
import secrets
from flask import Flask, request, render_template, send_from_directory, redirect, url_for
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

@app.route('/')
def index():
    files = database.get_all_files()   # 获取所有文件记录
    return render_template('index.html', 
                           files=files, 
                           max_content_length=app.config['MAX_CONTENT_LENGTH'])


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理上传的文件并保存到服务器"""
    if 'file' not in request.files:
        return '没有选择文件', 400

    file = request.files['file']
    if file.filename == '':
        return '文件名为空', 400
    
    original_name = file.filename
    # 获取原始扩展名（带点，如 ".png"）
    _, ext = os.path.splitext(file.filename)
    # 生成时间戳字符串，例如 "20260414153012"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    stored_filename = timestamp + ext
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
    file.save(file_path)
    size = os.path.getsize(file_path)
    database.add_file_record(original_name, stored_filename, size, file.mimetype, file_path)
    flash(f'文件 "{original_name}" 上传成功！', 'success')
    # 重定向回首页
    return redirect(url_for('index'))

@app.route('/files')
def list_files():
    # 调用数据库函数获取所有记录
    files = database.get_all_files()
    # 渲染模板，并把 files 传过去
    return render_template('files.html', files=files)


@app.route('/download/<int:file_id>')
def download_file(file_id):
    # 1. 根据 ID 获取文件记录
    record = database.get_file_by_id(file_id)
    if record is None:
        return "文件不存在", 404

    # 2. 提取存储文件名和原始文件名（用于下载时的提示名）
    # record 结构：(id, original_filename, stored_filename, size, type, upload_time, path)
    stored_filename = record[2]          # 存储在 uploads/ 下的文件名
    original_filename = record[1]        # 用户上传时的原始文件名

    # 3. 发送文件
    # send_from_directory 的第一个参数是目录路径，第二个参数是文件名
    # as_attachment=True 会让浏览器弹出下载对话框，attachment_filename 可设置下载时的文件名
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        stored_filename,
        as_attachment=True,
        download_name=original_filename   # Flask 2.0+ 用 download_name，旧版用 attachment_filename
    )

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return "QwQ 文件过大，请上传小于 {} MB 的文件~".format(max_mb), 413

if __name__ == '__main__':
    app.run(debug=True)