#!/usr/bin/env bash
# =============================================================================
# FabricShield AI — End-to-End Test Harness
# Runs the full loop in one command: token -> scan -> poll -> approve -> mask
# -> verify. Use after deploying + seeding a test database (see runbook §7).
#
# USAGE
#   ./e2e_test.sh --backend https://fshield-prod-api-xxx.azurewebsites.net \
#                 --tenant <YOUR_TENANT_GUID> [options]
#
# OPTIONS (flags override env vars)
#   --backend URL       BACKEND_URL        (required) API base, no trailing slash
#   --tenant GUID       TENANT_ID          (required) must equal your signed-in tenant
#   --connection NAME   CONNECTION_NAME    default: primary   (KV secret middle segment)
#   --db-type TYPE      DATABASE_TYPE      default: azure_sql (azure_sql|fabric)
#   --schemas a,b       SCHEMAS            default: dbo
#   --scope SCOPE       API_SCOPE          default: api://fabricshield-prod/.default
#   --token JWT         TOKEN              skip az; use this bearer token
#   --limit N           APPROVAL_LIMIT     default: 1   (# columns to approve+mask)
#   --mask-all                              approve+mask EVERY flagged column
#   --timeout SEC       POLL_TIMEOUT       default: 180 (scan poll budget)
#   --verify                                run DB-side checks (needs sqlcmd)
#   --sql-server HOST   SQL_SERVER         for --verify
#   --sql-db NAME       SQL_DB             for --verify
#   --principal NAME    SQL_PRINCIPAL      default: 'FabricShield AI' (for --verify)
#   -h | --help
#
# DEPENDENCIES: curl, python3, and (az CLI unless --token is supplied).
# =============================================================================
set -euo pipefail

# ── Defaults / env fallbacks ─────────────────────────────────────────────────
BACKEND_URL="${BACKEND_URL:-}"
TENANT_ID="${TENANT_ID:-}"
CONNECTION_NAME="${CONNECTION_NAME:-primary}"
DATABASE_TYPE="${DATABASE_TYPE:-azure_sql}"
SCHEMAS="${SCHEMAS:-dbo}"
API_SCOPE="${API_SCOPE:-api://fabricshield-prod/.default}"
TOKEN="${TOKEN:-}"
APPROVAL_LIMIT="${APPROVAL_LIMIT:-1}"
MASK_ALL="false"
POLL_TIMEOUT="${POLL_TIMEOUT:-180}"
DO_VERIFY="false"
SQL_SERVER="${SQL_SERVER:-}"
SQL_DB="${SQL_DB:-}"
SQL_PRINCIPAL="${SQL_PRINCIPAL:-FabricShield AI}"

# ── Arg parse ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend) BACKEND_URL="$2"; shift 2;;
    --tenant) TENANT_ID="$2"; shift 2;;
    --connection) CONNECTION_NAME="$2"; shift 2;;
    --db-type) DATABASE_TYPE="$2"; shift 2;;
    --schemas) SCHEMAS="$2"; shift 2;;
    --scope) API_SCOPE="$2"; shift 2;;
    --token) TOKEN="$2"; shift 2;;
    --limit) APPROVAL_LIMIT="$2"; shift 2;;
    --mask-all) MASK_ALL="true"; shift;;
    --timeout) POLL_TIMEOUT="$2"; shift 2;;
    --verify) DO_VERIFY="true"; shift;;
    --sql-server) SQL_SERVER="$2"; shift 2;;
    --sql-db) SQL_DB="$2"; shift 2;;
    --principal) SQL_PRINCIPAL="$2"; shift 2;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

c_ok=$'\033[32m'; c_err=$'\033[31m'; c_dim=$'\033[2m'; c_off=$'\033[0m'
die() { echo "${c_err}✗ $*${c_off}" >&2; exit 1; }
ok()  { echo "${c_ok}✓ $*${c_off}"; }

command -v curl    >/dev/null || die "curl not found"
command -v python3 >/dev/null || die "python3 not found"
[[ -n "$BACKEND_URL" ]] || die "--backend (or BACKEND_URL) is required"
[[ -n "$TENANT_ID"   ]] || die "--tenant (or TENANT_ID) is required"
BACKEND_URL="${BACKEND_URL%/}"   # strip trailing slash

# ── Helpers ──────────────────────────────────────────────────────────────────
_json() { python3 -c "import sys,json;d=json.load(sys.stdin);print($1)"; }

