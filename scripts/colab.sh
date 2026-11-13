#!/usr/bin/env bash
# WSL 안의 colab CLI 를 감싼다. PowerShell 이 인용부호를 망가뜨리지 않게
# 모든 호출을 이 파일을 거쳐서 한다.
# 사용: wsl -e bash /mnt/c/.../scripts/colab.sh status -s room
export PATH="$HOME/.local/bin:$PATH"
exec colab "$@"
