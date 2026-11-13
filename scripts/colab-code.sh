#!/usr/bin/env bash
# 인증 코드를 FIFO 로 밀어 넣고 결과를 기다린다.
# 사용: bash colab-code.sh '4/0A...'
export PATH="$HOME/.local/bin:$PATH"
CODE="$1"
if [ -z "${CODE:-}" ]; then echo "코드가 없습니다"; exit 1; fi

if [ ! -p /tmp/cin ]; then echo "FIFO 가 없습니다. colab-start.sh 를 먼저 돌리십시오."; exit 1; fi

# reader(colab) 가 살아 있는지 먼저 확인
if ! pgrep -f "colab new -s room" >/dev/null; then
  echo "colab new 프로세스가 없습니다."; exit 1
fi

printf '%s\n' "$CODE" > /tmp/cin
echo "코드 전달함. 60초 기다립니다."
sleep 60
echo "===== log ====="
tail -25 /tmp/cnew.log
echo "===== status ====="
colab status -s room 2>&1
echo "===== end ====="
