#!/bin/bash
# Warn if code changes are staged without documentation/status updates
CODE_CHANGED=$(git diff --cached --name-only | grep -E 'src/|\.py')
DOC_CHANGED=$(git diff --cached --name-only | grep -E 'README.md|BACKLOG.md|CURRENT_STATUS.md|\.DME-SYNC_DEV_RULES.md|CONTRIBUTING.md')
if [[ -n "$CODE_CHANGED" && -z "$DOC_CHANGED" ]]; then
  echo "WARNING: Code changes staged without documentation/status updates. Please update relevant docs, BACKLOG.md, and CURRENT_STATUS.md."
  exit 1
fi 