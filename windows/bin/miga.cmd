@echo off
setlocal DisableDelayedExpansion
"%~dp0..\..\.venv-win\Scripts\python.exe" "%~dp0..\..\main.py" %*
exit /b %errorlevel%
