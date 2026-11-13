# -*- coding: utf-8 -*-
"""room3d.ipynb 생성기.  실행: uv run --with nbformat python build_nb.py"""
import io, json, os
from nbformat import v4 as nbf
from nbformat import writes as nbwrites

cells = []
def md(s):  cells.append(nbf.new_markdown_cell(s.strip("\n")))
def code(s): cells.append(nbf.new_code_cell(s.strip("\n")))

# ═══════════════════════════════════════════════════════════════════
md(r"""
# 영상 하나에서 3차원 장면까지 — 재현 노트북

폰으로 찍은 **영상 한 편**에서 3차원 장면을 만들고, 브라우저가 읽을 수 있는
**`.sog` 파일 하나**로 줄여서 내려받습니다. 이 노트의 모든 셀은 위에서부터 차례로
실행하면 됩니다. 중간에 판단이 필요한 곳은 **"멈춤"** 이라고 적어 두었습니다.

```
영상 → 사진 24장 → 점 300만 개 → 알갱이 → .sog (15MB)
                                      └──→ 메시 (부록, 물리를 붙일 때만)
```

## 이 노트가 남기는 것

| 산출물 | 어디에 쓰나 |
|---|---|
| `scene.sog` | 웹 뷰어(`index.html`)가 여는 파일 |
| `measurements.json` | README 의 수치 표에 그대로 옮기는 값 |
| `scene.ply` | 중간 산출물. 형식별 크기를 견줄 때 씀 |
| `room_mesh.glb` | 부록. 물리를 붙일 때만 |

## 실행 환경

런타임 → **런타임 유형 변경** → 하드웨어 가속기 **T4 GPU**.
GPU 가 없으면 5단계에서 메모리가 넘칩니다.

| 단계 | T4 기준 시간 | 비고 |
|---|---|---|
| 설치 | 25초 | |
| 가중치 내려받기 | **180초** | 4.91GB, 처음 한 번만 |
| 복원 (24장) | 10초 | 최대 6.8GB |
| 알갱이 변환 | 1초 | |
| `.sog` 줄이기 | 30초 | npx 내려받기 포함 |

**시간의 대부분은 가중치 내려받기입니다.** 4단계를 걸어 두고 그동안 확인할 것을
미리 읽어 두면 좋습니다.

## 이 노트를 읽는 법

- **설명 셀**은 "왜 이렇게 하는가"를 적었습니다. 코드만 급히 돌릴 때는 건너뛰어도 됩니다.
- **코드 셀**은 판단 근거가 되는 값을 `print` 합니다. 숫자가 안 나오면 다음으로 넘어가지 마십시오.
- **멈춤** 표시가 있는 곳은 결과를 눈으로 보고 정해야 하는 자리입니다.
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 0. 준비 — 지금 무엇이 갖춰졌는지 센다

먼저 GPU 가 실제로 붙었는지 봅니다. **여기서 걸러야 나중에 30분을 안 버립니다.**

`torch.cuda.get_device_capability()` 가 알려 주는 두 번째 숫자가 중요합니다.
T4 는 `(7, 5)` 로 나옵니다. 이 값이 **8 미만이면 bfloat16 을 하드웨어로 못 합니다.**
5단계에서 `amp_dtype="fp16"` 을 골라야 하는 근거가 바로 이 값입니다.

> 흔한 실수: 작은 시험(8장)에서는 bf16 으로도 돌아갑니다. 그래서 "되는데?" 하고
> 24장으로 늘리면 그때 메모리가 넘칩니다. 원인은 계산 정밀도인데 오류 메시지는
> "CUDA out of memory" 라서 엉뚱한 곳을 보게 됩니다.
""")

code(r"""
import torch, time, json, os

T0 = time.time()
assert torch.cuda.is_available(), (
    "GPU 가 안 잡혔습니다.\n"
    "런타임 → 런타임 유형 변경 → 하드웨어 가속기 'T4 GPU' 로 바꾸고\n"
    "런타임 → 런타임 다시 시작 후 이 셀부터 다시 실행하십시오.")

gpu = torch.cuda.get_device_properties(0)
cc  = torch.cuda.get_device_capability()
print(f"GPU        {gpu.name}")
print(f"메모리      {gpu.total_memory/1e9:.1f} GB")
print(f"계산 능력   {cc[0]}.{cc[1]}")
print(f"bfloat16   {'지원' if cc[0] >= 8 else '미지원 → fp16 을 써야 합니다'}")
print(f"torch      {torch.__version__}")
""")

md(r"""
## 1. 설치

세 가지를 깝니다.

- **map-anything** — 영상에서 점과 카메라를 뽑는 모델입니다. 저장소와 가중치 모두
  `facebook/map-anything-apache` 로 Apache-2.0 이고 승인 절차가 없습니다.
  기본판 `facebook/map-anything` 은 가중치가 cc-by-nc 라 가려 씁니다.
- **open3d** — 부록(메시)에서만 씁니다.
- **trimesh** — 메시를 `.glb` 로 내보낼 때 씁니다.

**토치를 다시 깔지 않습니다.** 코랩에 이미 CUDA 판이 들어 있고, 여기서 `pip install torch`
를 치면 CPU 판으로 갈아엎는 일이 생깁니다. 그러면 런타임을 다시 시작해야 하고
받아 둔 가중치도 날아갑니다.

`%%capture` 는 pip 출력이 수백 줄이라 화면을 덮어 버리는 것을 막습니다.
설치가 실패하면 `%%capture` 를 지우고 다시 돌려 원인을 보십시오.
""")

