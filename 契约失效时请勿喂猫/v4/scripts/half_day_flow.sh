#!/usr/bin/env bash
# 半天检查点流程 (ticket 25/24): 跑到里程碑边界 -> 存档检查点 -> 过检查器
# -> 过=续跑; 不过=调种子从上一个好检查点重跑。
set -uo pipefail
cd "$(dirname "$0")/.."
export OPENAI_BASE_URL=http://localhost:4000/v1
# 故事模型线路（用户 2026-09-30 裁定：只用 litellm 提供的 zai/ 线路，不用 volcengine）。
# 中途经历：zai-coding/glm-5.3-flash 曾可用，代理重启后该组消失；zai/glm-5.3-flash 已可用
# （余额已恢复），原生工具调用与 inner 字段均实测正常。Copilot 配额恢复后可切回
# github_copilot/gpt-6-luna（需 V3_PROVIDER_API=responses）。
export OPENAI_MODEL=zai/glm-5.3-flash
export V3_PROVIDER_API=chat
export OPENAI_API_KEY="${LITELLM_API_KEY:?set LITELLM_API_KEY to the litellm master key}"
export V3_PROVIDER_TIMEOUT=120 V3_PROVIDER_RETRIES=4
export V3_PROVIDER_MAX_RETRIES=4 V3_PROVIDER_MAX_DURATION=420
export V3_PROVIDER_CONCURRENCY=8
# 地平线设计下，等待最慢的思考者是常态而非停摆（ticket 53）：stall 现在量的是
# “连续无进展”的墙钟秒数，不再累积每一次冻结；等待容忍由 freeze/hung 两个有界上限管住。
# 真卡死会在分钟内被判定并写进 trace（在飞角色/已等时长/最近进展/命中阈值）。
export V4_STALL_SECONDS=300
export V4_FREEZE_TOLERANCE_SECONDS=120
export V4_HUNG_TIMEOUT_SECONDS=60
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
