#!/bin/bash
GROOT_VENV=/home/ubuntu/Isaac-GR00T/.venv/bin/python3
SERVER_SCRIPT=/home/ubuntu/roboticsai/src/inference/groot_franka_server.py
CKPT_BASE=/tmp/dagger_run9/checkpoints
LOG=/tmp/run9_server_monitor.log
PORT=8001

echo "[$(date)] Monitor v2 started" >> $LOG

get_latest() {
  local LI=$(ls -d ${CKPT_BASE}/iter_* 2>/dev/null | sort -V | tail -1)
  [ -z "$LI" ] && return
  local LC=$(ls -d ${LI}/checkpoint-* 2>/dev/null | sort -t- -k2 -n | tail -1)
  echo ${LC:-$LI}
}

do_restart() {
  local CKPT=$1
  echo "[$(date)] Restarting with $CKPT" >> $LOG
  pkill -f groot_franka_server 2>/dev/null; sleep 3
  cd /home/ubuntu/Isaac-GR00T
  CUDA_VISIBLE_DEVICES=3 nohup $GROOT_VENV $SERVER_SCRIPT --checkpoint "$CKPT" --port $PORT --device 0 > /tmp/groot_server.log 2>&1 &
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    sleep 5
    if curl -sf http://localhost:${PORT}/health >/dev/null 2>&1; then
      echo "[$(date)] Ready after $((i*5))s with $CKPT" >> $LOG
      return 0
    fi
  done
  echo "[$(date)] FAILED to start" >> $LOG
  return 1
}

while true; do
  sleep 10
  CUR=$(curl -sf http://localhost:${PORT}/health 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('checkpoint',''))" 2>/dev/null)
  LAT=$(get_latest)
  [ -z "$LAT" ] && continue
  if [ -z "$CUR" ]; then
    echo "[$(date)] Server down" >> $LOG
    do_restart "$LAT"
    continue
  fi
  if [ "$CUR" != "$LAT" ]; then
    LN=$(echo "$LAT" | grep -o 'checkpoint-[0-9]*' | grep -o '[0-9]*')
    CI=$(echo "$CUR" | grep -o 'iter_[0-9]*' | grep -o '[0-9]*')
    LI=$(echo "$LAT" | grep -o 'iter_[0-9]*' | grep -o '[0-9]*')
    if [ -n "$LI" ] && [ -n "$CI" ] && [ "$LI" -gt "$CI" ] && [ "$LN" = "7000" ]; then
      echo "[$(date)] Auto-upgrade iter_${CI} -> iter_${LI}" >> $LOG
      do_restart "$LAT"
    fi
  fi
done