code(r"""
%%capture
# 이미 받아 뒀으면 다시 받지 않는다. 셀을 두 번 돌려도 터지지 않게.
!cd /content && { test -d map-anything || git clone -q --depth 1 https://github.com/facebookresearch/map-anything.git; }
!cd /content/map-anything && pip install -q -e .
!pip install -q open3d trimesh
""")

md(r"""
설치 직후 `import mapanything` 은 **실패합니다.** 저장소를 `/content/map-anything`
아래에 받았는데 파이썬은 그 경로를 모르기 때문입니다. 경로를 끼워 넣습니다.

`pip install -e .` 를 했는데도 실패한다면, `-e` 설치가 현재 파이썬이 아닌 다른
인터프리터로 들어간 것입니다. 이 `sys.path.insert` 한 줄이 그 경우까지 덮어 줍니다.
""")

code(r"""
import sys
sys.path.insert(0, '/content/map-anything')

import mapanything
print("mapanything:", mapanything.__file__)
print(f"여기까지 {time.time()-T0:.0f}초")
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 2. 영상을 올리고 조건을 검사한다

아래 셀을 돌리면 파일 선택 창이 뜹니다. 영상을 고르십시오.

### 통과해야 하는 조건 네 가지

| 조건 | 왜 | 이 노트의 판정 |
|---|---|---|
| **가로** | 세로 영상은 화면 위아래를 천장과 바닥이 차지합니다. 둘 다 밋밋해서 얻을 것이 적습니다 | `width > height` |
| **15~20초** | 그 이상은 같은 장면이 되풀이될 뿐입니다 | 15 ≤ 길이 ≤ 20 |
| **24장으로 뽑을 수 있는 길이** | 너무 짧으면 프레임 사이 시차가 커서 정합이 어긋납니다 | 길이 ≥ 8초 |
| **흐리지 않음** | 빨리 지나가면 번진 장이 섞입니다 | 3단계에서 점수로 확인 |

**가장 흔한 실패는 "제자리에서 몸만 돌며 찍은 영상"입니다.** 이건 해상도나 길이로는
안 걸러집니다. 6단계에서 카메라 퍼짐을 재서 판정합니다.

`ffprobe` 로 잰 값을 그대로 출력하고, 조건마다 통과 여부를 찍습니다.
**✗ 가 하나라도 있으면 여기서 멈추고** 다시 찍을지 정하십시오.
""")

code(r"""
import os, subprocess, json
from google.colab import files

up = files.upload()
VIDEO = os.path.join('/content', list(up.keys())[0])
print(f"올린 파일: {VIDEO}  {os.path.getsize(VIDEO)/1e6:.1f}MB")

def probe(path):
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,duration,nb_frames,r_frame_rate,codec_name',
         '-of', 'json', path],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)['streams'][0]

info   = probe(VIDEO)
W, H   = int(info['width']), int(info['height'])
DUR    = float(info.get('duration', 0))
NFR    = int(info.get('nb_frames', 0) or 0)
NUM, DEN = (info['r_frame_rate'].split('/') + ['1'])[:2]
SRC_FPS = float(NUM) / float(DEN)

print(f"\n해상도    {W}×{H}  ({'가로' if W > H else '세로'})")
print(f"길이      {DUR:.2f}초")
print(f"원본 fps  {SRC_FPS:.2f}  (프레임 {NFR}장)")
print(f"코덱      {info['codec_name']}")

ok_land = W > H
ok_dur  = 15 <= DUR <= 20
ok_len  = DUR >= 8
print()
print(("통과" if ok_land else "실패") + "  가로 영상")
print(("통과" if ok_dur  else "주의") + "  15~20초")
print(("통과" if ok_len  else "실패") + "  8초 이상")

if not (ok_land and ok_len):
    print("\n>>> 멈춤: 다시 찍는 편이 빠릅니다.")
if ok_dur and ok_land and ok_len:
    print("\n>>> 조건 통과. 다음으로 넘어갑니다.")
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 3. 사진 24장을 뽑는다

### 왜 24장인가

복원 모델은 **사진 사이의 시차**로 거리를 잽니다. 장수가 늘면 시차 정보가 늘지만
메모리와 시간이 함께 늘고, 100장을 넘기면 T4 16GB 로는 넘칩니다.

| 장수 | 복원 시간 | 최대 메모리 |
|---|---|---|
| 24 | 10초 | 6.8GB |
| 32 | 13초 | 7.3GB |
| 64 | 32초 | 9.5GB |
| 96 | 55초 | 12.0GB |
| 128 | 넘침 | |

24장에서 얻는 것이 가장 많습니다. **더 또렷하게 보고 싶은 곳이 있으면 장수를
늘리는 것보다 그 앞에서 한두 걸음 더 움직여 찍는 편이 낫습니다.**

### 왜 고정 fps 를 안 쓰나

`fps=1.6` 처럼 상수로 두면 영상이 길 때 장수가 같이 늘어납니다. 60초짜리에
`fps=1.6` 을 주면 96장이 나와서 메모리가 넘칩니다. **길이와 무관하게 24장**이
되게 하려면 `fps = 24 / 길이` 로 계산해야 합니다.

### 흐림을 점수로 남긴다

프레임마다 회색조로 줄여 이웃 화소 차이의 평균을 냅니다. **값이 낮을수록 번진 장**입니다.
중앙값의 절반 아래로 떨어지는 장이 셋 이상이면 다시 찍는 편이 빠릅니다.

사진은 모델이 정한 크기로 줄어서 들어갑니다. 원본이 4K 여도 16:9 면 **518×294** 로
들어갑니다. 케이블이나 시계 줄처럼 가는 것이 뭉개지는 까닭이 여기 있습니다.
""")

