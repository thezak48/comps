#!/bin/bash
# Check formatting and linting only (no auto-fix)

# Python
black --check .
isort --check-only .
flake8 .
djlint templates/ --check --profile=jinja

# Static assets
npm run check
