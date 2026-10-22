#!/bin/bash
# Format all code: Python, Jinja, JS, CSS

# Python
echo
echo "============================="
echo "  Formatting Python files"
echo "============================="
black .
isort .
flake8 .

echo
echo "============================="
echo "  Formatting HTML/Jinja templates"
echo "============================="
djlint templates/ --reformat --profile=jinja --extension=jinja
djlint templates/ --reformat --profile=jinja --extension=html

echo
echo "============================="
echo "  Formatting CSS files"
echo "============================="
npm run format:css

echo
echo "============================="
echo "  Formatting JS files"
echo "============================="
npm run format:js

echo
echo "============================="
echo "  Running Prettier"
echo "============================="
npm run prettier:format