code(r"""
import glob, subprocess
import numpy as np
from PIL import Image

TARGET = 24
FPS    = TARGET / DUR
print(f"영상 {DUR:.2f}초 → fps {FPS:.4f} (장수 {round(DUR*FPS)}장 예상)")

os.makedirs('/content/frames', exist_ok=True)
for f in glob.glob('/content/frames/*.jpg'):
    os.remove(f)

t = time.time()
subprocess.run(['ffmpeg', '-v', 'error', '-i', VIDEO,
                '-vf', f'fps={FPS}', '-q:v', '2',
                '/content/frames/f_%03d.jpg'], check=True)
paths = sorted(glob.glob('/content/frames/*.jpg'))[:TARGET]
print(f"{len(paths)}장 뽑음 ({time.time()-t:.1f}초)")

def sharpness(path):
    # 회색조 480×270 으로 줄여 이웃 화소 차이의 평균. 낮으면 번진 장.
    g = np.asarray(Image.open(path).convert('L').resize((480, 270)), dtype=np.float64)
    return float(np.abs(np.diff(g, axis=0)).mean() + np.abs(np.diff(g, axis=1)).mean())

scores = [sharpness(p) for p in paths]
med    = float(np.median(scores))
blurry = [i for i, s in enumerate(scores) if s < med * 0.5]

print("\n장마다 선명도")
print("  " + "  ".join(f"{i:02d}:{s:.1f}" for i, s in enumerate(scores)))
print(f"\n중앙값 {med:.2f} · 최소 {min(scores):.2f} · 최대 {max(scores):.2f}")
print(f"번진 장 {len(blurry)}장 {blurry if blurry else ''}")
if len(blurry) >= 3:
    print(">>> 멈춤: 번진 장이 셋 이상입니다. 다시 찍는 편이 빠릅니다.")
""")

code(r"""
# 뽑은 장을 눈으로 봅니다. 번진 장과 시차가 있는지 함께 확인하십시오.
import matplotlib.pyplot as plt

cols = 4
rows = int(np.ceil(len(paths) / cols))
fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.2, rows * 1.9))
for ax in axes.ravel():
    ax.axis('off')
for ax, pth, s in zip(axes.ravel(), paths, scores):
    ax.imshow(Image.open(pth))
    ax.set_title(f"{os.path.basename(pth)[2:5]} · {s:.1f}", fontsize=8)
plt.tight_layout()
plt.show()
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 4. 복원 — 사진에서 점과 카메라를 뽑는다

**모델이 하는 일**은 사진마다 깊이 지도를 하나씩 만들고, 그 사진들이 각각 어디서
찍혔는지를 함께 알아내어 전부를 한 좌표계에 겹치는 것입니다. 결과로 색을 가진 점
수백만 개와, 카메라가 있던 자리 스물몇 곳이 나옵니다.

### 함정 — `amp_dtype` 을 `fp16` 으로

공식 예제는 `amp_dtype="bf16"` 입니다. 그런데 **T4(계산 능력 7.5)에는 bf16 이
하드웨어로 없습니다.** bf16 을 주면 계산이 통째로 32비트로 풀려서 메모리가 두 배가
되고, 24장에서 넘칩니다. 0단계에서 `bfloat16 미지원` 이라고 나온 것이 이 근거입니다.

```python
amp_dtype="fp16"     # T4·V100 등 계산 능력 7.x 에서는 반드시 이것
```

### 메모리를 아끼는 스위치

| 인자 | 하는 일 |
|---|---|
| `memory_efficient_inference=True` | 중간 결과를 GPU 에 오래 붙들지 않습니다 |
| `minibatch_size=1` | 사진을 한 장씩 넣습니다. 느리지만 메모리가 제일 적게 듭니다 |
| `apply_mask=True` | 하늘·구멍처럼 믿을 수 없는 점을 표시해 둡니다 |
| `mask_edges=True` | 사진 가장자리는 시차가 없어서 오차가 큽니다. 걸러 냅니다 |
| `apply_confidence_mask=False` | 24장 규모에서는 켜면 점이 너무 많이 날아갑니다 |

**가중치 4.91GB 를 처음 한 번 받습니다.** 세션이 살아 있는 동안은 다시 안 받습니다.
""")

