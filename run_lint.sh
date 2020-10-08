set -e
flake8 . --count --select=E9,F63,F7,F82 --show-source
flake8 . --count --max-complexity=10 --max-line-length=120 --exclude .idea
