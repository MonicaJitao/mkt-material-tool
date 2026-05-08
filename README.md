# mkt-material-tool

微众银行营销素材自动化生成工具 —— 从 Brief 到海报，AI 驱动的六阶段工作流。

## 功能概览

| 阶段 | 说明 |
|------|------|
| Brief | 填写活动信息（节日、受众、城市、客户经理、风格、尺寸） |
| Plan Review | AI 生成结构化视觉方案，用户审核 |
| Image Batch | 批量生成候选背景图（Tuzi Banana / Gemini） |
| HTML Generate | 选定图片后，Claude 生成 HTML 海报 |
| HTML Editor | iframe 沙箱预览 + CodeMirror 源码编辑 + 版本管理 |
| Library | 浏览和管理历史活动、素材、HTML 版本 |

## 技术栈

**后端**
- Python 3.11+ / FastAPI / SQLAlchemy / Pydantic v2
- SQLite 数据库（7 张表，11 状态状态机）
- httpx 调用外部 API（Tuzi Banana 图像生成、Anthropic Claude）

**前端**
- React 18 + TypeScript 5.5
- Vite 5.4 / React Router 6 / TanStack Query / Zustand / CodeMirror 6
- 纯 CSS + Design Tokens（暗色主题，劳动红 + 鎏金配色）

## 项目结构

```
mkt-material-tool/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由
│   │   ├── core/         # 配置、状态机、工具函数
│   │   ├── db/           # SQLAlchemy 模型、数据库会话
│   │   ├── schemas/      # Pydantic 请求/响应模型
│   │   └── services/     # AI 代理、存储服务、HTML 校验
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/          # API 客户端
│       ├── pages/        # 6 个工作流页面
│       ├── components/   # Shell、Stepper、编辑器等组件
│       └── styles/       # Design Tokens + 全局样式
├── 五一宣传提示词/        # 参考素材（五一活动提示词）
└── 图像批量生成/          # 独立的批量生图工具（已单独维护）
```

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+
- Tuzi Banana API Key（图像生成）
- Anthropic API Key（HTML 生成）

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入真实的 API Key

# 启动服务（默认 http://127.0.0.1:8765）
uvicorn app.main:app --reload --port 8765
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（默认 http://localhost:5173，自动代理 /api 到后端）
npm run dev
```

### 测试

```bash
# 后端测试
cd backend
pytest

# 前端类型检查
cd frontend
npm run typecheck
```

## 工作流程

```
用户填写 Brief
    ↓
AI 生成视觉方案 → 用户审核/修改
    ↓
批量生成候选背景图 → 用户选择
    ↓
Claude 生成 HTML 海报
    ↓
预览 + 编辑 + 保存版本
    ↓
发布到素材库
```

## 环境变量

参见 [backend/.env.example](backend/.env.example)，主要配置项：

| 变量 | 说明 |
|------|------|
| `TUZI_API_KEY` | Tuzi Banana API 密钥 |
| `TUZI_API_BASE` | Tuzi API 地址（默认 `https://api.tu-zi.com`） |
| `ANTHROPIC_API_KEY` | Anthropic Claude API 密钥 |
| `ANTHROPIC_BASE_URL` | Claude API 地址（支持代理） |
| `ANTHROPIC_MODEL` | Claude 模型名称 |
| `DATABASE_URL` | SQLite 数据库连接串 |

## License

MIT