code(r"""
from mapanything.models import MapAnything
from mapanything.utils.image import load_images

t = time.time()
model = MapAnything.from_pretrained("facebook/map-anything-apache").to("cuda").eval()
print(f"모델 준비 {time.time()-t:.0f}초")

t = time.time()
views = load_images(paths)
print(f"사진 넣기 {time.time()-t:.1f}초 · 한 장 크기 {tuple(views[0]['img'].shape[-2:])}")

torch.cuda.reset_peak_memory_stats()
t = time.time()
pred = model.infer(
    views,
    memory_efficient_inference=True,
    minibatch_size=1,
    use_amp=True,
    amp_dtype="fp16",          # ← T4 에서는 반드시 fp16
    apply_mask=True,
    mask_edges=True,
    apply_confidence_mask=False,
)
torch.cuda.synchronize()
RECON_SEC = time.time() - t
PEAK_GB   = torch.cuda.max_memory_allocated() / 1e9
print(f"복원 {RECON_SEC:.1f}초 · 최대 GPU 메모리 {PEAK_GB:.2f}GB")
print(f"돌려준 뷰 {len(pred)}개 · 키: {sorted(pred[0].keys())}")
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 5. 점을 모으고 쓸 만한지 잰다

여기서 두 가지를 합니다.

### (1) 멀리 튄 점을 버린다

창밖, 거울, 유리에 비친 것은 **엉뚱하게 먼 거리**로 잡힙니다. 그대로 두면 장면이
한없이 커지고, 다음 단계에서 알갱이 반지름을 정할 때 기준(장면의 가장 긴 변)이
망가집니다. 각 축의 **0.5 ~ 99.5 백분위 밖**을 버립니다. 타원체로 자르는 대신 축별로
자르는 이유는, 방 하나가 가로로 길어도 가로만 잘리지 않게 하기 위해서입니다.

### (2) 카메라가 실제로 움직였는지 잰다

```
카메라 퍼짐 = 카메라 위치들의 경계 상자 대각선
비율       = 카메라 퍼짐 / 장면 대각선
```

이 비율이 **0.1 보다 작으면** 제자리에서 몸만 돌린 것입니다. 그러면 사진들이 거의
한 점에서 찍힌 셈이라 거리를 못 재고, 결과가 **아치 모양으로 휘어** 나옵니다.

> 왜 하필 0.1 인가: 장면 대각선의 10% 를 움직였다는 것은, 책상 하나를 앞에서
> 옆으로 옮겨 가며 찍은 정도입니다. 이보다 적으면 삼각측량의 밑변이 너무 짧습니다.

숫자가 나오면 `spread_ratio` 를 기록해 두십시오. **README 의 수치 판정 항목이
바로 이 값입니다.**
""")

