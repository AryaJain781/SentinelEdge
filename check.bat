@echo off
REM ==========================================================
REM check.bat - one-click format, lint and test for CMD
REM Usage (from the project root):  check.bat
REM Steps: 1) Black format  2) Ruff lint (auto-fix)  3) Ruff lint (must be clean)  4) Pytest
REM Stops at the first failing step and exits with a non-zero code.
REM ==========================================================
setlocal
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul && (
    py -3.11 --version >nul 2>nul && set "PY=py -3.11"
    if not "%PY%"=="py -3.11" py -3.12 --version >nul 2>nul && set "PY=py -3.12"
)
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo ==^> 1/4 Formatting with Black
%PY% -m black src tests
if errorlevel 1 goto :fail

echo.
echo ==^> 2/4 Linting with Ruff (auto-fix)
%PY% -m ruff check src tests --fix
if errorlevel 1 goto :fail

echo.
echo ==^> 3/4 Linting with Ruff (must be clean)
%PY% -m ruff check src tests
if errorlevel 1 goto :fail

echo.
echo ==^> 4/4 Running tests with Pytest
%PY% -m pytest
if errorlevel 1 goto :fail

echo.
echo ALL CHECKS PASSED (format, lint, tests)
endlocal
exit /b 0

:fail
echo.
echo FAILED - fix the error above and run check.bat again.
endlocal
exit /b 1
