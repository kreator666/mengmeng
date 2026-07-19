"""
逃顶信号推送模块

通道（backend/data/sentinel_config.json 配置，未启用则只存档不推送）：
- SMTP 邮件（QQ/163 邮箱授权码）
- 通用 webhook（POST JSON {title, text}，兼容 Server酱/Bark/企业微信机器人）

灯色含义：green 正常 / yellow 警惕 / red 逃顶信号
"""

import asyncio
import json
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import aiohttp

CONFIG_FILE = Path(__file__).resolve().parents[2] / "data" / "sentinel_config.json"

LIGHT_LABEL = {"green": "绿·正常", "yellow": "黄·警惕", "red": "红·逃顶信号"}


def load_config(path: Path | None = None) -> dict[str, Any]:
    file = path or CONFIG_FILE
    if not file.is_file():
        return {}
    try:
        with open(file, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def build_message(from_light: str, to_light: str, total_score: float,
                  detail: dict[str, Any]) -> tuple[str, str]:
    """构造推送标题与正文"""
    title = f"算力链风险信号：{LIGHT_LABEL.get(from_light, from_light)} → {LIGHT_LABEL.get(to_light, to_light)}"
    lines = [
        f"综合评分：{total_score:.0f}/100",
        f"数据日期：{detail.get('date', '')}",
        "",
    ]
    reasons = detail.get("reasons", {})
    for layer, label in [("light", "判级"), ("price", "价格层"), ("news", "新闻层"), ("dashboard", "仪表盘层")]:
        items = reasons.get(layer) or []
        if items:
            lines.append(f"【{label}】")
            lines += [f"  - {r}" for r in items]
    return title, "\n".join(lines)


def _send_smtp(cfg: dict[str, Any], title: str, body: str) -> bool:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = cfg["from_addr"]
    msg["To"] = ",".join(cfg["to_addrs"])
    with smtplib.SMTP_SSL(cfg["host"], int(cfg.get("port", 465)), timeout=30) as server:
        server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["from_addr"], cfg["to_addrs"], msg.as_string())
    return True


async def _send_webhook(url: str, title: str, body: str) -> bool:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json={"title": title, "text": body},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            return resp.status < 400


def smtp_ready(cfg: dict[str, Any]) -> bool:
    s = cfg.get("smtp", {})
    return bool(s.get("enabled") and s.get("host") and s.get("username")
                and s.get("password") and s.get("from_addr") and s.get("to_addrs"))


def webhook_ready(cfg: dict[str, Any]) -> bool:
    w = cfg.get("webhook", {})
    return bool(w.get("enabled") and w.get("url"))


def make_notifier(config: dict[str, Any] | None = None):
    """
    生成推送器（async callable）；两个通道都未配置时返回 None
    任一通道成功即视为已推送
    """
    cfg = config if config is not None else load_config()
    use_smtp = smtp_ready(cfg)
    use_webhook = webhook_ready(cfg)
    if not use_smtp and not use_webhook:
        return None

    async def notify(from_light: str, to_light: str, total_score: float,
                     detail: dict[str, Any]) -> bool:
        title, body = build_message(from_light, to_light, total_score, detail)
        ok = False
        if use_smtp:
            try:
                ok = await asyncio.to_thread(_send_smtp, cfg["smtp"], title, body) or ok
            except Exception:
                pass
        if use_webhook:
            try:
                ok = await _send_webhook(cfg["webhook"]["url"], title, body) or ok
            except Exception:
                pass
        return ok

    return notify
