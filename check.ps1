# check.ps1 - one-click format, lint and test for Windows PowerShell
# Usage (from the project root):
#   powershell -ExecutionPolicy Bypass -File .\check.ps1
# Steps: 1) Black format  2) Ruff lint (auto-fix)  3) Ruff lint (must be clean)  4) Pytest
# The script stops at the first failing step and exits with a non-zero code.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Prefer the project virtual environment, then the Python launcher (3.11, then 3.12).
$Python = "python"
$PyArgs = @()
if (Test-Path ".\.venv\Scripts\python.exe") {
    $Python = ".\.venv\Scripts\python.exe"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in @("3.11", "3.12")) {
        & py "-$v" --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $Python = "py"
            $PyArgs = @("-$v")
            break
        }
    }
}

function Invoke-Step {
    param([string]$Title, [string[]]$Arguments)
    Write-Host ""
    Write-Host "==> $Title" -ForegroundColor Cyan
    & $Python @PyArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Title (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Invoke-Step "1/4 Formatting with Black" @("-m", "black", "src", "tests")
Invoke-Step "2/4 Linting with Ruff (auto-fix)" @("-m", "ruff", "check", "src", "tests", "--fix")
Invoke-Step "3/4 Linting with Ruff (must be clean)" @("-m", "ruff", "check", "src", "tests")
Invoke-Step "4/4 Running tests with Pytest" @("-m", "pytest")

Write-Host ""
Write-Host "ALL CHECKS PASSED (format, lint, tests)" -ForegroundColor Green
exit 0
