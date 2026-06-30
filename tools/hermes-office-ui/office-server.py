#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hermes办公室本地数据桥接服务。

启动方式：
  python office-server.py

访问：
  http://127.0.0.1:8787/hermes-office.html

作用：
- 代理读取 Hermes API Server 的 /health/detailed
- 读取 F:\ml\.hermes-agent\logs\gateway.log 中的平台事件
- 给前端提供 /api/office JSON，避免浏览器 CORS / file:// 限制
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
HERMES_HOME = Path(os.environ.get("HERMES_HOME", r"F:\ml\.hermes-agent"))
GATEWAY_LOG = HERMES_HOME / "logs" / "gateway.log"
CONFIG_FILE = HERMES_HOME / "config.yaml"
HERMES_API = os.environ.get("HERMES_API", "http://127.0.0.1:8642")
PORT = int(os.environ.get("OFFICE_PORT", "8787"))

PLATFORM_META = {
    "feishu": {
        "id": "feishu",
        "name": "飞书 Agent",
        "platform": "Feishu / Lark",
        "role": "企业协作入口",
        "connector": "WebSocket + Bot 授权",
        "icon": "fa-solid fa-paper-plane",
        "className": "platform-feishu",
        "capabilities": ["群聊/私聊", "飞书文档", "审批提醒", "任务分发"],
        "screenLines": ["FEISHU WS", "docs + chat"],
    },
    "weixin": {
        "id": "wechat",
        "name": "微信 Agent",
        "platform": "Weixin / WeChat",
        "role": "个人消息与归档入口",
        "connector": "Weixin Home Channel",
        "icon": "fa-brands fa-weixin",
        "className": "platform-wechat",
        "capabilities": ["私聊通知", "消息归档", "语音转写", "长期记忆"],
        "screenLines": ["WECHAT HOME", "archive=on"],
    },
    "qqbot": {
        "id": "qq",
        "name": "QQ Agent",
        "platform": "QQ Bot",
        "role": "QQ 私聊 / 群聊入口",
        "connector": "QQBot WebSocket",
        "icon": "fa-brands fa-qq",
        "className": "platform-qq",
        "capabilities": ["C2C 消息", "群聊监听", "自动重连", "附件识别"],
        "screenLines": ["QQBOT C2C", "reconnect"],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_tail(path: Path, max_bytes: int = 220_000) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes), os.SEEK_SET)
        data = f.read()
    return data.decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: float = 2.5):
    try:
        with urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def parse_config() -> dict:
    text = CONFIG_FILE.read_text(encoding="utf-8", errors="replace") if CONFIG_FILE.exists() else ""
    def val(key, default=""):
        m = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.M)
        return m.group(1).strip().strip('"') if m else default
    return {
        "path": str(CONFIG_FILE),
        "api_enabled": val("API_SERVER_ENABLED", "false").lower() in {"true", "1", "yes"},
        "api_host": val("API_SERVER_HOST", "127.0.0.1"),
        "api_port": int(val("API_SERVER_PORT", "8642") or 8642),
        "api_key_configured": bool(val("API_SERVER_KEY", "")),
    }


def classify_state(state: str | None, error: str | None = None) -> tuple[str, str]:
    state = (state or "unknown").lower()
    if state == "connected":
        return "在线", "connected"
    if state in {"connecting", "reconnecting"}:
        return "连接中", "connecting"
    if error:
        return "异常", "error"
    if state in {"disconnected", "stopped"}:
        return "离线", "offline"
    return "未知", "unknown"


