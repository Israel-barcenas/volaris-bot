#!/usr/bin/env bash
# Simple startup script for volaris-bot
# Put this file in the repo root and make it executable: chmod +x run_bot.sh

# Adjust VENV path if needed
VENV_DIR=".venv"
REPO_DIR="/home/Israel-barcenas/volaris-bot"

cd "$REPO_DIR" || exit 1

if [ -d "$VENV_DIR" ]; then
  source "$VENV_DIR/bin/activate"
fi

# Ensure Playwright browsers are installed in the venv
# playwright install

# Run the bot with nohup and redirect output to a log file
nohup python bot_volaris.py >> bot.log 2>&1 &

echo "Volaris bot started (nohup). Logs: $REPO_DIR/bot.log"
