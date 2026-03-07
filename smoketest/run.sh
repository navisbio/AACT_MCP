#!/usr/bin/env bash
set -euo pipefail

# ── Smoketest for aact-mcp plugin ────────────────────────────────────────
# Each test runs three messages in the same conversation:
#   1. The task prompt — executed end-to-end
#   2. A hallucination check — verifies entities/counts from the response
#   3. A follow-up asking what should be improved about the MCP and tooling
#
# Usage:
#   ./smoketest/run.sh              # run all tests
#   ./smoketest/run.sh basic-query  # run a single test
# ─────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PLUGIN_DIR/.env"
OUTPUT_DIR="$SCRIPT_DIR/results/$(date +%Y%m%d_%H%M%S)"
SINGLE_TEST="${1:-}"

FOLLOWUP_PROMPT="Now reflect on the task you just completed. Based on your experience using the MCP tools and skills in this session:

1. What worked well? Which tools and workflows were effective?
2. What failed or underperformed? (e.g. SQL queries that returned errors or unexpected results, tools that didn't return useful data, workflow steps that were inefficient)
3. What information was missing or hard to find? Were there gaps in tool coverage?
4. What specific improvements would you suggest for the MCP tools, tool descriptions, or skill workflows?
5. Were there any tool calls you wanted to make but couldn't, or parameters you wished existed?

Be concrete and specific — reference actual tool calls, error messages, and query strings from this session. This feedback will be used to improve the plugin."

HALLUCINATION_CHECK_PROMPT="I want you to check for each of the NCT IDs, drug names, sponsor names, and statistics you mentioned if they really exist in the database or if you hallucinated them. For each one, verify by querying the AACT database again. Report a table with: entity name, claimed value, verified value, and whether the verification passed or failed."

ALLOWED_TOOLS="mcp__plugin_aact_aact__list_tables,mcp__plugin_aact_aact__describe_table,mcp__plugin_aact_aact__get_column_values,mcp__plugin_aact_aact__read_query,mcp__plugin_aact_aact__fetch_rows,Read,Write,Edit,Grep,Glob,Bash,Skill,Agent"

# ── Load credentials ────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Create it with DB_USER and DB_PASSWORD."
  exit 1
fi
set -a
source "$ENV_FILE"
set +a

if [[ -z "${DB_USER:-}" || -z "${DB_PASSWORD:-}" ]]; then
  echo "ERROR: DB_USER and DB_PASSWORD must be set in $ENV_FILE"
  exit 1
fi

# ── Verify Claude Code is available ─────────────────────────────────────
if ! command -v claude &>/dev/null; then
  echo "ERROR: claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
  exit 1
fi

# ── Prepare output directory ────────────────────────────────────────────
mkdir -p "$OUTPUT_DIR"
echo "Output directory: $OUTPUT_DIR"

# ── Helper: extract text result from stream-json ────────────────────────
extract_text() {
  local stream_file="$1"
  local text_file="$2"
  local json_file="$3"

  grep '"type":"result"' "$stream_file" | tail -1 > "$json_file" 2>/dev/null || true
  python3 -c "
import sys, json
for line in open('$json_file'):
    try:
        obj = json.loads(line)
        if obj.get('type') == 'result':
            print(obj.get('result', '(no result)'))
    except: pass
" > "$text_file" 2>/dev/null || true
}

# ── Define test cases ───────────────────────────────────────────────────
# Each test: name|max_turns|max_budget|prompt
# Use 0 for max_turns or max_budget to leave them unlimited
TESTS=(
  "explore-schema|6|2.00|Explore the AACT database schema. List all tables, then describe the 'studies', 'conditions', and 'interventions' tables. Summarize the key columns and how these tables relate to each other via nct_id."
  "trial-search|8|3.00|Find all Phase 3 clinical trials for pembrolizumab (Keytruda) in non-small cell lung cancer. Show the NCT ID, title, phase, status, enrollment, and lead sponsor for each. Sort by enrollment descending."
  "sponsor-landscape|10|4.00|Analyze the competitive landscape of clinical trials in Alzheimer's disease. Find the top 10 sponsors by number of trials, break down by phase, and identify which sponsors have the most Phase 3 trials. Show the data in a structured summary."
  "endpoint-deep-dive|12|5.00|Investigate the primary endpoints used in completed Phase 3 trials for type 2 diabetes. What are the most common primary outcome measures? How do they differ across the top 5 sponsors? Are there trends in endpoint selection? Produce a detailed analysis."
  "recruitment-pipeline|10|4.00|Build a pipeline view of actively recruiting oncology trials. Query for trials with overall_status='Recruiting' and conditions matching cancer/tumor/carcinoma/lymphoma. Group by phase and show the top 10 conditions by trial count. Include total enrollment across all matching trials."
  "trial-design-analysis|12|5.00|Compare the study designs of COVID-19 vaccine trials. Find trials where interventions mention 'vaccine' and conditions mention 'COVID' or 'SARS-CoV-2'. Analyze the distribution of study types, masking, allocation methods, and enrollment sizes. Which companies ran the largest trials?"
  "geographic-analysis|10|4.00|Analyze where clinical trials for rare diseases are conducted. Find trials where conditions match 'orphan' or specific rare diseases like 'cystic fibrosis' or 'Huntington'. Query the facilities table to identify the top countries and institutions. How many sites does a typical rare disease trial have?"
)

# ── Run tests ───────────────────────────────────────────────────────────
PASS=0
FAIL=0
TOTAL=0

for test_entry in "${TESTS[@]}"; do
  IFS='|' read -r name max_turns max_budget prompt <<< "$test_entry"

  # Skip if single test requested and doesn't match
  if [[ -n "$SINGLE_TEST" && "$name" != "$SINGLE_TEST" ]]; then
    continue
  fi
  TOTAL=$((TOTAL + 1))

  # Build optional flags for the task message
  LIMIT_FLAGS=()
  if [[ "$max_turns" != "0" ]]; then
    LIMIT_FLAGS+=(--max-turns "$max_turns")
  fi
  if [[ "$max_budget" != "0" ]]; then
    LIMIT_FLAGS+=(--max-budget-usd "$max_budget")
  fi

  # Generate a unique session ID for this test
  SESSION_ID=$(python3 -c "import uuid; print(uuid.uuid4())")

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "TEST: $name (max_turns=${max_turns:-unlimited}, budget=${max_budget:-unlimited})"
  echo "  Session: $SESSION_ID"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  # ── Message 1: Run the task ──────────────────────────────────────────
  task_stream="$OUTPUT_DIR/${name}.task.stream.jsonl"
  task_text="$OUTPUT_DIR/${name}.task.txt"
  task_json="$OUTPUT_DIR/${name}.task.json"

  echo "  [1/3] Running task..."

  if CLAUDECODE= claude -p "$prompt" \
    --plugin-dir "$PLUGIN_DIR" \
    --allowedTools "$ALLOWED_TOOLS" \
    --output-format stream-json \
    --session-id "$SESSION_ID" \
    "${LIMIT_FLAGS[@]}" \
    --verbose \
    > "$task_stream" 2>&1; then

    extract_text "$task_stream" "$task_text" "$task_json"

    # Check if MCP tools were actually used (match plugin prefix or bare tool names)
    mcp_calls=$(grep -c -E 'mcp__plugin_aact|"(list_tables|describe_table|get_column_values|read_query|fetch_rows)"' "$task_stream" 2>/dev/null | tail -1 || echo "0")

    if [[ "$mcp_calls" -gt 0 ]]; then
      echo "  PASS - $mcp_calls MCP tool calls made"
      echo "  Preview: $(head -c 300 "$task_text" 2>/dev/null)..."
      PASS=$((PASS + 1))
    else
      echo "  FAIL - No MCP tool calls detected (server likely not connected)"
      grep '"type":"system"' "$task_stream" | head -1 | python3 -c "
import sys, json
for line in sys.stdin:
    obj = json.loads(line)
    for s in obj.get('mcp_servers', []):
        if 'aact' in s.get('name',''):
            print(f\"    MCP: {s['name']} -> {s['status']}\")
" 2>/dev/null || true
      FAIL=$((FAIL + 1))
      continue  # skip follow-up if task failed
    fi
  else
    echo "  FAIL - Claude exited with error"
    FAIL=$((FAIL + 1))
    continue  # skip follow-up if task failed
  fi

  # ── Message 2: Hallucination check ─────────────────────────────────
  hallu_stream="$OUTPUT_DIR/${name}.hallucination.stream.jsonl"
  hallu_text="$OUTPUT_DIR/${name}.hallucination.txt"
  hallu_json="$OUTPUT_DIR/${name}.hallucination.json"

  echo "  [2/3] Running hallucination check..."

  if CLAUDECODE= claude -p "$HALLUCINATION_CHECK_PROMPT" \
    --resume "$SESSION_ID" \
    --plugin-dir "$PLUGIN_DIR" \
    --allowedTools "$ALLOWED_TOOLS" \
    --output-format stream-json \
    --verbose \
    > "$hallu_stream" 2>&1; then

    extract_text "$hallu_stream" "$hallu_text" "$hallu_json"
    echo "  Hallucination check collected ($(wc -c < "$hallu_text" | tr -d ' ') bytes)"
  else
    echo "  WARN - Hallucination check failed (task result still valid)"
  fi

  # ── Message 3: Ask for feedback ──────────────────────────────────────
  feedback_stream="$OUTPUT_DIR/${name}.feedback.stream.jsonl"
  feedback_text="$OUTPUT_DIR/${name}.feedback.txt"
  feedback_json="$OUTPUT_DIR/${name}.feedback.json"

  echo "  [3/3] Collecting feedback..."

  if CLAUDECODE= claude -p "$FOLLOWUP_PROMPT" \
    --resume "$SESSION_ID" \
    --output-format stream-json \
    --max-turns 1 \
    --verbose \
    > "$feedback_stream" 2>&1; then

    extract_text "$feedback_stream" "$feedback_text" "$feedback_json"
    echo "  Feedback collected ($(wc -c < "$feedback_text" | tr -d ' ') bytes)"
  else
    echo "  WARN - Feedback collection failed (task result still valid)"
  fi
done

# ── Summary ─────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RESULTS: $PASS/$TOTAL passed, $FAIL failed"
echo "Output: $OUTPUT_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Files per test:"
echo "  *.task.txt          — task output"
echo "  *.hallucination.txt — entity/count verification results"
echo "  *.feedback.txt      — MCP/tooling improvement suggestions"
echo ""
ls -lh "$OUTPUT_DIR"/*.task.json 2>/dev/null || echo "(no results)"
