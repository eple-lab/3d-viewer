#!/usr/bin/env bash
# WSL 에는 OS 키링(gnome-keyring 등)이 없어서 colab CLI 가 토큰을 저장하지 못한다.
# keyrings.alt 를 넣으면 평문 파일 백엔드로 떨어져서 저장이 된다.
export PATH="$HOME/.local/bin:$PATH"
set -e
uv tool install --python 3.12 google-colab-cli --with keyrings.alt --force
echo "== python -c keyring =="
"$HOME/.local/share/uv/tools/google-colab-cli/bin/python" - <<'PY'
import keyring
print("backend:", keyring.get_keyring())
PY
echo "== done =="
