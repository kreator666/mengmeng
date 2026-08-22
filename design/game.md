目录
约定与状态码 · 系统 · 数据 · 因子 · 评估 · 回测 · 选股 · MCP 工具
约定
项目	说明
Base URL	https://markethon.fit。交互式调试见 /docs，机器可读 schema 见 /openapi.json
请求格式	POST 一律 Content-Type: application/json；GET 使用 query 参数
有状态	进程内单例缓存。须先 POST /data/load 加载数据，之后的评估/回测/选股都基于该缓存；重复 load 会覆盖
错误格式	统一 {"detail": "错误信息"}
股票代码	000001.SZ / 600519.SH 格式；因子名不区分大小写（自动转大写）
认证 / 限流	除 /health 与文档页外均需认证：POST /auth/login（新用户名自动注册，密码至少 6 位）获取 Bearer token，之后请求带 Authorization: Bearer <token>；token 默认 7 天有效、服务重启失效。登录/注册接口有限频（登录每 IP 每分钟 20 次且每用户名每分钟 5 次，注册每 IP 每分钟 5 次，超限 429）。下文 curl 示例均需加 -H "Authorization: Bearer $TOKEN"
状态码	含义
200	成功
400	业务错误：数据未加载 / 因子不存在 / 表达式非法 / 参数取值错误
422	请求体格式校验失败（FastAPI 自动返回字段级错误列表）
500	服务内部错误（数据源不可用、计算异常等）
系统
GET/health
健康检查。返回 {"ok": true}。
GET/status
服务状态：数据是否已加载、股票数、日期范围、已注册自定义因子。
# 响应示例
{
  "loaded": true,
  "symbols": 10,
  "date_range": ["2023-01-01", "2024-12-31"],
  "custom_factors": ["RET5"]
}
数据
GET/data/symbols
列出全市场 A 股代码（总数 + 样例）。
参数	类型	默认	说明
limit	int	50	样例返回条数
# 响应示例
{"total": 5536, "sample": ["000001.SZ", "000002.SZ", "..."]}
POST/data/load
从 ClickHouse 拉取日线 → 转 qlib 格式 → 预计算并缓存全部 158 个 Alpha158 因子（可选再缓存 360 个 Alpha360）。所有后续操作的前提；耗时随股票数增长（数百只约数分钟），请求会同步阻塞至完成。
字段	类型	必填	默认	说明
limit	int	否	500	全市场取前 N 只（symbols/universe 为空时生效）；0 表示全部股票
symbols	string[]	否	null	显式股票列表，优先于 limit
universe	string | string[]	否	null	支持品种列表 ["IF","IC"]，合并后自动去重；兼容 IF+IC 字符串
start	string	否	2021-08-21	天梯固定五年区间起始日；自定义研究可显式覆盖
end	string	否	2026-08-20	天梯固定五年区间截止日；自定义研究可显式覆盖
alpha360	bool	否	false	同时缓存 Alpha360 因子（360 个，计算量约为 Alpha158 的 2 倍）
# 请求
curl -sk -X POST https://markethon.fit:19371/data/load \
  -H 'Content-Type: application/json' \
  -d '{"limit": 200, "start": "2023-01-01", "end": "2024-12-31", "alpha360": true}'

# 响应 200
{
  "loaded": true,
  "symbols": 10,
  "trading_days": 484,
  "date_range": ["2023-01-03", "2024-12-31"],
  "alpha158_factors": 158,
  "alpha360_factors": 360
}
因子
GET/factors
列出可用因子。未加载数据返回 400。
# 响应示例（加载 alpha360=true 后多出 alpha360 键，360 个因子名）
{
  "alpha158": ["BETA10", "BETA20", "..."],
  "alpha360": ["CLOSE0", "CLOSE1", "..."],
  "custom": {"RET5": "($close-Ref($close,5))/Ref($close,5)"}
}
POST/factors/define
注册 qlib 表达式因子（安全沙箱，无代码执行）。注册时用单只股票试算校验，非法表达式立即返回 400。变量 $open $high $low $close $volume $vwap；函数 Mean/Std/Max/Min/Sum/Ref/Delta/Corr/Rank/Slope/Rsqr/Resi/Log/Abs/Sign 等。
字段	类型	必填	说明
name	string	是	因子名（自动转大写）
expression	string	是	qlib 表达式，≤1000 字符
# 请求
curl -sk -X POST https://markethon.fit:19371/factors/define \
  -H 'Content-Type: application/json' \
  -d '{"name": "RET5", "expression": "($close-Ref($close,5))/Ref($close,5)"}'

# 响应 200
{"registered": "RET5", "expression": "($close-Ref($close,5))/Ref($close,5)"}

