"""폰용으로 점을 1/3 로 줄인 파일을 만든다 (코랩에서 실행).

3,496,815개는 데스크톱에서는 문제없지만 폰 GPU 에서는 100MB 넘는 텍스처를
잡아야 한다. 1/3 로 줄이고 알갱이 반지름을 sqrt(3) 배로 키우면, 점 사이는
벌어지지 않으면서 메모리는 1/3 이 된다.

    colab exec -s room -f scripts/make_light.py --timeout 600
"""
import os
import subprocess
import numpy as np

SRC = "/content/scene.ply"
DST = "/content/scene-low.ply"
SOG = "/content/scene-low.sog"
STEP = 3          # 3,496,815 → 1,165,605
GROW = 3 ** 0.5   # 반지름을 sqrt(3) 배로

raw = open(SRC, "rb").read()
head_end = raw.index(b"end_header\n") + len(b"end_header\n")
header = raw[:head_end]
n = int([l for l in header.split(b"\n") if l.startswith(b"element vertex")][0].split()[-1])
print(f"원본 점 {n:,}")

a = np.frombuffer(raw, dtype="<f4", count=n * 17, offset=head_end).reshape(n, 17)
b = np.ascontiguousarray(a[::STEP])
b[:, 10:13] += np.log(GROW)      # scale_0..2 는 로그값이라 더하기로 곱한다

header = header.replace(f"element vertex {n}".encode(), f"element vertex {len(b)}".encode())
with open(DST, "wb") as f:
    f.write(header)
    f.write(b.tobytes())

print(f"남긴 점 {len(b):,} ({len(b)/n*100:.1f}%) · {os.path.getsize(DST)/1e6:.1f}MB")
print(f"반지름 {np.exp(b[0, 10]):.5f} (원본의 {GROW:.2f}배)")

subprocess.run(["npx", "-y", "@playcanvas/splat-transform@3.10.3", "-w", DST, SOG], check=True)
print(f"scene-low.sog {os.path.getsize(SOG):,}B ({os.path.getsize(SOG)/1e6:.2f}MB)")
print(f"알갱이당 {os.path.getsize(SOG)/len(b):.2f}B")
