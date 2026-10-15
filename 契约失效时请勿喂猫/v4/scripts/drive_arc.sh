#!/usr/bin/env bash
# 无人值守推进器（2026-10-02）：按半天分段推进整个 12 日弧线。
# 每段：跑到里程碑边界 -> 若因墙钟/上游中断则从最新检查点自动续跑（最多 MAX_RESUMES 次）
#       -> 存档检查点 -> 过该半天的锚点门；门不过就停（不带病续跑）。
# 日志：logs/drive.log（追加），每段门禁结果：logs/gate-<name>.txt
set -uo pipefail
cd "$(dirname "$0")/.."

export OPENAI_BASE_URL=http://localhost:4000/v1
export OPENAI_MODEL=${OPENAI_MODEL:-github_copilot/gpt-6-luna}
export V3_PROVIDER_API=${V3_PROVIDER_API:-responses}
export OPENAI_API_KEY="${LITELLM_API_KEY:?set LITELLM_API_KEY}"
export V3_PROVIDER_TIMEOUT=120 V3_PROVIDER_RETRIES=4
export V3_PROVIDER_MAX_RETRIES=4 V3_PROVIDER_MAX_DURATION=420
export V3_PROVIDER_CONCURRENCY=8
export V4_STALL_SECONDS=300 V4_FREEZE_TOLERANCE_SECONDS=120 V4_HUNG_TIMEOUT_SECONDS=60
export V3_MAX_WALL_SECONDS=${V3_MAX_WALL_SECONDS:-10800}

mkdir -p checkpoints logs
LOG=logs/drive.log
MAX_RESUMES=${MAX_RESUMES:-3}
LOG_ONLY=${LOG_ONLY:-0}

say() { echo "[$(date +%m-%d\ %H:%M:%S)] $*" >> "$LOG"; }

newest_checkpoint() { ls -t runs/*.checkpoint.json 2>/dev/null | head -1; }
newest_artifact()   { ls -t runs/real-*.json runs/resumed-*.json 2>/dev/null | grep -v checkpoint | head -1; }

# 上游配额/连通性失败计数：连续 3 段都因 provider 失败而放弃则整体停下
provider_fail_streak=0

run_segment() {   # $1=name $2=stop-iso $3=resume-checkpoint(可空)
  local name=$1 stop=$2 resume=$3
  say "==== [$name] stop=$stop resume=${resume:-<fresh>} ===="
  local attempt=0 rc artifact ckpt
  while :; do
    export V3_CLOCK_STOP="$stop"
    if [ -n "$resume" ]; then export V3_RESUME_CHECKPOINT="$resume"; else unset V3_RESUME_CHECKPOINT; fi
    python3 -m harness.real_run >> "$LOG" 2>&1
    rc=$?
    artifact=$(newest_artifact)
    if [ $rc -eq 0 ]; then
      say "  [$name] reached endpoint (rc=0) artifact=$artifact"
      break
    fi
    attempt=$((attempt+1))
    local reason
    reason=$(grep -h "engine] stop: \|RuntimeError: real experiment" "$LOG" | tail -1)
    say "  [$name] attempt $attempt rc=$rc | $reason"
    if [ $attempt -ge $MAX_RESUMES ]; then
      say "  [$name] ABORT after $MAX_RESUMES attempts"
      case "$reason" in
        *429*|*provider*|*429*|*quota*) provider_fail_streak=$((provider_fail_streak+1)) ;;
      esac
      return 9
    fi
    resume=$(newest_checkpoint)
    if [ -z "$resume" ]; then say "  [$name] no checkpoint to resume from"; return 9; fi
    say "  [$name] resuming from $resume"
  done

  ckpt=$(newest_checkpoint)
  [ -n "$ckpt" ] && cp "$ckpt" "checkpoints/$name.json"
  python3 scripts/check_milestones.py "$artifact" --half "$name" > "logs/gate-$name.txt" 2>&1
  local grc=$?
  say "  [$name] gate rc=$grc : $(grep -E '结果' "logs/gate-$name.txt" | tail -1)"
  if [ $grc -ne 0 ]; then
    say "  [$name] GATE FAIL — 停在这里，不带病续跑"
    return 3
  fi
  say "  [$name] OK -> checkpoints/$name.json (artifact=$artifact)"
  LAST_ARTIFACT="$artifact"
  LAST_CKPT="checkpoints/$name.json"
  provider_fail_streak=0
  return 0
}

# --- 弧线：第 1 天下午起，直到第 12 天 21:30 world_stops -------------------------
# 首段从"已在跑的 d1-pm 半成品检查点"续，避免重算已完成的 7 小时。
FIRST_PM_RESUME=${FIRST_PM_RESUME:-}

segments=(
  "d1-pm|2026-03-16T22:00:00+08:00"
)
for d in 2 3 4 5 6 7 8 9 10 11 12; do
  day=$(printf '%02d' $d)
  case $d in
    2) date=2026-03-17 ;; 3) date=2026-03-18 ;; 4) date=2026-03-19 ;;
    5) date=2026-03-20 ;; 6) date=2026-03-21 ;; 7) date=2026-03-22 ;;
    8) date=2026-03-23 ;; 9) date=2026-03-24 ;; 10) date=2026-03-25 ;;
    11) date=2026-03-26 ;; 12) date=2026-03-27 ;;
  esac
  segments+=("d${d}-am|${date}T12:59:00+08:00")
  segments+=("d${d}-pm|${date}T22:00:00+08:00")
done

resume="$FIRST_PM_RESUME"
say "===== driver start: model=$OPENAI_MODEL max_wall=$V3_MAX_WALL_SECONDS max_resumes=$MAX_RESUMES ====="
for seg in "${segments[@]}"; do
  name="${seg%%|*}"; rest="${seg#*|}"; stop="${rest%%|*}"
  run_segment "$name" "$stop" "$resume"
  rc=$?
  if [ $rc -ne 0 ]; then
    if [ "$name" = "d1-pm" ] && [ -n "$FIRST_PM_RESUME" ]; then
      # 半成品检查点可能属于旧代码；重跑该段（从 d1-am 存档开始）一次
      say "  [$name] retry from the archived d1-am checkpoint"
      run_segment "$name" "$stop" "checkpoints/d1-am.json"
      rc=$?
    fi
    [ $rc -ne 0 ] && { say "===== driver STOP at $name (rc=$rc, provider_fail_streak=$provider_fail_streak) ====="; exit $rc; }
  fi
  if [ $provider_fail_streak -ge 3 ]; then
    say "===== driver STOP: 3+ consecutive provider failures (likely quota) ====="; exit 7
  fi
  resume="$LAST_CKPT"
done
say "===== driver finished the 12-day arc ====="
