#!/usr/bin/env bash
# Runs the same stages as the CI/CD pipeline on your own machine - handy for a live demo.
set -euo pipefail
cd "$(dirname "$0")/.."

banner() { printf '\n\033[1;36m==== %s ====\033[0m\n' "$1"; }

banner "STAGE 1/5  Lint"
if python3 -m flake8 --version >/dev/null 2>&1; then
  python3 -m flake8 app tests --max-line-length=120 && echo "lint clean"
else
  echo "flake8 not installed - falling back to syntax check"
  python3 -m compileall -q app tests && echo "syntax OK"
fi

banner "STAGE 2/5  Unit tests"
python3 -m unittest discover -s tests -v

if command -v docker >/dev/null 2>&1; then
  TAG="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
  banner "STAGE 3/5  Build Docker image (tag: $TAG)"
  docker build --build-arg APP_VERSION="$TAG" -t student-management:"$TAG" .

  banner "STAGE 4/5  Run container + smoke test"
  docker rm -f sms-pipeline >/dev/null 2>&1 || true
  docker run -d --name sms-pipeline -p 5055:5000 student-management:"$TAG" >/dev/null
  trap 'docker rm -f sms-pipeline >/dev/null 2>&1 || true' EXIT
  ./scripts/smoke_test.sh http://localhost:5055

  banner "STAGE 5/5  Done"
  echo "Image student-management:$TAG is ready to push / deploy."
else
  banner "Docker not found - running app directly for the smoke test"
  PORT=5055 SQLITE_PATH="$(mktemp -u).db" python3 -m app.app >/tmp/sms.log 2>&1 &
  PID=$!
  trap 'kill $PID 2>/dev/null || true' EXIT
  ./scripts/smoke_test.sh http://localhost:5055
fi

banner "PIPELINE PASSED"
