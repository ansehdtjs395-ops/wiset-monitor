# -*- coding: utf-8 -*-
"""홈 화면 아이콘 생성 (한 번만 실행해서 docs/icons/ 에 커밋).

python tools/make_icons.py [글꼴 경로]   (기본: 윈도우 맑은 고딕 굵게)
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Windows\Fonts\malgunbd.ttf"
OUT = Path(__file__).resolve().parent.parent / "docs" / "icons"
BG, FG, ACCENT = (46, 49, 146), (255, 255, 255), (255, 214, 102)


def make(size, maskable=False):
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    pad = size * (0.2 if maskable else 0.12)
    inner = size - 2 * pad
    f1 = ImageFont.truetype(FONT, int(inner * 0.30))
    f2 = ImageFont.truetype(FONT, int(inner * 0.20))
    d.text((size / 2, pad + inner * 0.36), "WISET", font=f1, fill=FG, anchor="mm")
    d.rounded_rectangle([size / 2 - inner * 0.28, pad + inner * 0.56, size / 2 + inner * 0.28, pad + inner * 0.585],
                        radius=size * 0.01, fill=ACCENT)
    d.text((size / 2, pad + inner * 0.76), "언론보도", font=f2, fill=FG, anchor="mm")
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    make(192).save(OUT / "icon-192.png")
    make(512).save(OUT / "icon-512.png")
    make(512, maskable=True).save(OUT / "icon-maskable-512.png")
    make(180).save(OUT / "apple-touch-icon.png")
    make(32).resize((32, 32)).save(OUT / "favicon-32.png")
    print("저장:", OUT)


if __name__ == "__main__":
    main()
