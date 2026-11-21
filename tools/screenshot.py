# -*- coding: utf-8 -*-
"""리포트 화면 검사: 375px·1280px 캡처 + 가로 스크롤·잘림 검사.

python tools/screenshot.py <html 파일> <출력 폴더>
(Playwright + 윈도우 기본 Edge 사용, GitHub Actions에서는 chromium)
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CHECK_JS = """() => {
  const doc = document.documentElement;
  const over = [];
  document.querySelectorAll('body *').forEach(el => {
    if (el.closest('nav.tabs .wrap')) return;            // 탭 줄은 일부러 가로 스크롤
    const r = el.getBoundingClientRect();
    if (r.width && (r.right > doc.clientWidth + 1 || r.left < -1)) over.push(el.tagName + '.' + el.className + ' ' + (el.textContent||'').trim().slice(0,30));
  });
  const small = [];
  document.querySelectorAll('.summary, .title, p, li').forEach(el => {
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < 15) small.push(el.className + ' ' + fs);
  });
  return {scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth, overflow: over.slice(0,10), small: small.slice(0,5)};
}"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    html, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge")
        except Exception:
            browser = p.chromium.launch()
        ok = True
        for name, w, h, mobile in (("mobile-375", 375, 812, True), ("pc-1280", 1280, 900, False)):
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2 if mobile else 1,
                                    is_mobile=mobile, has_touch=mobile)
            page.goto(html.as_uri())
            page.wait_for_timeout(300)
            r = page.evaluate(CHECK_JS)
            page.screenshot(path=str(out / f"{name}-top.png"))
            page.screenshot(path=str(out / f"{name}-full.png"), full_page=True)
            hscroll = r["scrollWidth"] > r["clientWidth"]
            ok &= not hscroll and not r["overflow"] and not r["small"]
            print(f"[{name}] 가로스크롤 {'있음 ✗' if hscroll else '없음 ✓'} "
                  f"(scrollWidth {r['scrollWidth']} / 화면 {r['clientWidth']}), "
                  f"화면 밖으로 나간 요소 {len(r['overflow'])}개, 15px 미만 본문 {len(r['small'])}개")
            for o in r["overflow"] + r["small"]:
                print("   -", o)
            page.close()
        browser.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
