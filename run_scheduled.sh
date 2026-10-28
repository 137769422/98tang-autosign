#!/bin/bash

# ===================================================
#     98堂论坛定时签到运行脚本 (macOS)
# ===================================================

cd "$(dirname "$0")"

# 确保 logs 目录存在
mkdir -p logs

echo "===================================================" >> logs/scheduled.log
echo "⏰ 开始执行定时签到任务: $(date '+%Y-%m-%d %H:%M:%S')" >> logs/scheduled.log
echo "===================================================" >> logs/scheduled.log

if [ -f "./.venv/bin/python" ]; then
    ./.venv/bin/python main.py >> logs/scheduled.log 2>&1
    status=$?
else
    python3 main.py >> logs/scheduled.log 2>&1
    status=$?
fi

echo "🏁 定时签到任务结束，退出代码: $status，时间: $(date '+%Y-%m-%d %H:%M:%S')" >> logs/scheduled.log
echo "" >> logs/scheduled.log

exit $status