code(r"""
import numpy as np

pts, cols, cams = [], [], []
for v in pred:
    m = v['mask'][0, ..., 0].cpu().numpy()                    # 믿을 수 있는 화소
    pts.append(v['pts3d'][0].cpu().numpy()[m])
    cols.append((v['img_no_norm'][0].cpu().numpy() * 255)
                .clip(0, 255).astype(np.uint8)[m])
    cams.append(v['camera_poses'][0].cpu().numpy())

xyz = np.concatenate(pts).astype(np.float64)
rgb = np.concatenate(cols)
cams = np.stack(cams)
N_RAW = len(xyz)
print(f"점 {N_RAW:,}개 (사진 {len(pred)}장)")

# 각 축 0.5 ~ 99.5 백분위 밖을 버린다
lo = np.percentile(xyz, 0.5,  axis=0)
hi = np.percentile(xyz, 99.5, axis=0)
keep = np.all((xyz > lo) & (xyz < hi), axis=1)
xyz, rgb = xyz[keep], rgb[keep]
print(f"멀리 튄 점을 버리고 {len(xyz):,}개  ({100*len(xyz)/N_RAW:.1f}% 남음)")

# 카메라가 실제로 움직였는가
cpos   = cams[:, :3, 3]
spread = float(np.linalg.norm(cpos.max(0) - cpos.min(0)))
diag   = float(np.linalg.norm(xyz.max(0) - xyz.min(0)))
ratio  = spread / diag

print(f"\n카메라 퍼짐   {spread:.4f}")
print(f"장면 대각선   {diag:.4f}")
print(f"비율          {ratio:.4f}")
print()
if ratio > 0.1:
    print(">>> 걸어 다니며 찍은 것으로 보입니다. 다음으로 넘어갑니다.")
else:
    print(">>> 멈춤: 카메라가 거의 안 움직였습니다.")
    print("    제자리에서 돌며 찍었다면 아치 모양으로 휘어 나올 가능성이 큽니다.")
    print("    그대로 가려면 이 사실을 README 의 '한계' 항목에 적으십시오.")

np.save('/content/xyz.npy', xyz)
np.save('/content/rgb.npy', rgb)
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 6. 점을 알갱이로 바꾼다

점은 **크기가 없어서** 화면을 못 채웁니다. 확대하면 사이가 전부 비어 보입니다.
그래서 점 하나를 **부피와 투명도를 가진 알갱이 하나**로 바꿉니다.

### 알갱이 하나에 원래 62칸

| 칸 | 개수 | 어디서 오나 |
|---|---|---|
| 자리 | 3 | 점에서 |
| 법선 | 3 | 안 씀. 0 |
| 기본 색 | 3 | 점 색. 구면 조화 0차 |
| **각도별 색** | **45** | **없음.** 학습을 걸어야 채워짐 |
| 불투명도 | 1 | 정함 |
| 크기 | 3 | 정함 |
| 회전 | 4 | 근거 없음. 안 돌린 사원수 |

**각도별 색 45칸은 헤더에 아예 넣지 않습니다.** 0 으로 채워 적으면 파일만 3.6배가
됩니다. 빼면 칸이 **17개**, 알갱이 하나에 **68바이트**입니다.

### 색을 왜 저렇게 넣나

학습된 스플랫의 색은 `f_dc = (color - 0.5) / 0.28209…` 로 저장됩니다. 뷰어는 이걸
읽을 때 반대로 풀어 씁니다. 0.28209 는 구면 조화 0차 계수라서 그 자리에 고정으로
들어갑니다.

### 알갱이 반지름

알갱이가 덮는 넓이는 반지름의 제곱에 비례합니다. 점 N 개로 표면을 덮으려면 반지름이
N 의 제곱근에 반비례해야 합니다.

```
r = K × (장면의 가장 긴 변) / sqrt(N)      K = 1.4 로 시작
```

**이웃 점까지의 거리를 기준으로 삼지 않습니다.** 점이 사진마다의 깊이에서 나오다
보니 가장 가까운 이웃은 늘 같은 사진 안의 옆 화소입니다. 점을 열 배 줄여도 이웃
거리가 두 배도 안 늘어나서 기준이 못 됩니다.

**좌표를 뒤집습니다.** 이 모델은 Y 가 아래를 향하고 three.js 는 Y 가 위입니다.
`y` 와 `z` 의 부호를 뒤집지 않으면 장면이 거꾸로 섭니다.

### 멈춤

만들고 나서 브라우저에 띄워 보십시오. **구멍이 보이면 K 를 올리고, 뭉개지면 내립니다.**
고친 값으로 다시 만드는 데는 몇 초면 됩니다.
""")

code(r"""
import os

SH_C0    = 0.28209479177387814
K        = 1.4        # 알갱이 크기. 구멍이 보이면 올리고, 뭉개지면 내립니다
OPACITY  = 0.9

def to_splat_ply(xyz, rgb, path, K=1.4, opacity=0.9):
    n      = len(xyz)
    extent = float((xyz.max(0) - xyz.min(0)).max())
    r      = K * extent / np.sqrt(n)

    # Y 축이 아래를 향한다 → three.js 에 맞게 y·z 부호를 뒤집는다
    p = xyz.astype(np.float32).copy()
    p[:, 1] *= -1.0
    p[:, 2] *= -1.0

    out = np.zeros((n, 17), dtype=np.float32)   # 17칸 × 4바이트 = 68바이트
    out[:, 0:3]   = p
    out[:, 6:9]   = (rgb.astype(np.float32) / 255.0 - 0.5) / SH_C0   # 기본 색
    out[:, 9]     = np.log(opacity / (1.0 - opacity))                # 불투명도(로짓)
    out[:, 10:13] = np.log(r)                                        # 반지름(로그)
    out[:, 13]    = 1.0                                              # 사원수 w

    hdr = ("ply\nformat binary_little_endian 1.0\n"
           f"element vertex {n}\n"
           "property float x\nproperty float y\nproperty float z\n"
           "property float nx\nproperty float ny\nproperty float nz\n"
           "property float f_dc_0\nproperty float f_dc_1\nproperty float f_dc_2\n"
           "property float opacity\n"
           "property float scale_0\nproperty float scale_1\nproperty float scale_2\n"
           "property float rot_0\nproperty float rot_1\n"
           "property float rot_2\nproperty float rot_3\n"
           "end_header\n")
    with open(path, 'wb') as f:
        f.write(hdr.encode())
        f.write(out.tobytes())
    return r, extent, len(hdr)

t = time.time()
splat_r, extent, hdr_len = to_splat_ply(xyz, rgb, '/content/scene.ply',
                                        K=K, opacity=OPACITY)
PLY_BYTES = os.path.getsize('/content/scene.ply')
BPS       = (PLY_BYTES - hdr_len) / len(xyz)

print(f"알갱이 {len(xyz):,}개 · 반지름 {splat_r:.5f} (긴 변 {extent:.3f}) · {time.time()-t:.1f}초")
print(f"scene.ply {PLY_BYTES/1e6:.1f}MB")
print(f"알갱이 하나에 {BPS:.2f}바이트  (정상이면 정확히 68)")
print(f"헤더 속성 17개 · f_rest 없음(정상) · 헤더 {hdr_len}바이트")

assert abs(BPS - 68) < 0.01, "68바이트가 아닙니다. 헤더에 45칸이 섞였는지 보십시오."
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 7. `.sog` 로 줄인다

**건너뛸 수 없는 단계입니다.** 알갱이 320만 개면 `.ply` 가 217MB 인데, 깃허브는
파일 하나에 **100MiB** 가 한계입니다.

```
npx -y @playcanvas/splat-transform@3.10.3 -w scene.ply scene.sog
```

- **`-w`** 를 빼면 파일이 이미 있을 때 덮어쓰지 않고 멈춥니다. 다시 돌릴 때 걸립니다.
- **버전을 3.10.3 으로 고정합니다.** 3.11.0 부터 기본으로 쓰는 SOG v3 를 Spark 2.1.0 과
  2.4.0 이 읽지 못합니다. 최신을 쓰면 뷰어에서 `Invalid file type` 이 납니다.
- `npx` 가 패키지를 처음 받을 때 20~30초 걸립니다. 두 번째부터는 빠릅니다.

### 크기를 말할 때 기준을 밝힌다

같은 파일이 도구마다 다르게 찍힙니다.

- 1,000,000 으로 나누면 **15.3MB**
- 1,048,576 으로 나누면 **14.6MB**

이 노트는 둘 다 출력합니다. README 에도 어느 기준인지 적으십시오.
""")

