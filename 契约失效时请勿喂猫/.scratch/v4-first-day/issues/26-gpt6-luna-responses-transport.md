# 26 — GPT-6 Luna native Responses tool transport

Status: done

## Issue

`github_copilot/gpt-6-luna` is configured for LiteLLM's Responses protocol only. The v4 provider sends native tools through `/chat/completions`, and the response-history shape persisted by `V4Session` is not a valid Responses input.

## Objective and acceptance

- Keep the existing chat-completions path unchanged for other models.
- For `github_copilot/gpt-6-luna`, convert chat-style session messages and function tools to native Responses input and normalize message/function-call output back to the v4 chat-style session shape.
- Preserve assistant text alongside one or more tool calls, and preserve matching call IDs for tool results.
- Route compaction through Responses without an unsupported thinking override.
- Add focused conversion/transport regression tests, update `V4-AGENT-INTERFACE.md` and `V4-DESIGN.md`, run the v4 suite and seed lint, and perform one bounded provider request if the local proxy is ready.
- Replace the memorial ceremony notice's leak-prone `代签通知书` wording with neutral `通知书原件` and guard that wording in the seed regression test; proxy-signing truth remains available only through in-person world action.
- Commit only scoped files with the configured pi identity; preserve all pre-existing work.

## Blockers

None known. Proxy readiness and `LITELLM_API_KEY` will be checked without printing credentials.

Need-review: yes
Need-test-cases: yes

## Comments

- 2026-09-28, pi: Claimed implementation. Legacy chat path and unrelated working-tree files will remain untouched.
- 2026-09-28, pi: Parent steering added a narrow seed privacy correction: neutralize the scheduled ceremony notice and add a regression assertion; transport remains the primary scope.
- 2026-09-28, pi: Implemented in ec75ac9. Fresh reviewer found P1: legacy multi-call result coalescing loses later calls' arguments/results in Responses history. Fixed only Responses path in bdb637f; real proxy accepted two same-name function calls and two consecutive outputs, returning the expected sum 5. Full v4 suite 323 OK (1 skipped), seed lint OK, diff check OK.
- 2026-09-28, pi: Fresh re-review (gpt-6-luna reviewer) verdict OK with nonblocking P2: no single threshold-triggered multi-call compaction regression. Source confirms compaction converts intact pairs. First provider story segment launched only after v3 218 green, v4 323 green, lint green, deterministic seed endpoint and provider two-turn smoke. Next: analyze each character's segment trajectory before continuation.
