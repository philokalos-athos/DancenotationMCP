#!/usr/bin/env bash
set -euo pipefail

if rg -n "^(<<<<<<<|=======|>>>>>>>)" -S . >/tmp/conflicts.out 2>/dev/null; then
  echo "Conflict markers found:"
  cat /tmp/conflicts.out
  exit 1
fi

echo "No conflict markers found in working tree."