code(r"""
t = time.time()

# 3.11.0 부터의 SOG v3 는 Spark 2.1.0 / 2.4.0 이 못 읽으므로 3.10.3 으로 고정
!npx -y @playcanvas/splat-transform@3.10.3 -w /content/scene.ply /content/scene.sog

SOG_BYTES = os.path.getsize('/content/scene.sog')
print(f"\n변환 {time.time()-t:.0f}초")
print(f"scene.ply {PLY_BYTES/1e6:.1f}MB  →  scene.sog {SOG_BYTES/1e6:.1f}MB")
print(f"줄어든 배수 {PLY_BYTES/SOG_BYTES:.1f}배")
print(f"100MiB 한계 대비 {100*SOG_BYTES/104857600:.1f}%")
assert SOG_BYTES < 100 * 1048576, "100MiB 를 넘었습니다. 알갱이 수를 줄이거나 K 를 키우십시오."
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 8. 형식별 크기를 견준다 (README 의 수치 표)

같은 알갱이를 네 형식으로 저장해 봅니다. **이 표가 README 의 "형식별 크기" 항목**입니다.

| 형식 | 무엇을 하나 | Spark 가 읽나 |
|---|---|---|
| `.ply` | 아무것도 안 줄임. 기준 | 읽음 |
| `.splat` | 알갱이당 32바이트로 재배열 | 읽음 |
| `.compressed.ply` | 양자화로 16바이트대 | 읽음 |
| `.sog` | 묶고(zip) 압축 | 읽음 (`pcsogszip`) |

**배수는 장면과 개수에 따라 달라집니다.** 남의 표를 그대로 옮기지 말고 이 셀의
숫자를 쓰십시오.

실패해도 노트가 멈추지 않게 각 변환을 따로 감쌌습니다. 어떤 형식이 실패했는지는
출력에 남습니다.
""")

code(r"""
import subprocess, os

def convert(dst):
    r = subprocess.run(
        ['npx', '-y', '@playcanvas/splat-transform@3.10.3',
         '-w', '/content/scene.ply', dst],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  실패: {(r.stderr or r.stdout).strip().splitlines()[-1][:120]}")
        return None
    return os.path.getsize(dst)

Formats = {'ply': '/content/scene.ply',
           'splat': '/content/scene.splat',
           'compressed.ply': '/content/scene.compressed.ply',
           'sog': '/content/scene.sog'}

# 아직 없는 것만 만든다 (.sog 는 앞 단계에서 이미 만들었다)
for name, path in Formats.items():
    if os.path.exists(path):
        continue
    print(f"{name} 만드는 중…")
    convert(path)

print()
print(f"{'형식':<16}{'바이트':>12}{'MB(1e6)':>10}{'배수':>8}")
print("-" * 46)
base = os.path.getsize(Formats['ply'])
sizes = {}
for name, path in Formats.items():
    if not os.path.exists(path):
        continue
    b = os.path.getsize(path)
    sizes[name] = b
    print(f"{name:<16}{b:>12,}{b/1e6:>10.1f}{base/b:>8.1f}")

print(f"\n알갱이당 바이트")
for name, b in sizes.items():
    print(f"  {name:<16}{b/len(xyz):>8.2f} B")
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 9. 측정값을 한 파일로 남긴다

README 에 옮겨 적을 값이 흩어져 있으면 옮기다 틀립니다. 한 번에 모아 `measurements.json`
으로 저장하고, README 에 붙일 표를 같이 출력합니다.

**이 셀의 출력을 그대로 복사해 README 에 넣으십시오.**
""")

