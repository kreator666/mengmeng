# 量化回测系统（mengmeng）线上运维指南

> 更新日期：2026-09-18
> 适用环境：阿里云服务器（SSH 别名 `aliyun`，公网 IP `47.253.171.222`），线上域名 `https://quant.freetoken.xin`
> 参考：FreeToken 运维指南（`doc/deploy-ops-guide-2026-09-04.md`），两系统同机部署

## 1. 架构总览

```
用户浏览器
    │ HTTPS (443)
    ▼
nginx（/etc/nginx/conf.d/quant.conf）
    │ proxy_pass http://quant-frontend  →  127.0.0.1:5173
    ▼
Docker Compose 项目 mengmeng（~/mengmeng）
    ├── 容器 mengmeng-frontend-1（nginx:alpine，端口 5173→80）
    │     ├── 静态托管前端构建产物（React + Vite dist）
    │     └── location /api → proxy_pass http://backend:8000（compose 内网）
    └── 容器 mengmeng-backend-1（python:3.11-slim，端口 8855→8000）
          ├── CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000
          ├── 挂卷 ~/mengmeng/data → /app/data（K线缓存、回测结果、扫描结果、sentinel.db）
          └── 挂卷 ~/mengmeng/factor → /factor（只读，chain_sentinel 依赖的研究版因子模块）
```

关键事实：

- **宿主机代码目录**：`~/mengmeng`（GitHub 仓库 `kreator666/mengmeng` 的克隆，部署分支 `markthon`）。
- **线上跑的是 Docker Compose 两个容器**，与同机的 freetoken（3099）、propfirm-db（postgres）、searxng 共存，互不影响。
- 对外入口只有两个：前端 `5173`（nginx 反代目标）和后端 `8855`（API，可不对外）。用 `sudo ss -tlnp | grep -E '5173|8855'` 确认，应显示 `docker-proxy`。
- 前端容器内的 nginx 把 `/api` 反代到 `http://backend:8000`（compose 服务名），**浏览器不直接访问 8855**。

## 2. 连接服务器

```bash
ssh aliyun        # 免密登录，用户 admin，有 sudo 权限
```

## 3. 发布更新流程（改完代码 push 之后）

```bash
ssh aliyun
cd ~/mengmeng

# 1) 备份线上数据（每次发布前必做，见第 5 节）
cp -r data data.bak-$(date +%Y%m%d-%H%M%S)

# 2) 拉最新代码
git pull origin markthon

# 3) 重建镜像并重启容器（秒级中断，数据已挂卷不会丢）
docker compose build
docker compose up -d
```

说明：

- `docker compose build` 全量构建约 2 分钟（后端 pip 安装 pandas/numpy 等 + 前端 npm ci + vite build）。
- 只改了后端代码可单独构建：`docker compose build backend && docker compose up -d backend`。
- 两容器均配置 `restart: unless-stopped`，服务器重启后自动拉起；无 pm2 / systemd 托管。

## 4. 发布后验证

```bash
docker compose ps                                   # backend 应为 Up (healthy)，frontend 为 Up
curl -s http://127.0.0.1:8855/health                # 直连后端，应输出 {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/                     # 前端 200
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5173/api/factor/builtins  # 经前端反代的 API 200
curl -s -o /dev/null -w '%{http_code}' https://quant.freetoken.xin/               # 线上 200
```

## 5. 数据备份与恢复

- 线上数据目录：`~/mengmeng/data`（宿主机侧，已挂卷到 `/app/data`），包含：
  - `cache/`：K 线缓存（parquet）、美股历史
  - `results/`：回测结果
  - `scanner_results/`：底部趋势 / v11 策略扫描结果
  - `sentinel.db`、`sentinel_config.json`、`us_stock_config.json`：逃顶哨兵数据与配置
- **每次发布前备份**：`cp -r data data.bak-YYYYmmdd-HHMMSS`。
- 恢复：`docker compose stop` → 用备份目录覆盖 `data/` → `docker compose up -d`。
- `factor/` 目录为**只读挂卷**（代码，非数据），随 git pull 更新，无需备份。

## 6. 常用排障命令

```bash
# 容器日志
cd ~/mengmeng
docker compose logs backend --tail 100
docker compose logs frontend --tail 50

# 谁占着端口（应看到 docker-proxy）
sudo ss -tlnp | grep -E ':(5173|8855)'

# 进后端容器排查（如验证 /factor 挂载）
docker compose exec backend ls /factor

# nginx 配置与重载
/etc/nginx/conf.d/quant.conf
sudo nginx -t && sudo systemctl reload nginx

# 磁盘占用（本机磁盘 40G，曾到 98%，需定期清理）
df -h /
docker system df
docker image prune -f          # 清 dangling 镜像
docker builder prune -f        # 清构建缓存
```

## 7. HTTPS 证书（DNS 生效后执行一次）

现有 `/etc/nginx/ssl/freetoken.crt` **不是通配证书**（仅 freetoken.xin / www.freetoken.xin），`quant.freetoken.xin` 需要单独签发：

```bash
# 前提：DNS 已添加 quant A 记录指向 47.253.171.222
sudo certbot certonly --webroot -w /home/admin/certbot -d quant.freetoken.xin
# 然后在 /etc/nginx/conf.d/quant.conf 中增加 443 server 块，
# 证书路径为 /etc/letsencrypt/live/quant.freetoken.xin/{fullchain,privkey}.pem
sudo nginx -t && sudo systemctl reload nginx
```

## 8. 踩坑记录（2026-09-18 首次部署）

1. **磁盘先清理再构建**。部署前磁盘 98%（仅剩 1.2G），主要是 freetoken 历次构建留下的 dangling 镜像（约 9.4G）+ 构建缓存（1.4G）。`docker image prune -f && docker builder prune -af` 后释放到 73%。
2. **`python:3.11-slim` 没有 curl**，compose 里 `healthcheck` 用 curl 会一直 unhealthy。已改为 `python -c "import urllib.request;..."`。
3. **后端依赖仓库根目录的 `factor/` 模块**。`chain_sentinel_service.py` 用 `parents[3]/factor` 定位，容器内解析为 `/factor`，必须在 compose 里挂 `./factor:/factor:ro`，否则 uvicorn 启动即 `ModuleNotFoundError: No module named 'openai_chain_sentinel'`。
4. **freetoken 的证书不覆盖 quant 子域名**（非通配），需 certbot 单独签发，见第 7 节。
5. 服务器内存 1.8G + 4G swap，两镜像并行构建无压力；若以后构建变慢/OOM，可改 `docker compose build backend`、`- frontend` 分开构建。

## 9. 相关路径速查

| 项目 | 位置 |
| --- | --- |
| 宿主机代码 | `~/mengmeng`（分支 `markthon`） |
| Compose 文件 | `~/mengmeng/docker-compose.yml` |
| 后端入口 | `backend/app/main.py`（uvicorn，容器内 8000 / 宿主 8855） |
| 前端 nginx 配置 | `frontend/Dockerfile` 内嵌（/api → backend:8000） |
| 数据目录 | `~/mengmeng/data`（挂卷 /app/data） |
| 因子模块 | `~/mengmeng/factor`（只读挂卷 /factor） |
| nginx 配置 | `/etc/nginx/conf.d/quant.conf` |
| HTTPS 证书 | `/etc/letsencrypt/live/quant.freetoken.xin/`（certbot 签发后） |
| GitHub 仓库 | `git@github.com:kreator666/mengmeng.git` |
