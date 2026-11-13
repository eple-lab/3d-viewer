"""캡처한 원본에서 README·문서에 넣을 그림을 만든다.

    uv run --with pillow python scripts/make_figures.py

shots/_raw/ 에 있는 각도별 렌더를 잘라 붙여서
    shots/viewer.jpg     대표 화면
    shots/coverage.jpg   앞에서는 보이고 뒤에서는 사라지는 비교
를 만든다. 라벨은 맑은 고딕으로 그린다.
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "shots")
RAW = os.path.join(SHOTS, "_raw")

BG = (11, 15, 20)
FG = (226, 232, 240)
DIM = (148, 163, 184)
ACC = (125, 211, 252)
BAD = (252, 165, 165)

FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"


def font(size, bold=False):
    for p in ((FONT_B if bold else FONT), FONT):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load(name):
    return Image.open(os.path.join(RAW, name)).convert("RGB")


def content_crop(im, margin=24):
    """배경색과 다른 화소만 남기고 잘라 낸다. 장면이 작게 잡혀도 크게 보이게."""
    bg = Image.new("RGB", im.size, BG)
    from PIL import ImageChops
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 10 else 0)
    box = diff.getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - margin), max(0, y0 - margin),
                    min(im.size[0], x1 + margin), min(im.size[1], y1 + margin)))


def main():
    os.makedirs(SHOTS, exist_ok=True)

    # ── 대표 화면 ────────────────────────────────────────────────
    # live060 은 배포된 주소(https://eple-lab.github.io/3d-viewer/)에서 찍은 것이다.
    hero = content_crop(load("live060.jpg"), 40)
    hero.thumbnail((1200, 900), Image.LANCZOS)
    hero.save(os.path.join(SHOTS, "viewer.jpg"), quality=90, optimize=True)
    print("viewer.jpg", hero.size)

    # ── 앞 / 뒤 비교 ─────────────────────────────────────────────
    if not (os.path.exists(os.path.join(RAW, "h060.jpg")) and
            os.path.exists(os.path.join(RAW, "b135.jpg"))):
        print("coverage.jpg 는 _raw 에 h060/b135 가 있어야 다시 만든다 (건너뜀)")
        return

    # 같은 카메라 거리로 찍었으므로 같은 사각형을 잘라야 자리가 맞는다.
    box = (0.06, 0.03, 0.82, 0.97)

    def same_crop(im):
        w, h = im.size
        return im.crop((int(w * box[0]), int(h * box[1]),
                        int(w * box[2]), int(h * box[3])))

    front = same_crop(load("h060.jpg"))
    back = same_crop(load("b135.jpg"))

    cell_h = 620
    front = front.resize((int(front.size[0] * cell_h / front.size[1]), cell_h), Image.LANCZOS)
    back = back.resize((int(back.size[0] * cell_h / back.size[1]), cell_h), Image.LANCZOS)

    pad, top, bottom = 22, 52, 74
    width = pad * 3 + front.size[0] + back.size[0]
    sheet = Image.new("RGB", (width, cell_h + top + bottom), BG)
    x1, x2 = pad, pad * 2 + front.size[0]
    sheet.paste(front, (x1, top))
    sheet.paste(back, (x2, top))

    d = ImageDraw.Draw(sheet)
    d.text((x1, 16), "앞에서 (시계 정면)", font=font(24, True), fill=FG)
    d.text((x2, 16), "135° 돌려서 (반대편)", font=font(24, True), fill=BAD)
    d.text((x1, top + cell_h + 12), "시계·매트·나무 책상이 모두 보인다",
           font=font(19), fill=DIM)
    d.text((x2, top + cell_h + 12), "매트 조각만 남고 시계는 사라진다",
           font=font(19), fill=BAD)
    d.text((x1, top + cell_h + 38),
           "24장 · 카메라 퍼짐 4.32 / 장면 대각선 3.97", font=font(17), fill=ACC)
    d.text((x2, top + cell_h + 38),
           "→ 그 면을 본 프레임이 0장이라 깊이를 못 만든다", font=font(17), fill=BAD)
    sheet.save(os.path.join(SHOTS, "coverage.jpg"), quality=90, optimize=True)
    print("coverage.jpg", sheet.size)


if __name__ == "__main__":
    main()
