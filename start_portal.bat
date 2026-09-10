@echo off
setlocal
cd /d "%~dp0"
python portal.py --host 127.0.0.1 --port 9000 --open
pause
endlocal