# 响应 400（表达式非法）
{"detail": "表达式无法计算: bad operand type for unary -: 'Sub'"}
评估
POST/factors/evaluate
对指定因子做 IC 评估（spearman rank IC，向量化实现），返回按 |ICIR| 降序的记录。
字段	类型	必填	默认	说明
names	string[]	是	—	因子名列表
periods	int[]	否	[1,5,10]	前瞻收益持有期（交易日）
quantiles	int	否	5	分组数
top_n	int	否	50	返回条数
响应记录字段：factor、IC均值、ICIR、t统计量、IC>0占比、多空收益（各持有期平均）。/factors/evaluate_all 参数相同但无需 names，多一个 factor_set 字段（alpha158 默认 158 个 / alpha360 360 个 / all 两者合并 518 个；后两者需加载时 alpha360=true）。
# 请求
curl -sk -X POST https://markethon.fit:19371/factors/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"names": ["ROC5", "STD20"], "periods": [1, 5]}'

# 响应 200
{
  "count": 2,
  "factors": [
    {"factor": "STD20", "IC均值": -0.048, "ICIR": -0.1306,
     "t统计量": -2.8614, "IC>0占比": 0.451, "多空收益": -0.0004},
    {"factor": "ROC5", "IC均值": 0.0148, "ICIR": 0.0406,
     "t统计量": 0.884, "IC>0占比": 0.5232, "多空收益": 0.0006}
  ]
}
POST/jobs/evaluate ＋ GET/jobs/{job_id}
异步 IC 评估：POST /jobs/evaluate 后台启动任务并立即返回 job_id（参数同 /factors/evaluate，names=null 表示批量评估整个因子集，可用 factor_set 选 alpha158 / alpha360 / all）；用 GET /jobs/{job_id} 轮询进度与结果，适合网页等需要展示进度的场景。
进度响应字段	类型	说明
status	string	running / done / error
done / total	int	已完成因子数 / 总因子数
current	string	最近完成的因子名
elapsed_s	float	已用秒数
eta_s	float|null	预计剩余秒数（刚启动时为 null）
result	object	done 时附，结构同 /factors/evaluate 响应
# 启动任务
curl -sk -X POST https://markethon.fit:19371/jobs/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"names": null, "periods": [1, 5, 10]}'
# → {"job_id": "a1b2c3d4e5f6"}

# 轮询进度
curl -sk https://markethon.fit:19371/jobs/a1b2c3d4e5f6
# → {"status": "running", "done": 42, "total": 158,
#    "current": "KLEN", "elapsed_s": 4.2, "eta_s": 11.6}
# 完成后 status=done 并附 result；job_id 不存在返回 404
回测
POST/backtest/quantile
多因子合成打分 + 分组回测。多空模式的空头腿不做空个股，而是做空用户选择的 IC/IF/IH/IM 期指主力连续：策略收益＝高分个股多头收益 − 指数收益。当前未另行扣除期指基差、移仓和手续费。
字段	类型	必填	默认	说明
names	string[]	是	—	参与合成的因子
weights	object	否	null	{"KMID": 1, "ROC5": -1}
long_short	bool	否	true	个股多头 − 指数空头 / 纯多头
periods	int	否	5	调仓周期（交易日）
quantiles	int	否	5	分组数
benchmark	string	多空时是	null	空头指数：IC/IF/IH/IM
响应：metrics（多空/多头总收益、年化收益、年化波动、夏普、最大回撤、胜率、交易日数）+ nav（主净值序列 {日期: 净值}）+ series（全部曲线：多头、多空（多空时）、Q1..QN 各分组净值，键为曲线名、值为 {日期: 净值}）。净值中的非法数值（NaN/Inf）以 null 表示。
# 请求
curl -sk -X POST https://markethon.fit:19371/backtest/quantile \
  -H 'Content-Type: application/json' \
  -d '{"names": ["ROC5", "KMID"], "periods": 5, "quantiles": 2}'

