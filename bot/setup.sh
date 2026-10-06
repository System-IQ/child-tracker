#!/data/data/com.termux/files/usr/bin/bash
set -e
pkg install -y python python-pip python-cryptography libffi openssl
pip install --upgrade pip
pip install -r "$(dirname "$0")/requirements.txt"
echo "✅ تم التثبيت. شغّل: bash bot/run.sh"
