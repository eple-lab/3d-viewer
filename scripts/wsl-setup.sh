#!/usr/bin/env bash
# WSL(Ubuntu) 안에서 코랩 CLI 를 깐다.
# 윈도우에서는 Colab CLI 를 쓸 수 없어서 WSL 로 넘어왔다.
# 실행:  wsl -e bash -c "tr -d '\r' < /mnt/c/.../scripts/wsl-setup.sh | bash"
set -euo pipefail

echo "== 1) uv 설치 =="
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo "== 2) python 3.12 준비 (시스템이 3.14 라 따로 받는다) =="
uv python install 3.12

echo "== 3) google-colab-cli 설치 =="
uv tool install --python 3.12 google-colab-cli

echo "== 4) 확인 =="
colab --help | head -15
echo
echo "설치 끝. 이제:  colab new -s room --gpu T4"
