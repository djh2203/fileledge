<p align="center">
  <img src="https://img.shields.io/badge/Fileledge-轻量私有云盘-2ea44f?style=for-the-badge&logo=icloud&logoColor=white" alt="Fileledge 轻量私有云盘" />
</p>


<p align="center">
  <img src="https://img.shields.io/badge/Python-3.7+-blue.svg?logo=python&logoColor=white" alt="Python 3.7+" />
  <img src="https://img.shields.io/badge/Flask-2.x-lightgrey.svg?logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/数据库-SQLite-brightgreen.svg?logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/许可证-MIT-yellow.svg" alt="MIT License" />
  <img src="https://img.shields.io/badge/维护者-djh2203-orange.svg" alt="djh2203" />
</p>

<h1 align="center">📁 Fileledge</h1>

<p align="center"><strong>基于 Flask + SQLite 的轻量级私有云盘系统</strong></p>

<p align="center">多用户隔离 · 文件夹管理 · 上传进度 · CSRF 防护<br>适合小团队或家庭内部使用</p>

---

## 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [配置说明](#配置说明)
- [部署到生产环境](#部署到生产环境)
- [安全注意事项](#安全注意事项)
- [常见问题](#常见问题)
- [未来扩展方向](#未来扩展方向)
- [贡献与许可](#贡献与许可)
- [联系方式](#联系方式)


---

## 功能特性

### 多用户支持

- **首次初始化**：系统首次启动时强制创建唯一管理员账户，确保安全
- **管理员面板**：管理员可在 Web 界面中创建普通用户，并查看所有用户列表
- **用户隔离**：每个用户的上传文件、文件夹均通过 `user_id` 进行数据库级与逻辑隔离，互不可见
- **管理员文件管理**：管理员可浏览并删除任意用户的文件/文件夹

### 文件管理

- **文件夹操作**：支持在当前路径下创建子文件夹，并通过面包屑导航在不同层级间跳转
- **递归删除文件夹**：管理员可删除文件夹及其所有子内容
- **文件名自动截断**：超过 25 字符显示省略号，悬停可见全名
- **移动端适配**：表格横向滑动、汉堡菜单折叠导航
- **文件上传**：
  - 支持任意文件类型上传
  - 前端基于配置的 `max_file_size_mb` 进行体积校验，并实时显示上传进度条
  - 后端同样进行大小限制（Werkzeug `MAX_CONTENT_LENGTH`）
- **文件下载**：所有文件通过动态路由提供下载，保留原始文件名，并校验归属权限
- **存储方式**：文件以时间戳重命名保存在服务器 `uploads/<user_id>/` 目录中，数据库记录原始文件名、相对路径等信息

### 安全机制

- **密码哈希**：所有用户密码通过 `werkzeug.security` 的 `generate_password_hash` 加密存储，不可逆
- **CSRF 防护**：全局生成并校验 CSRF Token，防止跨站请求伪造
- **登录保护**：所有文件管理路由均使用 `login_required` 装饰器验证会话
- **管理员专属接口**：`/admin` 路由被 `admin_required` 装饰器保护，仅限管理员访问
- **登录限流**：同一用户名连续登录失败 5 次后临时锁定 15 分钟，并延迟响应，防止暴力破解
- **初始化钩子**：`before_request` 钩子检测如果数据库中没有任何用户，则将除 `/init`、`/login` 和静态文件外的所有请求重定向至 `/init` 页面
- **路径穿越防护**：`is_safe_path()` 函数结合 `os.path.abspath` 与上传基路径比较，确保用户不能通过构造路径访问或操作 `uploads/` 以外的文件

### 界面

- 基于 **Bootstrap 5** 的响应式布局
- **深蓝导航栏**含 Logo 图片
- **Vanta.js 拓扑动态背景**（可定制颜色）
- 上传进度条采用 Bootstrap 条纹动画条
- 面包屑导航方便浏览多级目录

---

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 后端 | Python 3.x, Flask |
| 数据库 | SQLite（通过内置 `sqlite3` 模块操作） |
| 前端 | Bootstrap 5, Vanta.js 动态背景, 原生 CSS 动画, Jinja2 模板 |
| 安全相关 | `werkzeug.security`（密码哈希）、`secrets`（CSRF 令牌与密钥） |
| 部署建议 | Gunicorn / Waitress + Nginx + Flask-Compress（Gzip） |

---

---

## 项目结构

```
项目根目录/
├── server.py               # Flask 主程序（路由、视图、认证）
├── database.py             # 数据库初始化与 CRUD 操作
├── config.json             # 配置文件（最大上传文件大小）
├── requirements.txt        # Python 依赖
├── static/
│   ├── style.css           # 全局自定义样式
│   └── upload.js           # 上传进度及 AJAX 处理脚本
├── templates/
│   ├── base.html           # 公共母版（含 Bootstrap、Vanta）
│   ├── index.html          # 文件管理主页
│   ├── login.html          # 登录页面
│   ├── init.html           # 首次初始化管理员页面
│   ├── admin.html          # 管理员用户列表
│   ├── admin_user_files.html # 管理员管理用户文件
│   └── about.html          # 项目宣传页
├── uploads.db              # SQLite 数据库文件（运行后自动生成）
└── uploads/                # 用户上传文件的物理存储目录（运行后自动生成）
    └── <user_id>/          # 按用户 ID 隔离存储
```

---

---

## 快速开始

> 适用于本地开发 / 测试

### 环境要求

- Python 3.7 及以上版本
- pip

### 安装与运行

1. **获取代码**  
   克隆或解压项目源码到本地

2. **创建虚拟环境**（推荐）  
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows
   ```

3. **安装依赖**
   在项目根目录执行：
   ```bash
   pip install -r requirements.txt
   ```

4. **检查配置**  

   项目根目录下的 `config.json` 中 `max_file_size_mb` 默认值为 `100`，可按需修改


5. **清理旧数据（如有需要）**  
   删除 `uploads.db` 即可重新初始化管理员；`uploads/` 目录可保留，不影响初始化

6. **启动应用**  
   ```bash
   bash start.sh
   ```
   服务将在 `http://127.0.0.1:5000` 运行

7. **初始化管理员**  
   浏览器访问上述地址，系统会自动跳转到 `/init` 页面，按要求填写管理员用户名和密码完成注册并自动登录

---

---

## 使用指南

### 初始化管理员

- 首次访问系统（无任何用户）时，任何路径都会被重定向至 `/init`
- 输入管理员用户名、密码及确认密码  
  - 用户名仅允许 `3~20` 位字母、数字或下划线  
  - 密码至少 6 位  
- 创建成功后自动登录并跳转到文件管理页面

### 管理员操作

- **创建普通用户**：登录后页面上方会显示"管理用户"链接，进入 `/admin` 面板。填写新用户的用户名、密码并确认即可创建。创建成功后页面自动刷新，用户列表将更新
- **管理任意用户的文件**：在用户列表点击"管理文件"进入对应用户的文件浏览器，可删除单个文件或整个文件夹（含递归删除）
- **文件管理**：与普通用户界面相同，可上传、下载、创建文件夹，但其文件数据同样隔离存储，不会与普通用户混淆

### 普通用户操作

- 使用管理员创建的账号在 `/login` 页面登录
- **浏览文件**：登录后进入根目录，可通过面包屑导航进入子文件夹
- **创建文件夹**：在输入框中填写文件夹名（不能包含 `/ \ : * ? " < > |` 等字符），点击"创建文件夹"，成功后自动刷新目录
- **上传文件**：
  - 选择文件 → 点击"上传"
  - 若文件超过 `max_file_size_mb`（默认 100MB），前端会立即提示并阻止上传
  - 上传过程中会显示进度条，完成后自动刷新文件列表
- **下载文件**：点击文件列表中的文件名即可下载原始文件
- **移动端使用**：文件名过长时会显示 "..."，可横向滑动表格查看完整名称；手机端点击右上角汉堡按钮展开菜单

---

---

## 配置说明

### `config.json`

```json
{
    "max_file_size_mb": 100
}
```

- `max_file_size_mb`：允许上传的最大文件大小（单位：MB）。该值同时作用于前端校验和 Flask 后端限制（通过 `MAX_CONTENT_LENGTH` 实现）。修改后需重启服务生效

### 服务端常量（`server.py`）

| 常量 | 说明 |
|------|------|
| `app.config['UPLOAD_FOLDER']` | 上传文件存储目录，默认为 `uploads` |
| `app.secret_key` | Flask 会话加密密钥。应用首次启动会自动在项目根目录生成 `secret_config.py` 保存固定密钥。**生产环境**建议通过环境变量自定义：`export SECRET_KEY="your-generated-secret-key"` |
| 数据库路径 | 在 `database.py` 中由 `DATABASE = 'uploads.db'` 定义，如需修改可调整该变量 |

### 企业微信通知（可选）

项目根目录下的 `webhooks.json` 用于配置文件上传通知，格式为：
```json
{
    "用户名": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx"
}
```
- 键为系统内的用户名，值为对应企业微信群机器人的 Webhook 地址。
- 文件上传成功后，会异步向该 Webhook 发送通知。
- 未配置的用户不会发送通知。
- **安全提醒**：该文件包含密钥，请勿提交到公开仓库。

---

---

## 部署到生产环境

> 推荐方案：Nginx + Gunicorn + Flask-Compress

### 1. 安装 Gunicorn 和 Flask-Compress

```bash
pip install gunicorn flask-compress
```

### 2. 密钥管理（推荐）

应用已内置自动密钥管理功能：
- **首次启动**：自动在项目根目录生成 `secret_config.py`，保存固定密钥
- **生产环境**：建议通过环境变量自定义密钥，避免文件写入：
  ```bash
  export SECRET_KEY="your-generated-secret-key"
  ./start.sh
  ```
- **关闭调试模式**：确保 `debug=False`（代码已默认关闭）

### 3. 启用 Gzip 压缩和代理头修正

应用已自动启用 Gzip 压缩和代理头修正（`ProxyFix`），无需额外配置。`ProxyFix` 确保应用通过反向代理时能正确获取客户端真实 IP。

### 4. 静态文件缓存（可选）

在 `server.py` 中添加：

```python
@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response
```

### 5. 使用 Gunicorn 启动


使用项目提供的 `start.sh` 脚本（推荐）

```bash
# 先激活虚拟环境
source venv/bin/activate   # Linux/Mac
# 或 venv\Scripts\activate   # Windows

# 在 start.sh 中设置环境变量 SECRET_KEY（可选）
# 然后执行脚本
bash start.sh
```

注意：`start.sh` 使用单 worker 模式（`-w 1`）以避免 session 丢失，可根据服务器配置调整。

### 6. 配置 Nginx 反向代理

示例配置（`/etc/nginx/sites-available/filecloud`）：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 100m;   # 需与 config.json 中 max_file_size_mb 一致

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 禁止直接访问 uploads 目录（所有下载均通过 /download 路由提供）
    location /uploads {
        deny all;
    }
}
```

### 7. 配置 HTTPS（推荐）

使用 Let's Encrypt 获取证书，并配置 Nginx 监听 443 端口。同时在 `server.py` 中设置：

```python
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
```

### 8. 进程管理

可使用 `systemd` 或 `supervisor` 管理 Gunicorn 服务，保证后台运行及开机自启

---

---

## 安全注意事项

- **密钥管理**：应用首次启动会自动生成固定密钥到 `secret_config.py`。生产环境建议通过环境变量自定义密钥：`export SECRET_KEY="your-generated-secret-key"`
- **关闭调试模式**：切勿在生产环境开启 Flask 的 `debug=True`
- **限制上传目录访问**：通过 Nginx 配置禁止直接访问 `/uploads` 路径，所有文件获取必须经过应用鉴权
- **保护数据库**：`uploads.db` 不要直接暴露在 Web 可访问目录下
- **定期备份**：定期复制 `uploads/` 文件夹和 `uploads.db` 文件以保证数据安全
- **密码强度**：当前仅做最小长度要求（6位），建议管理员引导用户使用复杂密码
- **管理员删除防护**：管理员删除用户文件时经过 `user_id` 物理隔离与数据库级校验，防止误删其他用户数据
- **CSRF 保护**：所有 POST 请求（包括删除操作）均验证 CSRF Token
- **登录限制**：连续失败 5 次锁定 15 分钟，锁定状态存储在内存中（重启后重置），若使用多 worker 部署建议搭配 Redis
- **Webhook 密钥保管**：`webhooks.json` 中包含企业微信机器人密钥，务必加入 `.gitignore` 并妥善保管
- **文件类型白名单（可扩展）**：当前未限制文件类型，若需提高安全性，可在上传逻辑中增加 MIME 或扩展名白名单校验

---

---

## 常见问题

<details>
<summary><strong>Q：首次访问没有跳转到初始化页面，而是直接显示登录页？</strong></summary>

A：请检查是否存在 `uploads.db` 并且其中已有用户数据（例如之前的残留数据）。删除该文件及 `uploads/` 目录后重启服务即可。
</details>

<details>
<summary><strong>Q：上传大文件时失败，提示文件过大？</strong></summary>

A：首先确认 `config.json` 中的 `max_file_size_mb`；如果使用了 Nginx 反向代理，还需确保 `client_max_body_size` 的值不小于该配置。
</details>

<details>
<summary><strong>Q：管理员忘记密码怎么办？</strong></summary>

A：目前没有内置密码重置功能。可通过 Python 交互环境手动重置：

```python
from werkzeug.security import generate_password_hash
import sqlite3

new_hash = generate_password_hash('新密码')
conn = sqlite3.connect('uploads.db')
conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, 管理员ID))
conn.commit()
conn.close()
```
</details>

<details>
<summary><strong>Q：如何迁移或备份数据？</strong></summary>

A：直接备份 `uploads/` 目录（所有文件）和 `uploads.db`（数据库记录）。恢复时将两者放回原位置即可。
</details>

<details>
<summary><strong>Q：能否限制用户存储空间？</strong></summary>

A：当前版本未实现配额管理，所有用户共享同一个磁盘空间（实际物理磁盘大小限制）。如有需求可参考"未来扩展方向"进行二次开发。
</details>

<details>
<summary><strong>Q：手机访问时导航栏按钮消失？</strong></summary>

A：当屏幕宽度小于 992px 时，导航栏会自动折叠为汉堡菜单，点击即可展开。
</details>

<details>
<summary><strong>Q：文件名显示不全或被截断？</strong></summary>

A：移动端文件名超过 25 字符会自动截断并显示 "..."，可横向滑动表格查看完整名称，鼠标悬停也有提示。
</details>

<details>
<summary><strong>Q：如何配置企业微信通知？</strong></summary>

A：在项目根目录创建 `webhooks.json`，按以下格式填写用户名和对应的机器人 Webhook 地址：
```json
{
    "admin": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx"
}
```
确保已安装 `requests` 库。配置后用户上传文件时会自动向对应群聊发送通知。未配置的用户不会发送任何消息。
</details>

---

---

## 未来扩展方向

- 文件删除、重命名、移动（普通用户）
- 文件在线预览（文本、图片、视频等）
- 用户自行修改密码
- 回收站机制（误删恢复）
- 用户空间配额及已用容量显示
- 文件上传类型限制（MIME/扩展名白名单）

---

---

## 贡献与许可

本项目采用 [MIT 许可证](LICENSE) 开源，欢迎自由使用和修改，但须保留原始版权声明。

---

---

## 联系方式

| 项目 | 信息 |
|------|------|
| 维护者 | djh2203 |
| 邮箱 | hehe22032007@outlook.com |
| 项目仓库 | djh2203/fileledge |
