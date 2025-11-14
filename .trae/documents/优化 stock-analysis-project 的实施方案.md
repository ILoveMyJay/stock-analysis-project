## 项目分析摘要
- 前后端分离：后端 FastAPI + SQLite + AkShare（行情与基本面 + 策略计算），前端 Vite + Vue3 + ECharts + Axios（可视化与交互）
- 核心入口与路由：`backend/main.py` 的 `app = FastAPI()` (backend/main.py:15)，API 路由包括 `GET /api/stock/{code}` (backend/main.py:1099)、`GET /api/stock/{code}/strategies` (backend/main.py:1170)、`GET /api/stocks` (backend/main.py:1216)
- 关键策略与数据：基本面获取 `get_real_fundamental_data` (backend/main.py:662)、及时财务 `get_timely_financial_data` (backend/main.py:793)、PEG 策略 `analyze_peg_strategy` (backend/main.py:920)，技术指标与策略（MA/MACD/RSI/BOLL/动量/突破）分布在 248–574 行段

## 后端优化（性能、稳定性、工程化）
1. 缓存与并发
- 为日线行情（AkShare）增加二级缓存（SQLite/文件 + 内存 LRU），设置过期与刷新策略；保留现有基本面缓存但统一源标识（真实/缓存/回退）
- 将外部 IO（AkShare）与重计算迁移到后台任务或线程池，避免阻塞事件循环（`asyncio.to_thread`）
2. 启动与依赖
- 将 `init_database()` (backend/main.py:26) 与 `clean_expired_cache()` (backend/main.py:133) 挪到 FastAPI `startup` 事件钩子
- 补全 `backend/requirements.txt` 或 `pyproject.toml`，锁版本；移除未使用依赖（如未用的 `LinearRegression`）
3. 数据库与日志
- 开启 `PRAGMA journal_mode=WAL`，为热点字段建索引（如 `stocks.stock_code`）；避免每次全量覆写策略结果
- 细化异常分类与重试（指数退避），将 `print` 替换为结构化日志并写入 `error_logs` 表；增加耗时与缓存命中率埋点

## 策略与数据质量（可配置与鲁棒性）
- 统一滚动窗口不足与空值处理，减少 NaN 传播；在返回结构中统一 `insufficient_data`
- 将策略参数（均线窗口、BOLL 标准差、动量回看期、突破量比等）提取为可配置项（后端默认 + API 透传），前端可交互调整
- 对返回值添加来源元数据（真实/缓存/回退、更新时间、周期），统一单位与格式

## 前端优化（体验与工程化）
- 在 `vite.config.js` 配置 `server.proxy` 指向后端，移除硬编码 `http://127.0.0.1:8000` 与过宽的 CORS
- 统一 Axios 基地址与拦截器，增加错误提示与重试；抽离策略文案常量，减少组件体积
- 图表性能：开启 `ECharts` `large`/采样模式或只渲染最近 N 日；在窗口 resize 时 `echarts.resize()`；清理销毁实例避免内存泄漏

## 工程与交付（可观测性与部署）
- 增加健康检查与版本端点；错误日志表索引与统计接口（耗时、命中率）
- 统一启动脚本；可选提供 `Dockerfile` 与 `docker-compose` 以便一键启动
- 引入基础测试：后端路由与策略单元测试；前端组件与接口契约测试

## 里程碑
- M1：后端缓存与并发改造、启动钩子与依赖文件完善
- M2：策略参数化与数据来源元数据、数据库索引与日志指标
- M3：前端代理与 Axios 抽象、图表性能优化与资源管理
- M4：测试与监控补充、可选容器化与一键启动

请确认是否按上述计划推进，我将在获得确认后开始逐项实施并验证。