def log_milestones(platform_key: str, log_text: str) -> list[list[str]]:
    """从 gateway.log 中抽取平台相关里程碑，返回 [date,title,desc]。"""
    items: list[list[str]] = []
    lines = [ln for ln in log_text.splitlines() if platform_key.lower() in ln.lower()]
    # 只取最近事件，避免时间线过长
    interesting = []
    keywords = ["connected", "reconnected", "Disconnected", "inbound message", "C2C message", "Approved", "Unauthorized", "Session resumed", "Sent shutdown notification", "WebSocket error"]
    for ln in lines:
        if any(k.lower() in ln.lower() for k in keywords):
            interesting.append(ln)
    for ln in interesting[-8:]:
        date = ln[:10] if re.match(r"\d{4}-\d{2}-\d{2}", ln) else datetime.now().strftime("%Y-%m-%d")
        lower = ln.lower()
        if "websocket connected" in lower or " connected" in lower:
            title = "平台连接成功"
        elif "reconnected" in lower or "session resumed" in lower:
            title = "自动重连恢复"
        elif "websocket error" in lower:
            title = "连接波动记录"
        elif "inbound message" in lower or "c2c message" in lower:
            title = "收到用户消息"
        elif "approved" in lower:
            title = "用户授权完成"
        elif "unauthorized" in lower:
            title = "待授权用户访问"
        elif "shutdown notification" in lower:
            title = "关停通知送达"
        elif "disconnected" in lower:
            title = "平台断开连接"
        else:
            title = "运行事件"
        desc = re.sub(r"^\d{4}-\d{2}-\d{2} [\d:,]+\s+\w+\s+", "", ln)
        items.append([date, title, desc[:180]])
    return items


def build_agents(health: dict | None, log_text: str) -> list[dict]:
    platforms = (health or {}).get("platforms", {}) if isinstance(health, dict) else {}
    agents = []
    for platform_key, meta in PLATFORM_META.items():
        pstate = platforms.get(platform_key, {}) if isinstance(platforms, dict) else {}
        state_text, state_kind = classify_state(pstate.get("state"), pstate.get("error_message"))
        signal = pstate.get("state") or "not reported"
        if pstate.get("error_message"):
            signal = f"{signal}: {pstate.get('error_message')}"
        milestones = log_milestones(platform_key, log_text)
        if not milestones:
            milestones = [[datetime.now().strftime("%Y-%m-%d"), "平台纳入办公室", f"{meta['name']} 已按平台配置生成工位。"]]
        agent = {
            **meta,
            "statusText": state_text,
            "stateKind": state_kind,
            "signal": signal,
            "handle": extract_handle(platform_key, log_text),
            "updatedAt": pstate.get("updated_at"),
            "milestones": milestones,
        }
        agents.append(agent)
    return agents


def extract_handle(platform_key: str, log_text: str) -> str:
    if platform_key == "qqbot":
        m = re.search(r"\[QQBot:(\d+)\]", log_text)
        return f"Bot {m.group(1)}" if m else "QQBot"
    if platform_key == "feishu":
        m = re.search(r"user=([^\s]+).*platform=feishu|User\s+(ou_[^\s]+)\s+on feishu", log_text)
        if m:
            return next(g for g in m.groups() if g)
        return "Feishu Bot"
    if platform_key == "weixin":
        m = re.search(r"weixin:([^\s]+)", log_text)
        return "weixin:" + m.group(1) if m else "Weixin Home Channel"
    return platform_key


def api_office() -> dict:
    config = parse_config()
    health, health_error = fetch_json(f"{HERMES_API}/health/detailed")
    log_text = read_tail(GATEWAY_LOG)
    agents = build_agents(health, log_text)
    return {
        "ok": True,
        "generated_at": now_iso(),
        "hermes_api": HERMES_API,
        "config": config,
        "health": health,
        "health_error": health_error,
        "agents": agents,
        "stats": {
            "platform_count": len(agents),
            "online_count": sum(1 for a in agents if a.get("stateKind") == "connected"),
            "warning_count": sum(1 for a in agents if a.get("stateKind") not in {"connected"}),
            "gateway_pid": (health or {}).get("pid") if isinstance(health, dict) else None,
            "gateway_state": (health or {}).get("gateway_state") if isinstance(health, dict) else "unknown",
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HermesOffice/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/api/office":
            try:
                self.send_json(api_office())
            except Exception as exc:  # noqa: BLE001
                self.send_json({"ok": False, "error": repr(exc)}, status=500)
            return
        if path in {"/", ""}:
            path = "/hermes-office.html"
        rel = path.lstrip("/").replace("/", os.sep)
        target = (ROOT / rel).resolve()
        if not str(target).startswith(str(ROOT)) or not target.exists() or target.is_dir():
            self.send_error(404, "Not Found")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Hermes办公室服务已启动: http://127.0.0.1:{PORT}/hermes-office.html")
    print(f"数据接口: http://127.0.0.1:{PORT}/api/office")
    print("按 Ctrl+C 停止")
    server.serve_forever()


if __name__ == "__main__":
    main()
