#!/usr/bin/env python3
"""IBKR 自动重连脚本。
检测连接断开时自动重启 IB Gateway 并重连后端。
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ibkr-reconnect")

IBC_SCRIPT = os.path.expanduser("~/IBC/gatewaystart.sh")
BACKEND_PID_FILE = "/tmp/usstock-backend.pid"
CHECK_INTERVAL = 60  # 每60秒检查一次
RECONNECT_COOLDOWN = 120  # 重连后冷却120秒


def is_gateway_running() -> bool:
    """检查 IB Gateway 是否在运行。"""
    try:
        result = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=5
        )
        return ":7497" in result.stdout
    except Exception:
        return False


def kill_gateway():
    """杀掉 IB Gateway 进程。"""
    try:
        subprocess.run(
            ["pkill", "-f", "java.*ibgateway"], capture_output=True, timeout=5
        )
        logger.info("Killed existing IB Gateway")
        time.sleep(3)
    except Exception as e:
        logger.warning("Kill gateway failed: %s", e)


def start_gateway():
    """启动 IB Gateway。"""
    env = os.environ.copy()
    env["DISPLAY"] = ":99"
    try:
        subprocess.Popen(
            [IBC_SCRIPT, "-inline"],
            stdout=open("/tmp/ibgateway-reconnect.log", "w"),
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        logger.info("IB Gateway starting...")
        # 等待端口开放
        for _ in range(30):
            time.sleep(2)
            if is_gateway_running():
                logger.info("IB Gateway port 7497 is listening")
                return True
        logger.error("IB Gateway failed to start within 60s")
        return False
    except Exception as e:
        logger.error("Start gateway failed: %s", e)
        return False


def restart_backend():
    """重启后端进程。"""
    try:
        # 找到后端进程
        result = subprocess.run(
            ["pgrep", "-f", "uvicorn app.main"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            for pid in result.stdout.strip().split("\n"):
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            logger.info("Killed backend process(es)")
            time.sleep(3)

        # 重启后端
        subprocess.Popen(
            [
                "/usr/bin/python3", "-m", "uvicorn",
                "app.main:app",
                "--host", "0.0.0.0",
                "--port", "8001",
                "--loop", "asyncio",
            ],
            stdout=open("/tmp/usstock-backend.log", "w"),
            stderr=subprocess.STDOUT,
            cwd=os.path.expanduser("~/project/usstock/backend"),
            env={**os.environ, "PYTHONPATH": os.path.expanduser("~/project/usstock/backend")},
            start_new_session=True,
        )
        logger.info("Backend restarting...")
        time.sleep(10)
        return True
    except Exception as e:
        logger.error("Restart backend failed: %s", e)
        return False


def main():
    logger.info("IBKR reconnect monitor started (check every %ds)", CHECK_INTERVAL)
    last_reconnect = 0

    while True:
        try:
            now = time.time()

            if not is_gateway_running():
                if now - last_reconnect < RECONNECT_COOLDOWN:
                    logger.info("Gateway down but in cooldown, waiting...")
                else:
                    logger.warning("IB Gateway not running, restarting...")
                    kill_gateway()
                    if start_gateway():
                        restart_backend()
                        last_reconnect = now
                    else:
                        logger.error("Failed to restart IB Gateway")
            else:
                logger.debug("IB Gateway running OK")

        except Exception as e:
            logger.error("Monitor error: %s", e)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
