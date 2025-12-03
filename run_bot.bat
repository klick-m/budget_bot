@echo off
REM Script to run the budget bot
cd /d %~dp0
echo Starting Budget Bot...
.\\.venv\Scripts\python.exe main.py
pause
