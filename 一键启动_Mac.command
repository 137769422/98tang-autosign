#!/bin/bash

# ===================================================
#     98堂论坛自动签到系统 - 一键启动程序 (macOS)
# ===================================================

cd "$(dirname "$0")"

echo "==================================================="
echo "🤖 98tang-autosign - 正在检查运行环境..."
echo "==================================================="

# 检查虚拟环境，若不存在则自动初始化
if [ ! -f "./.venv/bin/python" ]; then
    if command -v python3 &> /dev/null; then
        echo "📦 正在自动创建独立运行环境 (.venv)..."
        python3 -m venv .venv
        echo "📥 正在安装依赖包（仅首次需要）..."
        ./.venv/bin/python -m pip install --upgrade pip
        ./.venv/bin/python -m pip install -r requirements.txt
    else
        echo "❌ 未检测到 Python3，请先安装 Python 3 环境"
        read -n 1 -s -r -p "按任意键退出..."
        echo ""
        exit 1
    fi
fi

echo "✅ 已就绪独立虚拟环境 (.venv)"
echo "---------------------------------------------------"
echo "🚀 正在启动 98tang 自动签到系统..."
echo "---------------------------------------------------"
./.venv/bin/python main.py "$@"
exit_code=$?
echo "---------------------------------------------------"
echo "执行完毕，返回状态码: $exit_code"
read -n 1 -s -r -p "按任意键退出窗口..."
echo ""
exit $exit_code
