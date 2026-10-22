@echo off
REM Check formatting and linting for Python, Jinja, JS, and CSS (no auto-fix)

echo.
echo =============================
echo   Checking Python files
echo =============================
black --check .
isort --check-only .
flake8 .

echo.
echo =============================
echo   Checking HTML/Jinja templates
echo =============================
djlint templates/ --check --profile=jinja --extension=jinja
if errorlevel 1 exit /b %errorlevel%
djlint templates/ --check --profile=jinja --extension=html
if errorlevel 1 exit /b %errorlevel%

REM Static assets: JS, CSS (lint and formatting check)
echo.
echo =============================
echo   Checking CSS files
echo =============================
call npm run lint:css

echo.
echo =============================
echo   Checking JS files
echo =============================
call npm run lint:js

echo.
echo =============================
echo   Checking Prettier formatting
echo =============================
call npm run prettier:check
