# PaperMap

现代化的论文管理与追踪系统，采用 Vue 3 + FastAPI 架构。

## 功能特性

- **论文管理**: 收集、搜索、筛选论文
- **矩阵视图**: 按公司/高校/作者/标签查看论文矩阵
- **标签系统**: 层级标签树，支持多级标签
- **关注列表**: 管理关注的公司、高校、作者
- **暗色模式**: 支持明/暗主题切换
- **响应式设计**: 适配各种屏幕尺寸

## 技术栈

### 前端
- Vue 3 + TypeScript
- Vite
- Tailwind CSS
- shadcn-vue 风格组件
- Vue Router
- Pinia
- TanStack Table

### 后端
- FastAPI
- SQLite
- Pydantic

## 快速开始

### 环境要求
- Node.js 18+
- Python 3.9+

### 环境变量配置

按需设置以下环境变量（启动前 `export` 或写入 shell 配置）：

| 变量 | 说明 | 示例 |
|------|------|------|
| `PAPER_MAP_API_KEY` | AI 接口密钥（摘要、公司/高校提取等） | `sk-xxx` |
| `PAPER_MAP_BASE_URL` | AI 接口地址，可选 | `https://api.openai.com/v1` |
| `PAPER_MAP_MODEL` | 模型名称 | `gpt-4o-mini` |
| `PAPER_MAP_PASSWORD` | 修改操作口令，可选 | 不设则无需密码 |
| `DB_PATH` | 数据库路径，可选 | `data/database.db` |

```bash
export PAPER_MAP_API_KEY=sk-xxx
export PAPER_MAP_BASE_URL=https://api.openai.com/v1
```

### 安装依赖

```bash
# 后端依赖
pip install fastapi uvicorn pydantic

# 前端依赖
cd frontend
npm install
```

### 启动开发服务器

使用启动脚本（推荐）:
```bash
./start.sh
```

或手动启动:

```bash
# 启动后端 (端口 8000)
cd backend
python main.py

# 启动前端 (端口 5173)
cd frontend
npm run dev
```

### 访问应用

- 前端: http://localhost:5173
- API 文档: http://localhost:8000/docs

## 项目结构

```
paper-map/
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── components/       # UI 组件
│   │   │   ├── ui/           # 基础 UI 组件
│   │   │   ├── layout/       # 布局组件
│   │   │   ├── papers/       # 论文相关组件
│   │   │   ├── matrix/       # 矩阵相关组件
│   │   │   └── tags/         # 标签相关组件
│   │   ├── views/            # 页面视图
│   │   ├── stores/           # Pinia stores
│   │   ├── api/              # API 调用
│   │   ├── types/            # TypeScript 类型
│   │   └── lib/              # 工具函数
│   ├── package.json
│   └── vite.config.ts
├── backend/                  # FastAPI 后端
│   ├── main.py               # 入口文件
│   ├── routers/              # API 路由
│   └── schemas/              # Pydantic 模型
├── database.py               # 数据库操作
├── completer.py              # AI 补全
├── link_parser.py            # 链接解析
├── config.py                 # 配置
├── data/                     # 数据目录
│   └── database.db           # SQLite 数据库
└── start.sh                  # 启动脚本
```

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/papers | 论文列表 |
| GET | /api/papers/{id} | 论文详情 |
| POST | /api/papers | 创建论文 |
| PUT | /api/papers/{id} | 更新论文 |
| DELETE | /api/papers/{id} | 删除论文 |
| GET | /api/matrix/companies | 公司矩阵 |
| GET | /api/matrix/universities | 高校矩阵 |
| GET | /api/matrix/authors | 作者矩阵 |
| GET | /api/tags | 标签列表 |
| GET | /api/tags/tree | 标签树 |
| POST | /api/collect | 收集论文 |
| GET | /api/watched/companies | 关注公司 |
| GET | /api/watched/universities | 关注高校 |
| GET | /api/watched/authors | 关注作者 |

## 开发

### 构建生产版本

```bash
cd frontend
npm run build
```

### 代码检查

```bash
cd frontend
npm run lint
```

## License

MIT
