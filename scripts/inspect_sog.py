#!/usr/bin/env python3
"""scene.sog 를 열어 알갱이 수와 바이트를 검사한다.

웹에서 받은 파일이 진짜인지, README 의 수치가 맞는지 확인할 때 쓴다.

    uv run --with pillow python scripts/inspect_sog.py scene.sog

.sog 는 zip 이다. 안에 meta.json 과 webp 텍스처가 들어 있다.
위치·회전·크기·색을 각각 텍스처에 담고, meta.json 에 개수와 범위를 적는다.
"""
import json
import os
import sys
import zipfile


def main(path: str) -> int:
    if not os.path.exists(path):
        print(f"파일이 없습니다: {path}")
        return 1

    size = os.path.getsize(path)
    print(f"파일      {path}")
    print(f"크기      {size:,} B  ({size/1e6:.2f} MB / {size/1048576:.2f} MiB)")
    print(f"100MiB    {'통과' if size < 100*1048576 else '초과 — 깃허브가 거부한다'}")

    if not zipfile.is_zipfile(path):
        print("\nzip 이 아닙니다. SOG 가 아니라 다른 형식일 수 있습니다.")
        print("앞 16바이트:", open(path, 'rb').read(16))
        return 1

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        print(f"\n들어 있는 파일 {len(names)}개")
        for n in sorted(names):
            print(f"  {n:<24}{z.getinfo(n).file_size:>10,} B")

        if "meta.json" not in names:
            print("\nmeta.json 이 없습니다. SOG v2 가 아닐 수 있다.")
            return 1

        meta = json.loads(z.read("meta.json"))
        count = meta.get("count")
        if count is None:
            for key in ("means", "splats", "positions"):
                if isinstance(meta.get(key), dict) and "count" in meta[key]:
                    count = meta[key]["count"]
                    break

        print(f"\nmeta.json 키: {sorted(meta.keys())}")
        if count:
            print(f"\n알갱이 수        {count:,}")
            print(f"알갱이당 바이트   {size/count:.2f} B")
            print(f"  (.ply 였다면   {count*68/1e6:.1f} MB — 68B/개 기준)")
            print(f"  압축 배수      {count*68/size:.1f}배")
        else:
            print("\nmeta.json 에서 count 를 못 찾았습니다. 키를 직접 보십시오.")
        print(f"\n버전      {meta.get('version', '?')}")
        for k in ("means", "scales", "quaternions", "sh0", "opacity"):
            if k in meta and isinstance(meta[k], dict):
                shp = meta[k].get("shape")
                print(f"  {k:<12} shape={shp}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