# 响应 200（nav 与 series 已截断）
{
  "metrics": {"多空总收益": "2.04%", "多空年化收益": "1.07%",
              "多空夏普": "0.130", "多空最大回撤": "-5.32%", "...": "..."},
  "nav": {"2023-01-11": 0.999, "2023-01-12": 0.9991, "...": "..."},
  "series": {
    "多头": {"2023-01-11": 1.0034, "...": "..."},
    "多空": {"2023-01-11": 0.9904, "...": "..."},
    "Q1":   {"2023-01-11": 1.013,  "...": "..."},
    "Q2":   {"2023-01-11": 0.9886, "...": "..."}
  }
}
POST/backtest/walk_forward
滚动验证：训练期选因子定权重（默认 legacy 按 |ICIR| 排序，可选 robust 稳定性筛选）→ 测试期回测 → 窗口滚动，无前视偏差。
字段	类型	必填	默认	说明
names	string[]	是	—	候选因子池
train_months	int	否	12	训练窗口月数
test_months	int	否	3	测试窗口月数
step_months	int	否	3	滚动步长（月）
long_short	bool	否	true	个股多头 − 指数空头 / 纯多头
quantiles	int	否	5	分组数
rebalance_periods	int	否	5	调仓周期（交易日）
category_counts	object	否	每类 1	{"动量": 2, "波动率": 0}，各类按 |ICIR| 选取数量
uncategorized_count	int	否	5	Alpha360/自定义等未分类因子的选取数
selection_method	string	否	"legacy"	训练期选因子方式：legacy=仅按 |ICIR| 排序（默认）；robust=半样本稳定性筛选 + 训练期去相关 + 权重向等权收缩
min_abs_icir	float	否	0.10	（仅 robust）最低 |ICIR| 及半样本稳定分数
min_abs_ic	float	否	0.005	（仅 robust）最低 |IC|
corr_threshold	float	否	0.75	（仅 robust）因子截面秩相关剔除阈值
weight_shrinkage	float	否	0.50	（仅 robust）ICIR 权重向等权收缩强度（0=纯 ICIR 加权，1=等权）
benchmark	string	多空时是	null	空头指数：IC/IF/IH/IM
submit_score	bool	否	false	是否保存本次 0–100 标准分；天梯统一回测区间为 2021-08-21 至 2026-08-20、初始本金 1 亿元，且股票数量不少于 500 只
响应在分组回测基础上增加 windows、standard_score；提交成功时增加 submission。天梯区间不符合 2021-08-21 至 2026-08-20、股票数量少于 500 只或其他硬门槛不满足时，回测仍会返回，但成绩不写入天梯，响应增加 submission_skipped。所有用户初始本金固定为人民币 1 亿元，A 股订单按 100 股整手取整。标准分 v3 权重：夏普 25%、年化收益 25%、年化 Alpha 20%、最大回撤 15%、回撤持续 15%。
# 响应 200（节选）
{
  "metrics": {"滚动验证多空总收益": "-3.06%", "..."},
  "nav": {"2024-01-03": 1.0, "..."},
  "windows": [
    {"window": 1, "train_start": "2023-01-03", "train_end": "2024-01-02",
     "test_start": "2024-01-03", "test_end": "2024-04-02",
     "selected_factors": ["KMID", "ROC5", "STD20", "VMA10"],
     "selection_method": "legacy",
     "weights": {"KMID": -0.62, "ROC5": -0.17, "...": "..."},
     "top_icir": {"KMID": -0.026, "ROC5": -0.0073}}
  ]
}
选股
POST/selection
按截面 z-score 加权打分排序。打分后先按截面日最低成交额和最低上市自然日数做硬过滤，再返回多头推荐与空头警示。上市日期以 ClickHouse 中该股票最早日线日期为准。
字段	类型	必填	默认	说明
names	string[]	是	—	参与打分的因子
weights	object	否	null	同回测 weights
top_n	int	否	20	多头/空头各返回数量
date	string	否	null	截面日期，null 为最新交易日
min_amount_cny	float	否	0	截面日最低成交额（元），0 为不限制
min_listed_days	int	否	0	最低上市自然日数，0 为不限制
# 响应 200（top_n=2 节选）
{
  "date": "2024-12-31",
  "filters": {"min_amount_cny": 50000000, "min_listed_days": 180, "before_filter": 200, "eligible": 146},
  "long_top": [
    {"symbol": "000010.SZ", "score": 0.9076, "close": 2.81, "amount_cny": 98650000, "listed_days": 2460},
    {"symbol": "000006.SZ", "score": 0.8207, "close": 7.32, "amount_cny": 77120000, "listed_days": 3120}
  ],
  "short_bottom": [
    {"symbol": "000007.SZ", "score": -1.1317, "close": 7.03, "amount_cny": 65300000, "listed_days": 1980},
    {"symbol": "000001.SZ", "score": -0.369, "close": 8.75, "amount_cny": 120600000, "listed_days": 12320}
  ]
}
MCP 工具（大模型客户端接入）
支持两种传输：公网 Streamable HTTP 端点 https://markethon.fit:19371/mcp（Bearer token 认证），以及服务器本机 stdio（python server/mcp_server.py）。 工具与 HTTP API 一一对应、同名同参数：service_status、list_symbols、load_data（含 alpha360 参数）、list_factors、define_factor、evaluate_factors、evaluate_all_alpha158（含 factor_set 参数，可评估 alpha158/alpha360/all）、backtest_quantile、walk_forward_backtest、select_stocks。 注意：/mcp 是 MCP 协议端点，不是 REST 端点，所以不会出现在 OpenAPI/Swagger 的接口列表中。Streamable HTTP 与网页/API 共用服务进程和用户状态；单独启动的 stdio 进程则持有自己的内存视图。
# 远程 MCP 客户端配置（Kimi Code / Claude Desktop 等）
{
  "mcpServers": {
    "factor-eval": {
      "url": "https://markethon.fit:19371/mcp",
      "headers": {"Authorization": "Bearer <TOKEN>"}
    }
  }
}

# 服务器本机 stdio 配置
{
  "mcpServers": {
    "factor-eval": {
      "command": "/home/userroot/桌面/factor-eval/.venv/bin/python",
      "args": ["/home/userroot/桌面/factor-eval/server/mcp_server.py"]
    }
  }
}