#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"
set -a
source .env
set +a
python telegram_bot.py 2>&1 | tee -a ~/child-tracker.log
