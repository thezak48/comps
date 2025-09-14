@echo off
REM Format all code: Python, Jinja, JS, CSS

REM Python
black .
isort .
flake8 .

djlint templates/ --reformat --profile=jinja

REM Static assets
npm run format
