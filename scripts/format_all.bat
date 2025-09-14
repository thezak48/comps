djlint templates/ --reformat --profile=jinja
@echo off
REM Format all code: Python, Jinja, JS, CSS

echo.
echo =============================
echo   Formatting Python files
echo =============================
black .
isort .
flake8 .

echo.
echo =============================
echo   Formatting Jinja templates
echo =============================
djlint templates/ --reformat --profile=jinja

echo.
echo =============================
echo   Formatting CSS files
echo =============================
call npm run format:css

echo.
echo =============================
echo   Formatting JS files
echo =============================
call npm run format:js

echo.
echo =============================
echo   Running Prettier
echo =============================
call npm run prettier:format
