# PaperMap 开发环境部署指南

本文档详细说明如何从零开始搭建 PaperMap 开发环境。

## 目录

- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [详细安装步骤](#详细安装步骤)
- [端口与访问地址](#端口与访问地址)
- [环境变量配置](#环境变量配置)
- [可选依赖](#可选依赖)
- [常见问题](#常见问题)

---

## 环境要求

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| Node.js | 18+ | 前端运行环境 |
| Python | 3.9+ | 后端运行环境 |
| git | 任意版本 | 代码克隆（可选） |
| npm | 随 Node.js 安装 | 前端包管理器 |

### 版本检查

```bash
# 检查 Node.js 版本
node -v   # 应输出 v18.x.x 或更高

# 检查 Python 版本
python --version   # 应输出 Python 3.9.x 或更高
# 或
python3 --version

# 检查 npm 版本
npm -v
```

---

## 快速启动

如果你已经安装好环境，可以用一条命令启动：

```bash
./start.sh
```

启动脚本会自动完成以下操作：

1. 检查 `data/database.db` 是否存在
2. 如果数据库不存在，自动创建 `data/` 目录并初始化数据库
3. 启动后端 API 服务（端口 8000）
4. 启动前端开发服务器（端口 5173）

启动成功后，终端会显示：

```
✅ PaperMap is running!
   Frontend: http://localhost:5173
   Backend:  http://localhost:8000
   API Docs: http://localhost:8000/docs
```

按 `Ctrl+C` 可同时停止前后端服务。

### Windows 用户注意

`start.sh` 是 Bash 脚本，Windows 原生命令行无法直接执行。推荐以下方案：

**方案一：使用 WSL2（推荐）**

在 Windows 上安装 WSL2 并运行 Ubuntu，可以获得与 Linux 完全一致的开发体验：

1. 安装 WSL2：`wsl --install`
2. 在 Ubuntu 中安装 Node.js 和 Python
3. 在项目目录下直接运行 `./start.sh`

**方案二：使用 Git Bash**

如果已安装 Git for Windows，可以在 Git Bash 中运行：

```bash
./start.sh
```

**方案三：手动分别启动**

无需 `start.sh`，打开两个终端窗口：

```bash
# 终端 1：初始化数据库（仅首次需要）
mkdir data
python -c "from database import Database; db = Database('data/database.db'); db.construct()"

# 终端 1：启动后端
cd backend
python main.py

# 终端 2：启动前端
cd frontend
npm run dev
```

访问地址不变：前端 `http://localhost:5173`，后端 `http://localhost:8000`。

---

## 详细安装步骤

### 1. 克隆项目（如适用）

```bash
git clone <repository-url>
cd paper-map
```

### 2. Python 虚拟环境（推荐）

使用虚拟环境可以避免依赖冲突：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate

# Windows:
# venv\Scripts\activate

# 确认虚拟环境已激活（命令行前会显示 (venv)）
which python   # Linux/macOS
# 或
where python   # Windows
```

### 3. 安装后端依赖

**核心依赖（运行 FastAPI 后端必须安装）：**

```bash
pip install fastapi uvicorn pydantic
```

> **注意**: 项目根目录的 `requirements.txt` 仅包含 Panel Dashboard 的依赖（`panel`, `pandas`, `param`），不包含 FastAPI 核心依赖。如果你只需要运行 Web 应用，上面的命令就够了。

**如果需要完整的开发环境（包括 Dashboard）：**

```bash
pip install -r requirements.txt
pip install fastapi uvicorn pydantic
```

### 4. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### 5. 初始化数据库

数据库会在首次启动时自动创建，也可以手动初始化：

```bash
# 创建数据目录
mkdir -p data

# 初始化数据库
python -c "from database import Database; db = Database('data/database.db'); db.construct()"
```

### 6. 启动服务

**方式一：一键启动（推荐）**

```bash
./start.sh
```

**方式二：手动分别启动**

打开两个终端窗口：

```bash
# 终端 1：启动后端
cd backend
python main.py

# 终端 2：启动前端
cd frontend
npm run dev
```

**方式三：使用 uvicorn 直接启动后端**

```bash
# 在项目根目录执行
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 端口与访问地址

| 服务 | 端口 | 访问地址 | 说明 |
|------|------|----------|------|
| 前端开发服务器 | 5173 | http://localhost:5173 | Vue + Vite 开发服务器 |
| 后端 API | 8000 | http://localhost:8000 | FastAPI 后端服务 |
| API 文档 | 8000 | http://localhost:8000/docs | Swagger UI 交互式文档 |
| API 文档 (ReDoc) | 8000 | http://localhost:8000/redoc | ReDoc 格式文档 |

### 前端代理配置

Vite 开发服务器配置了 API 代理，所有 `/api` 请求会自动转发到后端：

```typescript
// frontend/vite.config.ts
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

这意味着前端代码可以直接请求 `/api/xxx`，无需写完整地址。

---

## 环境变量配置

项目通过 `config.py` 支持环境变量覆盖默认配置：

| 环境变量 | 默认值 | 说明 | 实际使用位置 |
|----------|--------|------|--------------|
| `DB_PATH` | `data/database.db` | SQLite 数据库文件路径 | 部分脚本使用，FastAPI 后端硬编码为 `data/database.db` |
| `CACHE_PATH` | `cache/` | 缓存目录路径 | 辅助脚本使用 |
| `DASHBOARD_PORT` | `5006` | Panel Dashboard 端口 | 仅用于 `dashboard.py`（非 FastAPI） |
| `APP_PORT` | `5007` | Panel App 端口 | 仅用于 `dashboard.py`（非 FastAPI） |
| `DASHBOARD_ADDRESS` | `localhost` | Dashboard 监听地址 | 仅用于 `dashboard.py` |
| `APP_ADDRESS` | `0.0.0.0` | App 监听地址 | 仅用于 `dashboard.py` |

> **重要说明**: 
> - FastAPI 后端（`backend/main.py`）的端口 `8000` 是硬编码的，不读取环境变量
> - `DASHBOARD_PORT` 和 `APP_PORT` 用于 Panel Dashboard（`dashboard.py`），这是一个独立的数据面板，与 FastAPI 后端无关
> - 数据库路径 `DB_PATH` 仅被部分辅助脚本使用，FastAPI 后端在 `backend/main.py` 中硬编码为 `data/database.db`

### 设置环境变量示例

```bash
# Linux/macOS (临时)
export DB_PATH=/custom/path/database.db
./start.sh

# Linux/macOS (永久，写入 ~/.bashrc 或 ~/.zshrc)
echo 'export DB_PATH=/custom/path/database.db' >> ~/.bashrc
source ~/.bashrc

# Windows (临时)
set DB_PATH=C:\custom\path\database.db

# Windows (永久)
setx DB_PATH "C:\custom\path\database.db"
```

---

## 可选依赖

以下依赖用于辅助脚本，**不是运行核心应用的必需品**：

| 包名 | 用途 | 使用的脚本 |
|------|------|-----------|
| `arxiv` | arXiv 论文搜索与收集 | `paper_collector.py`, `arxiv_api.py`, `search_and_insert_papers.py` |
| `openai` | AI 摘要补全 | `ai_api.py`, `completer.py` |
| `tika` | PDF 解析 | `pdf_convertor.py` |
| `requests` | HTTP 请求 | `add_arxiv_links.py`, `completer.py`, `ai_api.py` |
| `tqdm` | 进度条显示 | `completer.py` |
| `panel`, `pandas`, `param` | Panel Dashboard | `dashboard.py` |

### 安装可选依赖

```bash
# arXiv 相关功能
pip install arxiv

# AI 补全功能（需要 OpenAI API Key）
pip install openai

# PDF 解析
pip install tika
# 注意：tika 需要本地运行 Java 环境

# Panel Dashboard
pip install panel pandas param

# 批量安装所有可选依赖
pip install arxiv openai tika requests tqdm panel pandas param
```

---

## 常见问题

### Q: 端口被占用怎么办？

**检查端口占用：**

```bash
# Linux/macOS
lsof -i :8000
lsof -i :5173

# Windows
netstat -ano | findstr :8000
netstat -ano | findstr :5173
```

**终止占用进程：**

```bash
# Linux/macOS
kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

**或者修改端口：**

- 前端：修改 `frontend/vite.config.ts` 中的 `server.port`
- 后端：修改 `backend/main.py` 中 `uvicorn.run` 的 `port` 参数

### Q: 数据库路径错误？

FastAPI 后端默认使用 `data/database.db`。如果遇到数据库找不到的错误：

1. 确保在项目根目录运行命令
2. 手动初始化数据库：
   ```bash
   mkdir -p data
   python -c "from database import Database; db = Database('data/database.db'); db.construct()"
   ```

### Q: CORS 跨域问题？

开发环境下，FastAPI 已配置允许所有来源：

```python
# backend/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    ...
)
```

如果仍有问题，确认：
1. 前端通过 `http://localhost:5173` 访问（不是 `127.0.0.1`）
2. 后端正常运行在 `http://localhost:8000`
3. Vite 代理配置正确

### Q: 前端构建失败？

```bash
cd frontend

# 清理依赖重新安装
rm -rf node_modules package-lock.json
npm install

# 检查 Node.js 版本
node -v  # 需要 18+
```

### Q: Python 依赖安装失败？

```bash
# 升级 pip
pip install --upgrade pip

# 使用国内镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi uvicorn pydantic

# 如果 uvicorn 安装失败，尝试安装完整版
pip install "uvicorn[standard]"
```

### Q: start.sh 没有执行权限？

```bash
chmod +x start.sh
./start.sh
```

### Q: 如何查看 API 文档？

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

在 Swagger UI 中可以直接测试 API 接口。

---

## 项目结构速览

```
paper-map/
├── frontend/           # Vue 3 前端
│   ├── src/           # 源代码
│   ├── package.json   # 前端依赖
│   └── vite.config.ts # Vite 配置（含代理）
├── backend/           # FastAPI 后端
│   ├── main.py        # 入口文件（端口 8000）
│   ├── routers/       # API 路由
│   └── schemas/       # Pydantic 模型
├── data/              # 数据目录
│   └── database.db    # SQLite 数据库（自动创建）
├── config.py          # 配置文件
├── database.py        # 数据库操作类
├── requirements.txt   # Python 依赖（仅 Panel Dashboard）
└── start.sh           # 一键启动脚本
```

---

## 开发建议

1. **使用虚拟环境**：避免全局 Python 环境污染
2. **前后端分离启动**：开发时分别启动，便于查看各自日志
3. **善用 API 文档**：Swagger UI 提供完整的接口测试功能
4. **数据库备份**：定期备份 `data/database.db` 文件

如有问题，请查看项目 README.md 或提交 Issue。