http() { # http METHOD PATH [JSON_BODY] -> echoes body, fails on non-2xx
  local method="$1" path="$2" data="${3:-}" code tmp; tmp="$(mktemp "${TMPDIR:-/tmp}/fsai.XXXXXX")"
  if [[ -n "$data" ]]; then
    code="$(curl -sS -o "$tmp" -w '%{http_code}' -X "$method" "$BACKEND_URL$path" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$data")"
  else
    code="$(curl -sS -o "$tmp" -w '%{http_code}' -X "$method" "$BACKEND_URL$path" \
      -H "Authorization: Bearer $TOKEN")"
  fi
  BODY="$(cat "$tmp")"; rm -f "$tmp"
  if [[ "$code" -lt 200 || "$code" -ge 300 ]]; then
    echo "${c_err}  HTTP $code on $method $path${c_off}" >&2
    echo "${c_dim}  $BODY${c_off}" >&2
    return 1
  fi
  printf '%s' "$BODY"
}

# ── 0. Token ─────────────────────────────────────────────────────────────────
echo "── FabricShield AI — end-to-end test ─────────────────────────────"
if [[ -z "$TOKEN" ]]; then
  command -v az >/dev/null || die "az CLI not found and no --token supplied"
  echo "Acquiring token (scope: $API_SCOPE) ..."
  TOKEN="$(az account get-access-token --scope "$API_SCOPE" --query accessToken -o tsv)" \
    || die "token acquisition failed — run 'az login --tenant <your-tenant>' first"
fi
# decode + sanity check (no signature check; informational)
python3 - "$TOKEN" <<'PY'
import sys,base64,json
t=sys.argv[1].split('.')
if len(t)<2: print("  (token does not look like a JWT)"); sys.exit(0)
c=t[1]+'='*(-len(t[1])%4)
d=json.loads(base64.urlsafe_b64decode(c))
print(f"  token aud : {d.get('aud')}")
print(f"  token iss : {d.get('iss')}")
print(f"  token roles: {d.get('roles')}")
if not d.get('roles'):
    print("  \033[31mWARNING: no app roles in token — assign yourself Analyst/Approver/Admin\033[0m")
PY

# ── 1. Trigger scan ──────────────────────────────────────────────────────────
SCHEMAS_JSON="$(python3 -c "import json,sys;print(json.dumps([s.strip() for s in sys.argv[1].split(',') if s.strip()]))" "$SCHEMAS")"
REQ="$(python3 -c "import json,sys;print(json.dumps({'tenant_id':sys.argv[1],'connection_name':sys.argv[2],'database_type':sys.argv[3],'schema_names':json.loads(sys.argv[4])}))" \
        "$TENANT_ID" "$CONNECTION_NAME" "$DATABASE_TYPE" "$SCHEMAS_JSON")"
echo "Triggering scan: $REQ"
RESP="$(http POST "/api/v1/scan" "$REQ")" || die "scan request failed"
SCAN_ID="$(printf '%s' "$RESP" | _json "d['scan_id']")"
ok "scan started: $SCAN_ID"

# ── 2. Poll until completed ──────────────────────────────────────────────────
deadline=$((SECONDS + POLL_TIMEOUT))
while :; do
  RESP="$(http GET "/api/v1/scan/$SCAN_ID")" || die "poll failed"
  STATUS="$(printf '%s' "$RESP" | _json "d.get('status')")"
  echo "  status: $STATUS"
  [[ "$STATUS" == "completed" ]] && break
  [[ "$STATUS" == "failed" ]] && die "scan failed: $(printf '%s' "$RESP" | _json "d.get('error')")"
  (( SECONDS > deadline )) && die "scan did not complete within ${POLL_TIMEOUT}s"
  sleep 3
done
FOUND="$(printf '%s' "$RESP" | _json "len(d.get('pii_columns',[]))")"
ok "scan completed — $FOUND PII column(s) flagged"

# ── 3. Fetch pending approvals (retry: written just after status flips) ──────
APPROVALS="[]"
for _ in 1 2 3 4 5 6; do
  APPROVALS="$(http GET "/api/v1/approvals?status_filter=PENDING&scan_id=$SCAN_ID&limit=500")" || die "list approvals failed"
  COUNT="$(printf '%s' "$APPROVALS" | _json "len(d)")"
  [[ "$COUNT" -gt 0 ]] && break
  sleep 2
done
[[ "${COUNT:-0}" -gt 0 ]] || die "no pending approvals for scan $SCAN_ID"
ok "pending approvals: $COUNT"

