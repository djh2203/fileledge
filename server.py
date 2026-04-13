import os
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename

app = Flask(__name__)

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

    # 使用 secure_filename 清理文件名，防止路径遍历攻击
    filename = secure_filename(file.filename)
    # 可选：为防重名添加时间戳前缀，这里暂时保持原样
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    return f'文件 "{filename}" 上传成功！'

if __name__ == '__main__':
    app.run(debug=True)