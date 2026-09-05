"""列出当前 Markethon 已注册因子，保存到 JSON。"""
import asyncio, json, os
import httpx

BASE = os.environ.get("MARKETHON_BASE_URL", "https://markethon.fit:19371").rstrip("/")
USER = os.environ.get("MARKETHON_USERNAME", "darkspell")
PWD = os.environ.get("MARKETHON_PASSWORD", "darkwave30133")

async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/auth/login", json={"username": USER, "password": PWD},
                         headers={"Content-Type":"application/json"})
        r.raise_for_status()
        token = r.json().get("access_token") or r.json().get("token")
        r = await c.get(f"{BASE}/factors", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        data = r.json()
        raw = data.get("factors", data.get("names", data.get("data", [])))
        names = [f.get("name") or f.get("factor") for f in raw]
        out = {"count": len(names), "factors": names}
        path = "d:/agent/mengmeng/backend/data/markethon_registered_factors.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"已注册因子数: {len(names)}")
        print(f"保存到: {path}")

if __name__ == "__main__":
    asyncio.run(main())
