failures=0
trap 'failures=$((failures+1))' ERR
isort . --check-only
black . --check
flake8 . --exclude .idea
if ((failures > 0)); then
  exit 1
fi
