#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_safe.py — يتحقق من المناطق الآمنة لواجهة إنستغرام ويطبع فلتر ffmpeg يرسمها على إطار معاينة.

الاستخدام:
    python3 scripts/check_safe.py build/theme.resolved.json
    python3 scripts/check_safe.py build/theme.resolved.json --frame <work>/frame.png   # يرسم فعلياً لو ffmpeg موجود

لا يعتمد على مكتبات خارجية. الرسم الفعلي يحتاج ffmpeg في PATH.
"""
import json
import os
import shutil
import subprocess
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "build/theme.resolved.json"
    frame = None
    if "--frame" in sys.argv:
        i = sys.argv.index("--frame")
        if i + 1 < len(sys.argv):
            frame = sys.argv[i + 1]
    with open(path, encoding="utf-8") as f:
        t = json.load(f)
    r = t.get("render", {})
    W, H = r.get("width", 1080), r.get("height", 1920)
    sz = t.get("safe_zones", {})
    top, bot = sz.get("top", 220), sz.get("bottom", 520)
    right, left = sz.get("right", 120), sz.get("left", 60)
    cap_y = t.get("caption", {}).get("position_y", 1460)

    # تحذيرات منطقية
    warns = []
    if cap_y > H - bot:
        warns.append(f"⚠ موضع الكابشن {cap_y} داخل المنطقة السفلى الآمنة (يبدأ عند {H - bot}). ارفعه أو صغّر safe_zones.bottom.")
    if cap_y < top:
        warns.append(f"⚠ موضع الكابشن {cap_y} أعلى من المنطقة العلوية — سيُحجب بالساعة/الحساب.")
    for w in warns:
        print(w)
    if not warns:
        print(f"✓ موضع الكابشن {cap_y} خارج المناطق الآمنة (العلوية {top}، السفلية تبدأ {H - bot}).")

    # فلتر drawbox للمعاينة
    boxes = [
        f"drawbox=x=0:y=0:w={W}:h={top}:color=red@0.4:t=fill",
        f"drawbox=x=0:y={H-bot}:w={W}:h={bot}:color=red@0.4:t=fill",
        f"drawbox=x={W-right}:y=0:w={right}:h={H}:color=orange@0.4:t=fill",
        f"drawbox=x=0:y=0:w={left}:h={H}:color=orange@0.25:t=fill",
        f"drawbox=x=0:y={cap_y}:w={W}:h=6:color=lime:t=fill",
    ]
    vf = ",".join(boxes)
    print("\nفلتر المعاينة (أحمر = ممنوع، أخضر = خط الكابشن):")
    print(f"  -vf \"{vf}\"")

    if frame:
        if not shutil.which("ffmpeg"):
            print("ffmpeg غير مثبّت — تخطّيت الرسم الفعلي.")
            return
        out = os.path.splitext(frame)[0] + ".safe.png"
        subprocess.run(["ffmpeg", "-y", "-i", frame, "-vf", vf, out],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✓ حُفظت المعاينة: {out}")


if __name__ == "__main__":
    main()
