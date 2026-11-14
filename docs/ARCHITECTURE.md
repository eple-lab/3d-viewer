# 아키텍처 — 영상에서 웹 주소까지

## 1. 한 장으로 보는 흐름

```
 ┌─────────┐   ffmpeg    ┌──────────┐   MapAnything   ┌────────────┐
 │ watch.mp4│ ──────────▶ │ 사진 24장 │ ──────────────▶ │ 점 300만 개 │
 │ 16.2초   │  fps=24/길이 │ 518×294   │  T4 · fp16      │ + 카메라 24대│
 └─────────┘             └──────────┘                 └─────┬──────┘
                                                             │
                        ┌────────────────────────────────────┘
                        ▼
                 ┌──────────────┐   알갱이 변환    ┌──────────────┐
                 │ 점 다듬기      │ ───────────────▶ │ scene.ply     │
                 │ 0.5~99.5%    │  17칸 × 4바이트   │ 68B/알갱이     │
                 └──────────────┘                  └──────┬───────┘
                                                          │ splat-transform 3.10.3
                                                          ▼
                                                   ┌──────────────┐
                                                   │ scene.sog     │  ~15MB
                                                   └──────┬───────┘
                                                          │ git push
                                                          ▼
                                              ┌────────────────────────┐
                                              │ GitHub Pages + index.html│
                                              └────────────────────────┘
```

세 걸음의 성격이 다르다. **복원만 GPU 가 필요하고, 나머지는 어디서든 된다.**
그래서 복원은 코랩에서, 알갱이·줄이기·뷰어는 로컬에서 하는 편이 빠르다.
(이 프로젝트는 재현성을 위해 전부 코랩 노트북 한 곳에 담았다.)

## 2. 파일 구조

```
3d-viewer/
├── index.html                 ← 제출물 ①. 뷰어 전체가 이 한 파일
├── scene.sog                  ← 제출물 ②. 알갱이 파일 (100MiB 미만)
├── .nojekyll                  ← 깃허브가 파일 이름을 손대지 않게 하는 빈 파일
├── README.md                  ← 제출물 ③. 네 가지 기준을 모두 담은 문서
│
├── data/
│   ├── video/watch.mp4        ← 원본 영상 (5.3MB)
│   └── measurements.json      ← 노트북이 남긴 모든 수치
│
├── docs/
│   ├── PRD.md                 ← 무엇을 만들고 무엇을 잴지
│   ├── ARCHITECTURE.md        ← 이 문서
│   ├── MEASUREMENTS.md        ← 수치의 정의와 값
│   ├── LIMITATIONS.md         ← 검은 얼룩 ↔ 시차·정렬
│   ├── PUBLISHING.md          ← 공개 판단과 배포 절차
│   └── CAPTURE.md             ← 촬영 조건과 이번 영상 판정
│
├── notebook/
│   ├── room3d.ipynb           ← 단계별 재현 노트북 (코드 + 설명)
│   └── build_nb.py            ← 노트북 생성기 (셀을 손으로 고칠 때)
│
├── shots/
│   ├── contact-sheet.jpg      ← 뽑은 24장 한눈에 보기
│   ├── viewer.jpg             ← 배포된 주소에서 찍은 화면
│   └── coverage.jpg           ← 앞 / 135° 비교 (한계 설명용)
│
└── scripts/
    ├── serve.ps1              ← 로컬 미리보기 서버
    ├── inspect_sog.py         ← .sog 를 열어 알갱이 수·바이트 검사
    ├── capture_server.py      ← 캔버스를 파일로 받는 작은 서버 (그림 만들 때)
    ├── make_figures.py        ← 캡처를 잘라 README 그림으로
    ├── colab.sh               ← WSL 의 colab CLI 래퍼
    ├── wsl-setup.sh           ← WSL 에 uv·colab CLI 설치
    ├── wsl-keyring.sh         ← 키링 없는 WSL 에 keyrings.alt 넣기
    └── run_notebook.py        ← 노트북 셀을 그대로 exec 해서 무인 실행
```

