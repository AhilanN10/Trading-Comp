# AMD Trading Bot: Live Deployment Guide

This guide details the setup and configuration required to run the **AMD EMA Crossover Trading Bot** (`deploy.py`) continuously on a spare laptop or dedicated server.

---

## 📋 Table of Contents
1. [System & Power Management Setup](#1-system--power-management-setup)
2. [Git-Based Deployment Workflow](#2-git-based-deployment-workflow)
3. [Environment Setup](#3-environment-setup)
4. [Configuration & Keys (Security First)](#4-configuration--keys-security-first)
5. [Running the Bot in the Background](#5-running-the-bot-in-the-background)
6. [Process Resilience & Auto-Restart](#6-process-resilience--auto-restart)
7. [Monitoring & Stopping the Bot](#7-monitoring--stopping-the-bot)

---

## 1. System & Power Management Setup

Laptops are configured to enter low-power sleep modes. Since the bot needs to trade continuously during market hours, you must prevent the laptop from sleeping when the lid is closed or when idle.

### macOS Configuration
1. Open **System Settings** > **Lock Screen** (or **Energy Saver** on older versions).
2. Set **Turn display off on power adapter when inactive** to **Never**.
3. Enable **Prevent automatic sleeping on power adapter when the display is off**.
4. To run with the lid closed, ensure the laptop is connected to an external power supply.
5. **Awake Utility (Terminal)**: To force macOS to stay awake indefinitely, you can open a terminal and run:
   ```bash
   caffeinate -d
   ```
   *(Keep this terminal open, or run it in the background by appending `&`)*

### Windows Configuration
1. Open **Control Panel** > **Power Options** > **Change plan settings**.
2. Set **Put the computer to sleep** to **Never** for when plugged in.
3. Click **Change advanced power settings** > expand **Power buttons and lid** > set **Lid close action** to **Do Nothing** when plugged in.

### Linux Configuration
1. Open `/etc/systemd/logind.conf` in a text editor (requires root privileges).
2. Uncomment and modify the following line:
   ```ini
   HandleLidSwitch=ignore
   ```
3. Restart the systemd service:
   ```bash
   sudo systemctl restart systemd-logind
   ```

---

## 2. Git-Based Deployment Workflow

Using a GitHub repository simplifies keeping the code updated on the spare laptop.

### Initial Setup on the Laptop
1. Open a terminal on the spare laptop.
2. Clone your repository:
   ```bash
   git clone <YOUR_GITHUB_REPO_URL>
   cd <REPO_DIR>/alpaca_sim
   ```

### Critical Security: API Keys
> [!WARNING]
> **NEVER push your `config.py` file to GitHub.**
> A `.gitignore` file has been configured in the repository to block `config.py` and `bot_state.json` from being tracked. Double-check that they are not tracked before pushing.

Because `config.py` is not in the cloned repository, you must create it manually on the laptop:
1. Copy the example configuration:
   ```bash
   cp config_example.py config.py
   ```
2. Open `config.py` in a text editor (e.g. `nano config.py`) and paste your actual Alpaca API credentials.

### Deploying Updates
When you make improvements or parameter adjustments on your main development computer:
1. Commit and push the changes from your dev machine:
   ```bash
   git add .
   git commit -m "Adjusted strategy filters"
   git push origin main
   ```
2. On your spare laptop, navigate to the repo directory and pull the changes:
   ```bash
   git pull origin main
   ```
   *Note: Since your local `config.py` and `bot_state.json` are ignored, they will remain untouched and safe.*

---

## 3. Environment Setup

Install Python 3 and the required dependencies on the target laptop:

```bash
# 1. Update pip (optional but recommended)
python3 -m pip install --upgrade pip

# 2. Install required packages
pip3 install pandas numpy alpaca-trade-api pytz yfinance matplotlib
```

---

## 4. Configuration & Keys (Security First)

Before running the bot:
1. Ensure `config.py` is present in the same directory as `deploy.py`.
2. Populate it with your Alpaca API Keys:
   ```python
   API_KEY = "YOUR_ALPACA_API_KEY"
   SECRET_KEY = "YOUR_ALPACA_SECRET_KEY"
   BASE_URL = "https://paper-api.alpaca.markets"  # Use https://api.alpaca.markets for Real Money
   ```
3. Ensure `bot_state.json` is not deleted, as it tracks dynamic states (like trailing stops/entry tracking details).


---

## 5. Running the Bot in the Background

To ensure the bot continues running even if the terminal window is closed or the session logs out, use a persistent multiplexer like `tmux`.

### Using `tmux` (Recommended)
1. **Install tmux** (if not already installed):
   - **macOS**: `brew install tmux`
   - **Debian/Ubuntu**: `sudo apt install tmux`
2. **Start a new tmux session**:
   ```bash
   tmux new -s trading-bot
   ```
3. **Run the bot script**:
   ```bash
   python3 deploy.py
   ```
4. **Detach from the session**:
   Press `Ctrl + B`, release, and then press `D`. The bot will run in the background.
5. **Re-attach to the session later**:
   ```bash
   tmux attach -t trading-bot
   ```

### Using `nohup` (Alternative)
If `tmux` is not available, run the script with `nohup`:
```bash
nohup python3 deploy.py > bot_output.log 2>&1 &
```
This runs the bot in the background and writes all output to `bot_output.log`.

---

## 6. Process Resilience & Auto-Restart

Temporary network drops or API rate limit timeouts can crash the bot script. Use an auto-restart script to automatically relaunch the bot if it exits.

### For Linux / macOS (Bash)
Create a file named `run_bot.sh` in the same directory:
```bash
#!/bin/bash
echo "Starting AMD Trading Bot monitor loop..."
until python3 deploy.py; do
    echo "Bot crashed with exit code $?. Respawning in 10 seconds..." >&2
    sleep 10
done
```
Make it executable:
```bash
chmod +x run_bot.sh
```
Run `./run_bot.sh` inside your terminal or `tmux` session.

### For Windows Command Prompt (Batch)
Create a file named `run_bot.bat` in the same directory:
```cmd
@echo off
:loop
echo Starting AMD Trading Bot...
python deploy.py
echo Bot exited or crashed. Restarting in 10 seconds...
timeout /t 10
goto loop
```
Double-click `run_bot.bat` to launch it.

### For Windows PowerShell
Create a file named `run_bot.ps1` in the same directory:
```powershell
while ($true) {
    Write-Output "Starting AMD Trading Bot..."
    python deploy.py
    Write-Output "Bot exited or crashed. Restarting in 10 seconds..."
    Start-Sleep -Seconds 10
}
```
Run it in PowerShell:
```powershell
.\run_bot.ps1
```
*(If PowerShell blocks execution, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first in your terminal session)*

---

## 7. Monitoring & Stopping the Bot

### Checking Logs
* If running in `tmux`, re-attach to the session:
  ```bash
  tmux attach -t trading-bot
  ```
* If running with `nohup`, inspect the tail of the log file:
  ```bash
  tail -f bot_output.log
  ```

### Stopping the Bot
* In `tmux`: Attach to the session and press `Ctrl + C`.
* If running with `nohup`:
  1. Find the process ID (PID):
     ```bash
     ps aux | grep deploy.py
     ```
  2. Kill the process:
     ```bash
     kill <PID>
     ```
