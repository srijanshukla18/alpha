#!/usr/bin/env bash
set -euo pipefail

DIR="${1:-agentcore_deploy}"

echo "🔧 Bootstrapping AgentCore Starter Toolkit project in: $DIR"
mkdir -p "$DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "❌ 'uv' not found. Install from https://astral.sh/uv/ (e.g., curl -LsSf https://astral.sh/uv/install.sh | sh)"
  exit 1
fi

# Initialize a standalone project regardless of parent workspace
(cd "$DIR" && uv init --no-workspace >/dev/null)
uv --directory "$DIR" add bedrock-agentcore-starter-toolkit >/dev/null

cat <<EOF

✅ AgentCore project ready in $DIR

Next steps (run these):

  uv --directory $DIR run agentcore configure -e ../src/alpha_agent/agentcore_entrypoint.py
  uv --directory $DIR run agentcore launch
  uv --directory $DIR run agentcore status

To invoke actions:

  uv --directory $DIR run agentcore invoke '{"action":"enforce_policy_guardrails","policy":{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:*","Resource":"*"}]},"preset":"prod"}'
EOF
