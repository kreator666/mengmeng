import asyncio
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.notify import (
    build_message, load_config, make_notifier, smtp_ready, webhook_ready,
)


def test_make_notifier_none_when_disabled():
    print("=" * 60)
    print("测试推送：未配置时返回 None")
    print("=" * 60)

    assert make_notifier({}) is None
    assert make_notifier({"smtp": {"enabled": False}, "webhook": {"enabled": False}}) is None
    assert make_notifier({"smtp": {"enabled": True}}) is None  # 字段不全
    print("   [OK] 未配置/字段不全均不启用\n")


def test_notifier_sends_once_per_channel():
    print("=" * 60)
    print("测试推送：SMTP/webhook 各发一次，任一成功即 True")
    print("=" * 60)

    cfg = {
        "smtp": {"enabled": True, "host": "smtp.test", "port": 465,
                 "username": "u", "password": "p", "from_addr": "a@t", "to_addrs": ["b@t"]},
        "webhook": {"enabled": True, "url": "http://hook.test/abc"},
    }
    assert smtp_ready(cfg) and webhook_ready(cfg)
    notifier = make_notifier(cfg)
    assert notifier is not None

    detail = {"date": "2026-07-18", "reasons": {"light": ["综合评分75≥70"], "price": ["x"]}}

    with mock.patch("app.core.notify._send_smtp") as m_smtp, \
         mock.patch("app.core.notify._send_webhook") as m_hook:
        m_hook.return_value = True
        ok = asyncio.run(notifier("yellow", "red", 75.0, detail))
        assert ok is True
        m_smtp.assert_called_once()
        title, body = build_message("yellow", "red", 75.0, detail)
        assert "黄·警惕 → 红·逃顶信号" in title and "75/100" in body and "综合评分75≥70" in body
        m_hook.assert_called_once()
        print("   [OK] 双通道各发一次，标题正文正确")

    # 通道全失败 → False
    with mock.patch("app.core.notify._send_smtp", side_effect=Exception("smtp down")), \
         mock.patch("app.core.notify._send_webhook", side_effect=Exception("hook down")):
        ok = asyncio.run(notifier("yellow", "red", 75.0, detail))
        assert ok is False
        print("   [OK] 双通道失败返回 False（不抛异常）\n")


def test_load_config(tmp_ok=True):
    print("=" * 60)
    print("测试推送：配置文件读取")
    print("=" * 60)

    cfg = load_config()
    assert "scheduler" in cfg and "smtp" in cfg and "webhook" in cfg
    assert cfg["scheduler"]["enabled"] is True
    print(f"   [OK] 默认配置：定时 {cfg['scheduler']['hour']}:{cfg['scheduler']['minute']:02d} "
          f"{cfg['scheduler']['timezone']}，推送默认关闭\n")


if __name__ == "__main__":
    test_make_notifier_none_when_disabled()
    test_notifier_sends_once_per_channel()
    test_load_config()
    print("全部推送模块测试通过")
