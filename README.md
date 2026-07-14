# 量化回测系统

基于 Gate.io API 的加密货币量化交易回测系统，支持现货 + 合约双市场。

## 功能特性

- **数据管理**：从 Gate.io API v4 按需拉取 K 线数据，本地缓存，自动分页
- **因子输入**：支持公式表达式和 Python 代码两种模式
- **多因子组合**：等权、加权、IC 加权
- **向量化回测**：基于 Pandas/NumPy 的毫秒级回测
- **绩效评估**：14+ 项核心指标（年化收益、夏普、最大回撤、Calmar 等）
- **Web 可视化**：资金曲线、K 线叠加买卖点、回撤分析、交易记录

## 技术栈

- **前端**：React 18 + TypeScript + Vite + Ant Design + ECharts + TradingView Lightweight Charts
- **后端**：FastAPI + Uvicorn + Pydantic v2
- **回测引擎**：Pandas + NumPy
- **数据存储**：SQLite + Parquet

## 快速启动

### 方式一：一键启动脚本

```bash
# 启动前后端（后端 8855，前端 5173）
bash start.sh
```

### 方式二：分别启动

**后端**

```bash
cd backend
bash start.sh        # 默认端口 8855
# 或指定端口
PORT=8855 bash start.sh
```

**前端**

```bash
cd frontend
bash start.sh        # 默认端口 5173
# 或指定后端端口
API_PORT=8855 bash start.sh
```

### 方式三：Docker Compose

```bash
docker-compose up --build
```

访问地址：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8855
- API 文档：http://localhost:8855/docs

## 项目结构

```
quant-backtest/
├── backend/              # 后端服务
│   ├── app/
│   │   ├── main.py       # FastAPI 入口
│   │   ├── api/          # API 路由
│   │   ├── core/         # 回测引擎、因子引擎、绩效分析
│   │   ├── data/         # Gate.io 客户端、缓存、存储
│   │   ├── models/       # Pydantic 模型
│   │   └── utils/        # 工具函数
│   ├── tests/            # 测试脚本
│   ├── requirements.txt
│   ├── Dockerfile
│   └── start.sh
├── frontend/             # 前端应用
│   ├── src/
│   │   ├── pages/        # 页面组件
│   │   ├── services/     # API 封装
│   │   └── types/        # TypeScript 类型
│   ├── package.json
│   ├── Dockerfile
│   └── start.sh
├── data/                 # 本地数据存储
├── design/               # 设计文档
├── docs/                 # 开发计划与文档
├── docker-compose.yml
└── start.sh              # 一键启动脚本
```

## 核心 API

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/symbols` | 获取交易对列表 |
| GET | `/api/data/klines` | 获取 K 线数据 |
| POST | `/api/backtest/run` | 执行回测 |
| GET | `/api/backtest/{id}` | 获取回测结果 |
| POST | `/api/factor/eval` | 预览因子信号 |
| GET | `/api/factor/builtins` | 获取内置因子列表 |

## 测试

```bash
cd backend
source venv/Scripts/activate

# M1 数据层测试
python tests/test_m1_data.py

# M2 回测引擎测试
python tests/test_m2_backtest.py

# M3 因子引擎测试
python tests/test_m3_factor.py

# M4 绩效分析测试
python tests/test_m4_performance.py
```

## 注意事项

1. **Gate.io 数据限制**：现货 K 线最多支持最近 10000 个数据点，请合理选择时间范围
2. **逻辑组合语法**：因子公式中的逻辑组合使用函数调用形式，例如 `AND(EMA(close, 12) > EMA(close, 26), RSI(close, 14) < 70)`
3. **代码安全**：用户提交的 Python 代码在 AST 沙箱中执行，禁止文件系统/网络访问

## 开发计划

详见 [docs/开发计划.md](docs/开发计划.md)。