code(r"""
import json

measurements = {
    "video": {
        "name": os.path.basename(VIDEO),
        "width": W, "height": H,
        "duration_s": round(DUR, 3),
        "source_fps": round(SRC_FPS, 3),
        "frames_extracted": len(paths),
    },
    "frames": {
        "sharpness_median": round(med, 2),
        "sharpness_min": round(min(scores), 2),
        "sharpness_max": round(max(scores), 2),
        "blurry_frames": blurry,
    },
    "recon": {
        "model": "facebook/map-anything-apache",
        "amp_dtype": "fp16",
        "seconds": round(RECON_SEC, 1),
        "peak_gpu_gb": round(PEAK_GB, 2),
        "points_raw": int(N_RAW),
        "points_kept": int(len(xyz)),
        "camera_spread": round(spread, 4),
        "scene_diagonal": round(diag, 4),
        "spread_ratio": round(ratio, 4),
    },
    "splat": {
        "count": int(len(xyz)),
        "K": K,
        "radius": round(splat_r, 6),
        "extent": round(extent, 4),
        "ply_bytes": int(PLY_BYTES),
        "bytes_per_gaussian": round(BPS, 2),
        "header_properties": 17,
    },
    "formats": {k: int(v) for k, v in sizes.items()},
    "sog": {
        "bytes": int(SOG_BYTES),
        "megabytes_1e6": round(SOG_BYTES / 1e6, 2),
        "mebibytes": round(SOG_BYTES / 1048576, 2),
        "ratio_vs_ply": round(PLY_BYTES / SOG_BYTES, 1),
    },
    "env": {
        "gpu": gpu.name,
        "vram_gb": round(gpu.total_memory / 1e9, 1),
        "compute_capability": f"{cc[0]}.{cc[1]}",
    },
}

with open('/content/measurements.json', 'w', encoding='utf-8') as f:
    json.dump(measurements, f, ensure_ascii=False, indent=2)

m = measurements
print("## README 에 붙일 표\n")
print("| 항목 | 값 |")
print("|---|---|")
print(f"| 영상 | {m['video']['width']}×{m['video']['height']}, {m['video']['duration_s']}초, {m['video']['source_fps']}fps |")
print(f"| 사진 | {m['video']['frames_extracted']}장 (선명도 중앙값 {m['frames']['sharpness_median']}) |")
print(f"| 복원 | {m['recon']['seconds']}초, 최대 GPU {m['recon']['peak_gpu_gb']}GB |")
print(f"| 점 | {m['recon']['points_raw']:,} → {m['recon']['points_kept']:,}개 |")
print(f"| **카메라 퍼짐 / 장면 대각선** | **{m['recon']['spread_ratio']}** ({m['recon']['camera_spread']} / {m['recon']['scene_diagonal']}) |")
print(f"| 알갱이 수 | {m['splat']['count']:,}개 |")
print(f"| **알갱이당 바이트** | **{m['splat']['bytes_per_gaussian']}B** |")
for k, v in m['formats'].items():
    print(f"| {k} 크기 | {v/1e6:.1f}MB ({v:,}B) |")
print(f"| **.sog vs .ply** | **{m['sog']['ratio_vs_ply']}배 작음** |")
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 10. 내려받는다

`scene.sog` 와 `measurements.json` 을 받습니다. 브라우저가 두 번 물어봅니다.

받은 파일을 프로젝트 폴더의 **`index.html` 과 같은 위치**에 두면 끝입니다.
로컬에서 보려면 그 폴더에서:

```bash
python -m http.server 8777
```

`http://localhost:8777` 을 엽니다. **`file://` 로 열면 브라우저가 파일 읽기를 막습니다.**

### 확인할 것

웹에 올린 뒤에는 주소 뒤에 `/scene.sog` 를 붙여 **파일이 실제로 내려오는지** 먼저
확인하십시오. 이게 404 면 화면은 까맣고, 원인은 뷰어가 아니라 배포입니다.
""")

code(r"""
from google.colab import files

files.download('/content/scene.sog')
files.download('/content/measurements.json')

print(f"전체 {time.time()-T0:.0f}초")
print(f"scene.sog {SOG_BYTES/1e6:.1f}MB · 알갱이 {len(xyz):,}개")
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 부록. 메시 — 물리를 붙일 때만

**이번 제출에는 필요 없습니다.** 화면에 띄우기만 할 것이면 건너뛰십시오. 알갱이는
그리기 위한 것이라 딛고 설 면이 없습니다. 캐릭터를 올려 놓고 움직이게 하려면
삼각형 메시가 따로 있어야 합니다.

### 포아송 대신 격자를 쓰는 이유

포아송 표면 복원(`create_from_point_cloud_poisson`)이 정석이지만, 등위면을 뽑는
단계에서 **파이썬 예외가 아니라 프로세스째 죽는 일**이 있습니다. `try` 로 못 잡으니
다음 설정으로 넘어가지도 못합니다. 그래서 격자로 갑니다.

```
점을 격자에 찍는다 → 형태 연산으로 구멍을 메운다(binary_closing)
 → 흐린다(gaussian_filter) → 등위면을 뽑는다(marching_cubes)
 → 떠 있는 부스러기를 버린다 → 타우빈으로 다듬는다 → 삼각형 수를 줄인다
```

메우는 정도를 반지름으로 정할 수 있다는 것이 이 길의 이점입니다. 타우빈은
라플라시안과 달리 부피가 덜 쪼그라듭니다.

**안 찍힌 곳은 색을 가져올 데가 없어 검게 남습니다.** 꼭짓점마다 가까운 점까지의
거리를 재서 본 곳과 지어낸 곳을 가르고, 지어낸 곳은 이웃 평균을 여러 번 되풀이해
채웁니다. 이웃 평균 반복이 라플라스 방정식을 푸는 것과 같아서 가장자리 색이
매끄럽게 이어집니다.

물체를 어디에 올릴지는 **수평면이 몰린 높이**를 세면 찾을 수 있습니다. 법선의
세로 성분이 1 에 가까운 꼭짓점을 높이별로 세면 바닥과 천장이 가장 크게 잡힙니다.
""")

