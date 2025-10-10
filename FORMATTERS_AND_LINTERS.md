
# Formatting and Linting Setup

This project enforces consistent code style and quality across Python, Jinja templates, JavaScript, and CSS using a combination of open-source tools and automation. Below is a comprehensive overview of the setup, configuration, and usage.

---

## Python & Jinja

| Tool    | Purpose                                      | Config File         | Notes |
|---------|----------------------------------------------|---------------------|-------|
| Black   | Code formatter for Python                    | `pyproject.toml`    | Enforces PEP 8 style, auto-formats code |
| isort   | Sorts and organizes Python imports           | `.isort.cfg`        | Keeps imports grouped and ordered |
| Flake8  | Linter for Python code quality               | `.flake8`           | Reports style and logic issues |
| djlint  | Formatter/linter for Jinja templates         | `.djlintrc`         | Only runs on `.jinja` files |

**Exclusions:** The `migrations/` folder is excluded from all Python formatters/linters to avoid altering migration scripts.

---

## JavaScript & CSS (Static Assets)

| Tool      | Purpose                        | Config File           | Notes |
|-----------|-------------------------------|-----------------------|-------|
| ESLint    | Linter for JavaScript         | `.eslintrc.js`        | Checks for code issues and enforces style |
| Stylelint | Linter for CSS                | `.stylelintrc.json`   | Checks for CSS errors and style issues |
| Prettier  | Formatter for JS and CSS      | `.prettierrc.json`    | Auto-formats code for consistency |

All static asset tools are managed via `package.json` (see `devDependencies` and `scripts`).

---

## Automation

- **Pre-commit hooks**: `.pre-commit-config.yaml` runs all formatters and linters automatically on commit for Python, Jinja, JS, and CSS files.
	- Python: Black, isort, Flake8
	- Jinja: djlint (only on `.jinja` files)
	- JS/CSS: Prettier, ESLint, Stylelint (via npm scripts)

---


## Installation & Setup

### Python/Jinja
1. (Recommended) Create and activate a virtual environment:
	- Linux/macOS: `python3 -m venv .venv && source .venv/bin/activate`
	- Windows: `python -m venv .venv && .venv\\Scripts\\activate`
2. Install development dependencies:
	- `pip install -r requirements-dev.txt`

### JavaScript/CSS
1. Ensure you have [Node.js](https://nodejs.org/) (v18+) and npm installed.
2. Install dependencies:
	- `npm install`

### Pre-commit Hooks
1. Install pre-commit (if not already):
	- `pip install pre-commit` (already included in `requirements-dev.txt`)
2. Install hooks:
	- `pre-commit install`
3. (Optional) Run all hooks manually:
	- `pre-commit run --all-files`

---

## Usage

### Python/Jinja
- Install dev tools: `pip install -r requirements-dev.txt`
- Format code: `black .` and `isort .`
- Lint code: `flake8 .`
- Format/lint Jinja: `djlint templates/ --reformat --profile=jinja`

### JavaScript/CSS
- Install tools: `npm install`
- Format all static assets: `npm run format`
- Lint JS: `npm run lint:js`
- Lint CSS: `npm run lint:css`

### Format Everything
- Linux/macOS: `scripts/format_all.sh`
- Windows: `scripts/format_all.bat`

---

## File/Folder Exclusions
- `migrations/` is excluded from all Python formatters/linters
- `static/` and `templates/` are excluded from Python formatters/linters
- Only `.jinja` files in `templates/` are checked by djlint
- `node_modules/` and npm/yarn log files are excluded via `.gitignore`

---

## Adding New Tools or Rules
- Update the relevant config file in the project root
- For Python, add to `requirements-dev.txt` if needed
- For JS/CSS, add to `package.json` under `devDependencies`
- Update `.pre-commit-config.yaml` to automate new checks

---

## References
- [Black](https://black.readthedocs.io/)
- [isort](https://pycqa.github.io/isort/)
- [Flake8](https://flake8.pycqa.org/)
- [djlint](https://djlint.com/)
- [ESLint](https://eslint.org/)
- [Stylelint](https://stylelint.io/)
- [Prettier](https://prettier.io/)
- [pre-commit](https://pre-commit.com/)