**왜 `index.html` 하나에 다 넣었나**: 심사자가 npm 을 돌리지 않는다. 빌드 도구가
없으면 `git push` 만으로 배포가 끝나고, 5년 뒤에도 열린다. three.js 와 Spark 는
CDN 에서 importmap 으로 가져온다.

## 3. 단계별 입출력

| # | 단계 | 입력 | 출력 | 도구 | T4 시간 |
|---|---|---|---|---|---|
| 1 | 조건 판정 | `.mp4` | 해상도·길이·fps | ffprobe | 1초 |
| 2 | 프레임 추출 | `.mp4` | `f_001..024.jpg` | ffmpeg `fps=24/길이` | 2초 |
| 3 | 복원 | 24장 | 점 + 카메라 24대 | MapAnything (Apache) | 10초 |
| 4 | 다듬기 | 점 | 점(축소) + 비율 | numpy | 1초 |
| 5 | 알갱이 | 점·색 | `scene.ply` | numpy | 1초 |
| 6 | 축소 | `scene.ply` | `scene.sog` | splat-transform 3.10.3 | 2초 |
| 7 | 측정 | 산출물 | `measurements.json` | numpy | 1초 |

**가중치 내려받기 180초가 전체 시간의 대부분이다.** 4.91GB, 세션당 한 번.

## 4. 좌표계 — 여기서 한 번 뒤집는다

```
MapAnything 출력          three.js / Spark
   Y ↓ (아래가 +)     →      Y ↑ (위가 +)
   Z ←                       Z →
```

```python
p[:, 1] *= -1.0     # y 뒤집기
p[:, 2] *= -1.0     # z 뒤집기
```

`y` 만 뒤집으면 거울상이 되어 글씨가 좌우로 뒤집힌다. **`y` 와 `z` 를 함께** 뒤집어야
손잡이 방향이 맞는다. 이걸 빠뜨리면 장면이 거꾸로 서고, 뷰어의 `뒤집기` 버튼으로도
임시로만 고칠 수 있다(파일에 반영되지 않는다).

## 5. 알갱이 파일 형식 (17칸 = 68바이트)

```
ply
format binary_little_endian 1.0
element vertex N
property float x, y, z              자리            3 × 4 = 12B
property float nx, ny, nz           법선(0)         3 × 4 = 12B
property float f_dc_0,1,2           기본 색         3 × 4 = 12B
property float opacity              불투명도 로짓    1 × 4 =  4B
property float scale_0,1,2          반지름 로그      3 × 4 = 12B
property float rot_0..3             사원수(1,0,0,0) 4 × 4 = 16B
                                    ────────────────────────
                                                          68B
```

**원래 62칸(248B)인 이유**는 각도별 색(`f_rest`) 45칸 때문이다. 우리는 학습을 걸지
않으므로 그 45칸이 전부 0 이다. 0 을 적으면 파일만 3.6배가 되고 얻는 것이 없다.
**헤더에 아예 넣지 않는다.** 뷰어는 없는 칸을 0 으로 읽는다.

색 변환은 학습된 스플랫과 같은 규약을 쓴다.

```
저장: f_dc = (rgb/255 − 0.5) / 0.28209479177387814
읽기: rgb  = (f_dc × 0.28209… + 0.5) × 255
```

## 6. 알갱이 크기 결정

```
r = K × (장면의 가장 긴 변) / sqrt(N)
```

- 알갱이가 덮는 넓이는 `r²` 에 비례한다
- 점 N 개로 표면을 덮으려면 `r² × N` 이 일정해야 한다
- 따라서 `r ∝ 1/sqrt(N)`

**이웃 점 거리를 쓰지 않는 이유**: 점은 사진마다의 깊이에서 나오므로 최근접 이웃이
항상 같은 사진 안의 옆 화소다. 점을 10배 줄여도 이웃 거리는 2배도 안 늘어난다.
그 값을 기준으로 삼으면 점을 줄일 때마다 알갱이가 실제보다 크게 나온다.

