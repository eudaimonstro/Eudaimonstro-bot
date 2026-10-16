#!/usr/bin/env bash
# Commit anything new under data/ and push. Each variant writes only to its own
# folder, so rebasing onto a concurrent push never conflicts.
set -euo pipefail
message="$1"
git config user.name "forecast-bot"
git config user.email "forecast-bot@users.noreply.github.com"
mkdir -p data
git add -A data
if git diff --cached --quiet; then
  echo "No new data to commit"
  exit 0
fi
git commit --quiet -m "$message"
for attempt in 1 2 3 4 5; do
  if git pull --rebase --autostash --quiet origin "${GITHUB_REF_NAME:-main}" && git push --quiet origin "HEAD:${GITHUB_REF_NAME:-main}"; then
    exit 0
  fi
  echo "Push attempt $attempt failed, retrying"
  git rebase --abort 2>/dev/null || true
  sleep $((attempt * 5))
done
echo "Could not push data after 5 attempts" >&2
exit 1
