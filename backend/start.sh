#!/bin/bash
# USStock Trading Bot 启动脚本
# 用法: ./start.sh [paper|live]

MODE=${1:-paper}
cd "$(dirname "$0")"

echo "========================================="
echo "  USStock 量化交易系统"
echo "========================================="

if [ "$MODE" = "live" ]; then
    echo ""
    echo "  ⚠️  实盘模式 (IBKR Live)"
    echo ""
    echo "  风控参数:"
    echo "    单票仓位: 1%"
    echo "    日亏损上限: 0.5%"
    echo "    周亏损上限: 2%"
    echo "    最多持仓: 2 只"
    echo "    连亏暂停: 2 笔"
    echo ""
    echo "  IBKR: 127.0.0.1:7496 (Live)"
    echo ""
    read -p "  确认启动实盘交易? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "  已取消。"
        exit 0
    fi
    echo ""
    echo "  启动实盘交易系统..."
    export $(cat .env.live | grep -v '^#' | xargs)
else
    echo ""
    echo "  📊 Paper Trading 模式"
    echo ""
    echo "  IBKR: 127.0.0.1:7497 (Paper)"
    echo ""
    echo "  启动模拟交易系统..."
    export $(cat .env | grep -v '^#' | xargs)
fi

export PYTHONPATH="$(pwd)"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --loop asyncio
