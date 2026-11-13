# 실행 환경 — Windows 에서 코랩 GPU 쓰기

## 1. 왜 WSL 인가

Colab CLI 공식 문서가 지원 범위를 못 박아 두었다.

> the Colab CLI currently supports Linux and macOS only. Windows is not supported at this time.

윈도우에서 그냥 `pip install google-colab-cli` 하면 깔리긴 하지만, 세션 관리가
유닉스 소켓과 키링에 기대고 있어서 첫 명령에서 막힌다. 두 길이 있다.

| 길 | 얻는 것 | 잃는 것 |
|---|---|---|
| **WSL + CLI** (이 프로젝트) | 명령으로 전부 자동화, 결과 파일 바로 내려받기 | WSL 설치·초기화 20~40분 |
| Colab MCP | 브라우저 노트를 옆에서 조작 | opencode 재시작 필요, 파일 전송이 셀 안에서만 |
| 브라우저에서 직접 | 가장 빠름, 설치 0 | 손으로 클릭, 자동화 없음 |

이 프로젝트는 **WSL + CLI** 로 갔다. 노트북을 코드로 밀어 넣고 결과를 바로 받기 위해서다.

## 2. 설치

```bash
# WSL 안에서 (Ubuntu)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

uv python install 3.12          # 시스템 파이썬이 3.14면 3.12를 따로 받는다
uv tool install --python 3.12 google-colab-cli
colab --help
```

`scripts/wsl-setup.sh` 가 이 과정을 그대로 담고 있다.

```powershell
wsl -e bash -c "tr -d '\r' < /mnt/c/.../scripts/wsl-setup.sh | bash"
```

`tr -d '\r'` 는 윈도우에서 저장한 파일의 CRLF 를 지운다. 없으면 `bash: $'\r': command not found` 가 난다.

## 3. 함정 넷 (전부 조용히 실패한다)

### (1) 키링이 없어 매 명령마다 재인증

```
Warning: Could not read the OAuth token from the OS keyring
Warning: Could not save the OAuth token ...
You will be asked to sign in again on the next command.
```

WSL 에는 gnome-keyring 이 없다. `keyrings.alt` 를 넣으면 평문 파일 백엔드로 떨어진다.

```bash
uv tool install --python 3.12 google-colab-cli --with keyrings.alt --force
```

확인:

```bash
~/.local/share/uv/tools/google-colab-cli/bin/python -c "import keyring;print(keyring.get_keyring())"
# keyrings.alt.file.PlaintextKeyring
```

**이걸 안 하면 `colab status` 한 번마다 구글 인증을 다시 해야 한다.**

### (2) PowerShell 이 인용부호와 `$` 를 망가뜨린다

```powershell
wsl -e bash -c "export PATH=$HOME/.local/bin:$PATH; colab status -s room"
# bash: line 1: export: `-s': not a valid identifier
```

PowerShell 이 네이티브 명령에 인자를 넘길 때 `$(...)`, `$VAR`, 괄호를 건드린다.
**해결: 셸 명령을 파일로 쓰고 `wsl -e bash 파일.sh` 로 부른다.**

```bash
# scripts/colab.sh
export PATH="$HOME/.local/bin:$PATH"
exec colab "$@"
```

```powershell
wsl -e bash /mnt/c/.../scripts/colab.sh status -s room
```

### (3) `colab exec -f` 는 **로컬** 파일을 읽는다

```bash
colab exec -s room -f /content/run_notebook.py     # ✗ FileNotFoundError
colab exec -s room -f ./scripts/run_notebook.py    # ✓
```

`-f` 는 파일 내용을 읽어서 원격 커널로 보낸다. 원격 경로가 아니라 **내 컴퓨터 경로**다.

### (4) `tail -f | colab` 으로 인증 코드를 넣으면 안 된다

인증 프롬프트에 코드를 넣으려고 파이프를 쓰면, `tail -f` 가 파이프에 **4KB 블록
버퍼링**을 해서 코드가 전달되지 않는다. FIFO 를 쓰고 writer 홀더를 따로 둬서 EOF 도 막는다.

```bash
mkfifo /tmp/cin
nohup bash -c 'exec 3>/tmp/cin; sleep 7200' &   # writer 홀더
nohup colab new -s room --gpu T4 < /tmp/cin > /tmp/cnew.log 2>&1 &
printf '%s\n' '4/0A...' > /tmp/cin              # 코드 투입
```

## 4. 세션 다루기

```bash
colab new -s room --gpu T4      # 처음 한 번. 브라우저 인증
colab status -s room
# [room] gpu-t4-s-usw4b0-... | Hardware: T4 | Shape: Standard | Status: IDLE
```

| 명령 | 하는 일 |
|---|---|
| `colab upload -s room <로컬> <원격>` | 파일 올리기 |
| `colab exec -s room -f <로컬.py> --timeout 3000` | 스크립트 실행 |
| `colab download -s room <원격> <로컬>` | 결과 받기 |
| `colab ls -s room /content` | 목록 |
| `colab stop -s room` | 세션 끄기 (**꼭**) |

`--timeout 3000` 은 출력이 없을 때 기다리는 시간이다. 기본이 30초라 가중치
내려받기(3분)에서 바로 끊긴다. **`--gpu` 값은 `T4`, `L4`, `G4`, `H100`, `A100` 중
하나여야 한다.** 모르는 값을 주면 조용히 다른 GPU 로 떨어지고 다음 걸음에서 실패한다.

## 5. 이 프로젝트에서 실제로 쓴 순서

```bash
# 1) 세션
colab new -s room --gpu T4

# 2) 파일 세 개
colab upload -s room data/video/watch.mp4   /content/watch.mp4
colab upload -s room notebook/room3d.ipynb  /content/room3d.ipynb
colab upload -s room scripts/run_notebook.py /content/run_notebook.py

# 3) 노트북을 그대로 실행 (upload/download 셀만 대체)
colab exec -s room -f scripts/run_notebook.py --timeout 3000

# 4) 결과
colab download -s room /content/scene.sog          ./scene.sog
colab download -s room /content/measurements.json  ./data/measurements.json

# 5) 정리
colab stop -s room
```

`run_notebook.py` 는 `.ipynb` 를 읽어 코드 셀을 순서대로 `exec` 한다. `%%capture`
같은 셀 매직은 지우고 `!명령` 은 `subprocess.run` 으로 바꾼다. **노트북을 고치면
실행도 같이 바뀐다** — 두 벌을 관리하지 않기 위한 장치다.

## 6. 시간

| 단계 | T4 |
|---|---|
| 세션 생성 | 20~60초 |
| 설치 | 25초 |
| 가중치 내려받기 | **180초** (4.91GB, 세션당 한 번) |
| 복원 24장 | 10초 |
| 알갱이 + sog | 35초 |
| **합계** | **약 5분** |
