#!/usr/bin/env python3
"""코랩에서 room3d.ipynb 를 무인으로 실행한다.

노트북은 사람이 읽고 돌리는 물건이라 `files.upload()` 처럼 손이 필요한 셀이 있다.
이 스크립트는 그 셀만 대체하고, 나머지는 **노트북에 적힌 그대로** 실행한다.
.ipynb 를 읽어 코드 셀을 순서대로 exec 하므로, 노트북을 고치면 이 실행도 같이 바뀐다.

코랩에서:  colab exec -s room -f /content/run_notebook.py --timeout 3000
"""
import json, os, subprocess, sys, time

# ── 손이 필요한 두 곳만 대체한다 ────────────────────────────────────
import google.colab.files as _files

def _upload(*a, **k):
    print("[대체] files.upload() → 이미 올려 둔 watch.mp4 를 쓴다")
    return {"watch.mp4": open("/content/watch.mp4", "rb").read()}

def _download(path, *a, **k):
    if os.path.exists(path):
        print(f"[대체] files.download({path}) → {os.path.getsize(path)/1e6:.1f}MB, 내려받기는 나중에")
    else:
        print(f"[대체] files.download({path}) → 파일 없음!")

_files.upload = _upload
_files.download = _download

# 그림은 파일로 안 띄우고 넘어간다
import matplotlib
matplotlib.use("Agg")

NB = "/content/room3d.ipynb"
nb = json.load(open(NB, encoding="utf-8"))
print(f"노트북 셀 {len(nb['cells'])}개 · {NB}")


def transform(src: str) -> str:
    """IPython 전용 문법을 평범한 파이썬으로 바꾼다."""
    out = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("%%"):            # %%capture 등 셀 매직
            continue
        if s.startswith("!"):             # !셸명령
            cmd = s[1:].strip()
            out.append(f"subprocess.run({cmd!r}, shell=True, check=True)")
            continue
        out.append(line)
    return "\n".join(out)


G = {"__name__": "__main__", "subprocess": subprocess}
T0 = time.time()
failed = []

for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] != "code":
        continue
    src = transform("".join(cell["source"]))
    if not src.strip():
        continue
    if "create_from_point_cloud_poisson" in src:
        print(f"\n[셀 {i}] 부록(메시)은 이번 제출에 쓰지 않으므로 건너뛴다", flush=True)
        continue
    print(f"\n{'='*66}\n[셀 {i}] ({time.time()-T0:.0f}초 경과)\n{'='*66}", flush=True)
    try:
        exec(compile(src, f"<cell {i}>", "exec"), G)
    except Exception as e:
        failed.append((i, e))
        print(f"\n!!! 셀 {i} 실패: {type(e).__name__}: {e}", flush=True)
        raise

print(f"\n\n전체 {time.time()-T0:.0f}초")

# ── 마지막 확인 ─────────────────────────────────────────────────────
for name in ("scene.sog", "scene.ply", "measurements.json"):
    p = f"/content/{name}"
    print(f"  {name:<20} {'있음 ' + str(round(os.path.getsize(p)/1e6, 2)) + 'MB' if os.path.exists(p) else '없음'}")
