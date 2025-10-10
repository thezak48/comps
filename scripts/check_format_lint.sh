#!/bin/bash
# Check formatting and linting for Python, Jinja, JS, and CSS (no auto-fix)

echo
echo "============================="
echo "  Checking Python files"
echo "============================="
black --check .
isort --check-only .
flake8 .

echo
echo "============================="
echo "  Checking Jinja templates"
echo "============================="
djlint templates/ --check --profile=jinja

# Static assets: JS, CSS (lint and formatting check)
echo
echo "============================="
echo "  Checking CSS files"
echo "============================="
npm run lint:css

echo
echo "============================="
echo "  Checking JS files"
echo "============================="
npm run lint:js

echo
echo "============================="
echo "  Checking Prettier formatting"
echo "============================="
npm run prettier:check
