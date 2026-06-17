@echo off
:loop
echo Starting AMD Trading Bot...
python deploy.py
echo Bot exited or crashed. Restarting in 10 seconds...
timeout /t 10
goto loop
