@echo off
REM Check formatting and linting only (no auto-fix)

REM Python
black --check .
isort --check-only .
flake8 .
djlint templates/ --check --profile=jinja

REM Static assets
npm run check
