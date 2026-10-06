@echo off
rem PDF -> HWPX converter: double-click to run the web app on this PC.
rem All work is done in tools\start_web.ps1 (Korean messages, UTF-8).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\start_web.ps1"
