param(
  [switch]$CI
)
$ErrorActionPreference = "Stop"

# 1) Create/upgrade venv
if (!(Test-Path .venv)) { py -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -r requirements-dev.txt

# 2) Ensure reports directory exists
if (!(Test-Path reports)) { New-Item -ItemType Directory -Path reports | Out-Null }

# 3) Run tests with reports
$args = @(
  "--maxfail=1",
  "--disable-warnings",
  "--html=reports/test-report.html",
  "--self-contained-html",
  "--junitxml=reports/junit.xml",
  "--cov=stockagents",
  "--cov-report=term-missing:skip-covered",
  "--cov-report=xml:reports/coverage.xml"
)
.\.venv\Scripts\python -m pytest @args
Write-Host "Reports written to ./reports"
