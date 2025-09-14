#!/bin/bash
# Format all code: Python, Jinja, JS, CSS

# Python
black .
isort .
flake8 .

djlint templates/ --reformat --profile=jinja

# Static assets
npm run format:css
npm run format:js
npm run prettier -- "static/js/**/*.js" "static/css/**/*.css"
