# FreeToken 线上运维指南

> 更新日期：2026-09-04
> 适用环境：阿里云服务器（SSH 别名 `aliyun`），线上域名 `https://freetoken.xin`

## 1. 架构总览

```
用户浏览器
    │ HTTPS (443)
    ▼
nginx（/etc/nginx/conf.d/dreamlab.conf）
    │ proxy_pass http://freetoken  →  127.0.0.1:3099
    ▼
Docker 容器 freetoken（镜像 freetoken，端口 3099）
    │ CMD: pnpm dev  →  node --import tsx ads-platform/server.ts
    ▼
Express 服务（ADS_HOST=0.0.0.0, ADS_PORT=3099）
    ├── 静态文件：/app/ads-platform/public（首页、任务墙、仪表盘）
    └── SQLite 数据库：/app/ads-platform/data/ads.sqlite（用户积分）
```

关键事实：

- **宿主机代码目录**：`~/freetoken`（即 GitHub 仓库 `kreator666/freetoken` 的克隆）。
- **线上跑的是 Docker 容器，不是宿主机直接跑的进程**。容器进程在宿主机 `ps aux` 里以 root 显示（`pnpm dev` / `node --import tsx ...`），**不要误杀**——那就是线上服务本身。
- nginx 只代理到 `127.0.0.1:3099`，谁占用 3099 谁就是线上服务。用 `sudo ss -tlnp | grep 3099` 确认，应显示 `docker-proxy`。

## 2. 连接服务器

本机 `~/.ssh/config` 已配置别名（密钥文件不收录进本文档）：

```bash
ssh aliyun        # 免密登录，用户 admin，有 sudo 权限
```

## 3. 发布更新流程（改完代码 push 之后）

```bash
ssh aliyun

# 1) 备份线上数据库（每次发布前必做，见第 5 节）
cd ~/freetoken
cp ads-platform/data/ads.sqlite ads-platform/data/ads.sqlite.bak-$(date +%Y%m%d-%H%M%S)

# 2) 拉最新代码
git pull origin main

# 3) 重建镜像（Dockerfile 会 pnpm install + 编译 better-sqlite3，约几分钟）
docker build -t freetoken .

# 4) 重建容器（秒级中断，数据已挂卷不会丢）
docker stop freetoken && docker rm freetoken
docker run -d --name freetoken \
  --restart unless-stopped \
  -p 3099:3099 \
  -v /home/admin/freetoken/ads-platform/data:/app/ads-platform/data \
  freetoken
```

容器参数说明：

| 参数 | 含义 |
| --- | --- |
| `--restart unless-stopped` | 服务器重启后容器自动拉起（与原配置一致） |
| `-p 3099:3099` | 对外服务端口，nginx 反代目标 |
| `-v .../data:/app/ads-platform/data` | **积分数据库持久化**，2026-09-04 起添加；之前数据在容器层，重建容器会丢 |

## 4. 发布后验证

```bash
docker ps --filter name=freetoken          # 状态应为 Up
curl -s http://127.0.0.1:3099/ | head      # 直连容器，确认新内容
curl -s -o /dev/null -w '%{http_code}' https://freetoken.xin/   # 应输出 200
```

## 5. 数据库备份与恢复

- 线上数据库文件：`~/freetoken/ads-platform/data/ads.sqlite`（宿主机侧，已挂卷）。
- **每次发布前备份**：`cp ads.sqlite ads.sqlite.bak-YYYYmmdd-HHMMSS`。
- 恢复：停容器 → 用备份文件覆盖 `ads.sqlite` → 启动容器。
- 宿主机上原有的 `ads.sqlite`（9月3日的副本）与容器内数据是两份独立拷贝，挂卷后以宿主机这份为准。

## 6. 常用排障命令

```bash
# 容器日志（pnpm dev / Express 输出）
docker logs freetoken --tail 100

# 谁占着 3099（应看到 docker-proxy）
sudo ss -tlnp | grep 3099

# 看首页实际返回的内容
curl -s http://127.0.0.1:3099/ | grep 关键字

# 查某进程是否属于容器（cgroup 带 /docker/<id> 即为容器进程）
sudo cat /proc/<PID>/cgroup

# nginx 配置位置
/etc/nginx/conf.d/dreamlab.conf
```

## 7. 踩坑记录

1. **`ps aux` 里的 root `pnpm dev` 不是残留进程**——是 freetoken 容器自身的进程（容器进程在宿主 PID 命名空间可见）。2026-09-04 曾误判为残留进程，实际旧容器的进程随 `docker rm` 已正常消亡。
2. **重建容器前必须先导出数据库**。2026-09-04 之前数据存在容器可写层里，直接 `docker rm` 会丢用户积分；当天已改为挂卷方式并补做了备份。
3. 镜像构建需要编译原生模块（better-sqlite3），Dockerfile 里已用 `node-gyp rebuild` 处理；若换基础镜像或 Node 版本需重新验证这一步。
4. 服务器上无 pm2、无 systemd 服务托管，进程保活完全依赖 Docker 的 `--restart unless-stopped`。

## 8. 相关路径速查

| 项目 | 位置 |
| --- | --- |
| 宿主机代码 | `~/freetoken` |
| 首页静态文件 | `ads-platform/public/index.html` |
| Express 入口 | `ads-platform/server.ts` |
| 数据库 | `ads-platform/data/ads.sqlite` |
| nginx 配置 | `/etc/nginx/conf.d/dreamlab.conf` |
| GitHub 仓库 | `git@github.com:kreator666/freetoken.git` |
