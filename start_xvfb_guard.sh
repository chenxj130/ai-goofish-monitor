#!/bin/bash
# === Xvfb 保活启动脚本 ===
# 根因：Xvfb 是一次性后台进程，运行中崩溃后无人重启
#       → Playwright TargetClosedError → 反复"启动任务失败"
# 方案：后台每 10 秒检测 Xvfb socket，崩溃则自动重启

set -e

# 1) 首次启动 Xvfb
rm -f /tmp/.X11-unix/X99
Xvfb :99 -ac -screen 0 1280x1024x24 >/dev/null 2>&1 &
sleep 2

# 2) 注入 DISPLAY 环境变量（主进程及所有子进程继承）
export DISPLAY=:99

# 3) Xvfb 保活守护（后台循环）
(
  while true; do
    if [ ! -S /tmp/.X11-unix/X99 ]; then
      echo "[xvfb-guard] $(date '+%Y-%m-%d %H:%M:%S'): Xvfb socket lost, restarting..." >&2
      rm -f /tmp/.X11-unix/X99
      Xvfb :99 -ac -screen 0 1280x1024x24 >/dev/null 2>&1 &
      sleep 2
      export DISPLAY=:99
    fi
    sleep 10
  done
) &

echo "[start.sh] Xvfb :99 started, DISPLAY=:99, guard PID=$!" >&2
echo "[start.sh] Starting ai-goofish-monitor..." >&2

# 4) 启动主应用（exec 替换当前进程）
exec python -m src.app