code(r"""
# 필요할 때만 실행하십시오. T4 기준 1~3분.
import open3d as o3d
import trimesh

xyz_m = xyz.copy()
xyz_m[:, 1] *= -1.0
xyz_m[:, 2] *= -1.0

pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(xyz_m)
pcd.colors = o3d.utility.Vector3dVector(rgb.astype(np.float64) / 255.0)

extent_m = float((xyz_m.max(0) - xyz_m.min(0)).max())
voxel    = extent_m / 900.0
pcd = pcd.voxel_down_sample(voxel_size=voxel)
o3d.io.write_point_cloud('/content/scene_points.ply', pcd)
print(f"격자로 줄여 {len(pcd.points):,}점 (voxel {voxel:.4f})")

pcd.estimate_normals(
    o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 4, max_nn=30))
pcd.orient_normals_towards_camera_location(pcd.get_center())

t = time.time()
mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=10)
dens = np.asarray(dens)
print(f"포아송 {time.time()-t:.0f}초 · 삼각형 {len(mesh.triangles):,}개")

mesh.remove_vertices_by_mask(dens < np.quantile(dens, 0.06))
mesh.remove_unreferenced_vertices()
if len(mesh.triangles) > 180_000:
    mesh = mesh.simplify_quadric_decimation(180_000)
mesh.remove_degenerate_triangles()
mesh.remove_duplicated_vertices()
mesh.compute_vertex_normals()
print(f"다듬은 뒤 삼각형 {len(mesh.triangles):,}개")

m = trimesh.Trimesh(
    vertices=np.asarray(mesh.vertices),
    faces=np.asarray(mesh.triangles),
    vertex_colors=(np.asarray(mesh.vertex_colors) * 255).astype(np.uint8),
    process=False)
m.export('/content/scene_mesh.glb')
print(f"scene_mesh.glb {os.path.getsize('/content/scene_mesh.glb')/1e6:.1f}MB")
""")

# ═══════════════════════════════════════════════════════════════════
md(r"""
## 마무리 — 막혔을 때 되짚을 표

| 증상 | 원인 |
|---|---|
| 복원에서 메모리가 넘침 | `bf16` 을 쓰고 있다 → `fp16` |
| `import mapanything` 실패 | `sys.path` 를 안 끼웠다 |
| 장면이 거꾸로 섬 | `y`·`z` 부호를 안 뒤집었다 |
| 장면이 한없이 큼 | 멀리 튄 점을 안 버렸다 |
| 표면에 구멍이 숭숭 | K 가 작다. 또는 점이 너무 적다 |
| 다 뭉개짐 | K 가 크다 |
| 아치 모양으로 휘어 나옴 | 제자리에서 돌며 찍었다. 다시 찍어야 한다 |
| `.sog` 가 안 열림 | SOG v3 로 만들었다 → splat-transform 3.10.3 |
| 깃허브가 파일을 거부 | 100MiB 초과. 알갱이 수를 줄인다 |
| 각도를 틀면 검은 자리 | 안 찍힌 면이다. 그쪽을 더 찍어야 한다 |

## 더 읽을 것

- `docs/PRD.md` — 이 프로젝트가 무엇을 만족해야 하는가
- `docs/ARCHITECTURE.md` — 파일 구조와 데이터 흐름
- `docs/MEASUREMENTS.md` — 수치의 뜻과 재는 법
- `docs/LIMITATIONS.md` — 검은 얼룩과 시차·정렬의 관계
- `docs/PUBLISHING.md` — 공개 판단과 배포 절차
""")

# ═══════════════════════════════════════════════════════════════════
nb = nbf.new_notebook()
nb['cells'] = cells
nb['metadata'] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
    "accelerator": "GPU",
    "colab": {"provenance": [], "gpuType": "T4", "toc_visible": True},
}
nb['nbformat'] = 4
nb['nbformat_minor'] = 5

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'room3d.ipynb')
with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write(nbwrites(nb))
print("wrote", out, len(cells), "cells")
