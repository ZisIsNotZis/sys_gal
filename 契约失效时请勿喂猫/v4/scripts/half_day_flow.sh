#!/usr/bin/env bash
# 半天检查点流程 (ticket 25/24): 跑到里程碑边界 -> 存档检查点 -> 过检查器
# -> 过=续跑; 不过=调种子从上一个好检查点重跑。
set -uo pipefail
cd "$(dirname "$0")/.."
export OPENAI_BASE_URL=http://localhost:4000/v1
export OPENAI_MODEL=github_copilot/gpt-6-luna
export OPENAI_API_KEY=sk-noauth
export V3_PROVIDER_TIMEOUT=120 V3_PROVIDER_RETRIES=4
export V3_PROVIDER_MAX_RETRIES=4 V3_PROVIDER_MAX_DURATION=420
export V3_PROVIDER_CONCURRENCY=8
# 地平线设计下，等待最慢的思考者是常态而非停摆：stall 预算放宽到 60%。
# 真死锁由 provider 单调用上限 (V3_PROVIDER_MAX_DURATION) 与总墙钟兜底。
export V4_STALL_BUDGET_RATIO=0.60
mkdir -p checkpoints

segment() {
  local name=$1 stop=$2 resume=$3
  echo "════ [$name] stop=$stop resume=${resume:-<fresh>} ════"
  if [ -n "$resume" ]; then
    export V3_RESUME_CHECKPOINT="checkpoints/$resume"
  else
    unset V3_RESUME_CHECKPOINT || true
  fi
  export V3_CLOCK_STOP=$stop
  python3 -m harness.real_run > "runs/seg-$name.log" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then
    echo "[$name] real_run FAILED (rc=$rc) — 流程停止，从上一个好检查点重跑"
    tail -5 "runs/seg-$name.log"
    exit $rc
  fi
  local ckpt
  ckpt=$(ls -t runs/*.checkpoint.json 2>/dev/null | head -1)
  if [ -n "$ckpt" ]; then cp "$ckpt" "checkpoints/$name.json"; fi
  local artifact
  artifact=$(ls -t runs/real-*.json 2>/dev/null | grep -v checkpoint | head -1)
  echo "[$name] checkpoint -> checkpoints/$name.json ; artifact -> $artifact"
  if [ -n "$artifact" ]; then
    # 检查器 FAIL = 里程碑未达成：必须停下调种子，不得带病续跑。
    if ! python3 scripts/check_milestones.py "$artifact" --half "$name"; then
      echo "[$name] 检查器 FAIL —— 调种子后从上一个好检查点重跑"
      exit 3
    fi
  fi
}

segment d1-am "2026-03-16T12:59:00+08:00" ""
segment d1-pm "2026-03-16T22:00:00+08:00" "d1-am.json"
segment d2-am "2026-03-17T12:59:00+08:00" "d1-pm.json"
segment d2-pm "2026-03-17T22:00:00+08:00" "d2-am.json"
echo "════ 全部半天段完成 ════"
