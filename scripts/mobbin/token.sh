#!/usr/bin/env bash
# Prints `Bearer <token>` for the Mobbin MCP `Authorization` header (refreshes when expired).
# Referenced from .omp/mcp.json as `"Authorization": "!bash scripts/mobbin/token.sh"` — OMP only
# treats `!` as a command hook when it is the first character of the header value.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
token="$(node "$here/oauth.mjs" --token)"
printf 'Bearer %s' "$token"