`K` 는 눈으로 정한다. 구멍 → 올린다, 뭉개짐 → 내린다. 다시 만드는 데 1초면 된다.

## 7. 뷰어 구조

```
index.html
├── <style>          다크 UI, 모바일 dvh, 640px 이하에서 패널 축소
├── <div .panel>     HUD(단계·진행률·오류) / 조작 / 측정값 / 도움말
├── <script importmap>
│     three@0.185.1            build/three.module.js
│     three/addons/            examples/jsm/
│     @sparkjsdev/spark@2.1.0  dist/spark.module.js
└── <script type="module">
      ① import → ② renderer+scene → ③ fetch+진행률
      → ④ SplatMesh → ⑤ getBoundingBox → fit → loop
```

### 조용히 실패하는 함정 셋

| 함정 | 증상 | 처리 |
|---|---|---|
| `SparkRenderer` 를 `scene.add()` 안 함 | 화면이 까맣다. **오류 없음** | ② 에서 무조건 추가, 단계 표시 |
| `.sog` 인데 `fileType:"sog"` | `Invalid file type` | `TYPE_OF` 표로 `pcsogszip` 매핑 |
| `Box3.setFromObject(splatMesh)` | 빈 상자 → 카메라가 엉뚱한 곳 | `mesh.getBoundingBox(true)` 우선, 실패 시 `Box3` |

세 번째가 특히 고약하다. **오류가 아니라 "빈 상자"가 돌아오기 때문에** 코드는
정상 종료하고 화면만 비어 있다. 뷰어는 두 방법을 모두 시도하고, 콘솔에 어느 쪽이
동작했는지 남긴다.

### 측정값을 화면에 띄우는 이유

파일 크기, 알갱이 수, 알갱이당 바이트, 장면 지름, fps 를 화면 아래에 표시한다.
**README 의 숫자를 심사자가 브라우저에서 바로 검증할 수 있게** 하기 위해서다.
숫자가 안 맞으면 문서가 틀린 것이고, 안 보이면 측정하지 않은 것이다.

## 8. 배포

```
main 브랜치 루트  →  Settings → Pages → Source: Deploy from a branch (main / root)
```

- `.nojekyll` 이 없으면 깃허브가 Jekyll 을 거치며 밑줄로 시작하는 파일을 건너뛴다.
  지금은 해당 파일이 없지만, 나중에 `_` 로 시작하는 파일을 넣을 때 문제가 된다.
- `.sog` 는 `Content-Type: application/octet-stream` 으로 내려온다. 뷰어는
  `fetch → arrayBuffer` 로 읽으므로 MIME 에 의존하지 않는다. **이 점이 중요하다.**
  `Content-Type` 을 보고 분기하는 코드를 넣으면 Pages 에서 깨질 수 있다.
- 파일 하나 100MiB 제한은 git 하드 리밋이다. 넘으면 push 가 거부된다.

## 9. 재현

```powershell
# 로컬 미리보기
powershell -File scripts\serve.ps1      # http://localhost:8777

# 알갱이 파일 검사
uv run --with pillow python scripts\inspect_sog.py scene.sog
```

코랩: `notebook/room3d.ipynb` 를 순서대로. 런타임 유형은 **T4 GPU**.

## 10. 왜 이 구조인가 (대안과 비교)

| 선택지 | 버리고 온 것 | 얻은 것 |
|---|---|---|
| React + Vite 빌드 | 빌드 단계, node_modules | `push` 만으로 배포, 5년 뒤에도 열림 |
| `.ply` 직접 배포 | 217MB | 15MB, 폰에서 3초 |
| 포아송 메시 | 표면 품질 | 프로세스가 죽지 않음 (부록에서 격자 방식) |
| Splat 학습 | 시점별 반사 | GPU 시간 0, 재현성 |
| 서버 업로드 | 임의 영상 처리 | 정적 호스팅, 비용 0, 개인정보 안 남음 |
