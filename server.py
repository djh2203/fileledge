import os
import json
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
import database
from datetime import datetime
database.init_db()   # 启动时确保表存在

app = Flask(__name__)

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
    """显示上传表单"""
    return render_template('index.html')

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
    return f'文件 "{original_name}" 上传成功！'

@app.route('/files')
def list_files():
    # 调用数据库函数获取所有记录
    files = database.get_all_files()
    # 渲染模板，并把 files 传过去
    return render_template('files.html', files=files)

if __name__ == '__main__':
    app.run(debug=True)