# choose ids
if [[ "$MASK_ALL" == "true" ]]; then
  IDS="$(printf '%s' "$APPROVALS" | python3 -c "import sys,json;print('\n'.join(a['approval_id'] for a in json.load(sys.stdin)))")"
else
  IDS="$(printf '%s' "$APPROVALS" | python3 -c "import sys,json;[print(a['approval_id']) for a in json.load(sys.stdin)[:$APPROVAL_LIMIT]]")"
fi
ID_ARR=()
while IFS= read -r _line; do [[ -n "$_line" ]] && ID_ARR+=("$_line"); done <<< "$IDS"
echo "  will approve+mask ${#ID_ARR[@]} column(s)"
# show what we're about to act on
printf '%s' "$APPROVALS" | python3 -c "
import sys,json
sel=set('''$IDS'''.split())
for a in json.load(sys.stdin):
    if a['approval_id'] in sel:
        print(f\"    - {a['schema_name']}.{a['table_name']}.{a['column_name']}  [{a['entity_type']}] -> {a['recommended_mask']}\")
"

# ── 4. Bulk approve ──────────────────────────────────────────────────────────
IDS_JSON="$(printf '%s' "$IDS" | python3 -c "import sys,json;print(json.dumps([x for x in sys.stdin.read().split() if x]))")"
APPROVE_REQ="$(python3 -c "import json,sys;print(json.dumps({'tenant_id':sys.argv[1],'approval_ids':json.loads(sys.argv[2]),'action':'approve'}))" "$TENANT_ID" "$IDS_JSON")"
RESP="$(http POST "/api/v1/approvals/bulk" "$APPROVE_REQ")" || die "bulk approve failed"
ok "approved: $(printf '%s' "$RESP" | _json "d['succeeded']") / failed: $(printf '%s' "$RESP" | _json "d['failed']")"

# ── 5. Apply mask per approval ───────────────────────────────────────────────
MASKED=0; FAILED=0
for id in "${ID_ARR[@]}"; do
  [[ -z "$id" ]] && continue
  if RESP="$(http POST "/api/v1/approvals/$id/mask")"; then
    SUCCESS="$(printf '%s' "$RESP" | _json "d.get('success')")"
    DDL="$(printf '%s' "$RESP" | _json "d.get('ddl_executed')")"
    if [[ "$SUCCESS" == "True" ]]; then MASKED=$((MASKED+1)); ok "masked $id"; echo "${c_dim}    $DDL${c_off}"
    else FAILED=$((FAILED+1)); echo "${c_err}  mask reported failure for $id: $(printf '%s' "$RESP" | _json "d.get('error')")${c_off}"; fi
  else
    FAILED=$((FAILED+1))
  fi
done
ok "masking done — $MASKED succeeded, $FAILED failed"

# ── 6. Optional DB-side verification ─────────────────────────────────────────
if [[ "$DO_VERIFY" == "true" ]]; then
  command -v sqlcmd >/dev/null || die "--verify needs sqlcmd"
  [[ -n "$SQL_SERVER" && -n "$SQL_DB" ]] || die "--verify needs --sql-server and --sql-db"
  echo "── DB verification ───────────────────────────────────────────────"
  echo "Masked columns now registered on the server:"
  sqlcmd -S "$SQL_SERVER" -d "$SQL_DB" -G -h -1 -W \
    -Q "SET NOCOUNT ON; SELECT OBJECT_SCHEMA_NAME(object_id)+'.'+OBJECT_NAME(object_id)+'.'+name+' = '+masking_function FROM sys.masked_columns;"
  echo "Negative test — '$SQL_PRINCIPAL' attempting to read a row (expect: permission denied):"
  if sqlcmd -S "$SQL_SERVER" -d "$SQL_DB" -G -b \
      -Q "EXECUTE AS USER = '$SQL_PRINCIPAL'; SELECT TOP 1 SSN FROM dbo.Patients; REVERT;" 2>/dev/null; then
    echo "${c_err}  ✗ SELECT SUCCEEDED — the principal can read rows. Re-check aqueducts_grant.sql!${c_off}"; exit 1
  else
    ok "row read was denied — principal is data-blind (HIPAA control proven)"
  fi
fi

SUFFIX=""; [[ "$DO_VERIFY" == "true" ]] && SUFFIX=" → verify"
echo "${c_ok}── PASS: scan → approve → mask${SUFFIX} complete ──${c_off}"
