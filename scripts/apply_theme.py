#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_theme.py — يتحقق من brand/THEME.json ويولّد ملفات الهوية التي تستهلكها خطوة الرسم:
  - build/theme.resolved.json  : الهوية بعد التحقق والقيم الافتراضية (يقرأها السكل والمحرّك)
  - build/caption.css          : ستايل الكابشن بألوانك وخطوطك (لمحرّك الرسم بالمتصفح)
  - build/ffmpeg_drawtext.txt   : إعدادات drawtext للمسار الخفيف (ffmpeg)

الاستخدام:
    python3 scripts/apply_theme.py brand/THEME.json
    python3 scripts/apply_theme.py brand/THEME.json --check   # تحقق فقط بلا توليد

لا يعتمد على أي مكتبة خارجية.
"""
import json
import os
import re
import sys

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
REQUIRED_COLORS = ["primary", "accent", "caption_text", "caption_bg", "hot_word"]
REQUIRED_FONTS = ["caption", "heading"]


def die(msg):
    print("✗ خطأ في THEME.json: " + msg)
    sys.exit(1)


def warn(msg):
    print("⚠ " + msg)


def load(path):
    if not os.path.exists(path):
        die(f"الملف غير موجود: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        die(f"صيغة JSON غير صحيحة (سطر {e.lineno}): {e.msg} — تأكد من الفواصل والأقواس.")


def check(theme):
    errors, warns = [], []
    colors = theme.get("colors", {})
    for k in REQUIRED_COLORS:
        v = colors.get(k, "")
        if not isinstance(v, str) or not HEX.match(v):
            errors.append(f"colors.{k} يجب أن يكون كود HEX مثل #1F3864 (القيمة الحالية: {v!r})")
    fonts = theme.get("fonts", {})
    for k in REQUIRED_FONTS:
        if not str(fonts.get(k, "")).strip():
            errors.append(f"fonts.{k} مطلوب (اسم خط مثبّت أو موجود في brand/fonts/)")
    page = theme.get("page", {})
    if not str(page.get("booking", "")).strip():
        warns.append("page.booking فارغ — لن يظهر رابط الحجز في كرت النهاية.")
    # logo / font files existence (relative to repo root = parent of scripts/)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo = theme.get("logo", {}).get("file", "")
    if logo and not os.path.exists(os.path.join(root, "brand", "logo", os.path.basename(logo))):
        warns.append(f"ملف الشعار غير موجود في brand/logo/: {logo}")
    for name, fp in theme.get("fonts", {}).get("files", {}).items():
        if name.startswith("_"):
            continue
        if fp and not os.path.exists(os.path.join(root, "brand", "fonts", os.path.basename(fp))):
            warns.append(f"ملف الخط غير موجود في brand/fonts/: {fp} (للخط {name})")
    # safe zones sanity
    sz = theme.get("safe_zones", {})
    if sz.get("bottom", 0) < theme.get("caption", {}).get("position_y", 1460) - theme.get("render", {}).get("height", 1920):
        pass
    return errors, warns


def caption_css(theme):
    c = theme["colors"]
    f = theme["fonts"]
    cap = theme.get("caption", {})
    radius = cap.get("corner_radius", 16)
    return f"""/* مولّد تلقائياً من brand/THEME.json — لا تعدّله يدوياً */
:root {{
  --primary: {c['primary']};
  --accent: {c['accent']};
  --caption-text: {c['caption_text']};
  --caption-bg: {c['caption_bg']};
  --hot: {c['hot_word']};
  --danger: {c.get('danger', '#C00000')};
  --success: {c.get('success', '#2E7D32')};
}}
.caption {{
  font-family: "{f['caption']}", "Tajawal", sans-serif;
  font-weight: {f.get('caption_weight', '800')};
  color: var(--caption-text);
  background: var(--caption-bg);
  border-radius: {radius}px;
  padding: 10px 22px;
  direction: rtl;
  text-align: center;
  line-height: 1.25;
}}
.caption .hot {{ color: var(--hot); }}
.heading {{ font-family: "{f['heading']}", "Cairo", sans-serif; color: var(--primary); }}
.number  {{ font-family: "{f.get('number', f['heading'])}", "Cairo", sans-serif; color: var(--accent); font-weight: 900; }}
.progress-bar {{ background: var(--accent); }}
"""


def ffmpeg_drawtext(theme):
    c = theme["colors"]
    cap = theme.get("caption", {})
    y = cap.get("position_y", 1460)
    # drawtext يحتاج لون بصيغة 0xRRGGBB
    def hx(v):
        return "0x" + v.lstrip("#")
    fontfile = ""
    files = theme.get("fonts", {}).get("files", {})
    cap_font = theme["fonts"]["caption"]
    if files.get(cap_font):
        fontfile = f"brand/fonts/{os.path.basename(files[cap_font])}"
    lines = [
        "# إعدادات drawtext للمسار الخفيف (scripts/make_reel.sh)",
        f"FONTFILE={fontfile}",
        f"FONTCOLOR={hx(c['caption_text'])}",
        f"BOXCOLOR={hx(c['caption_bg'])}@0.92",
        f"HOTCOLOR={hx(c['hot_word'])}",
        f"CAPTION_Y={y}",
        f"BOX_BORDER=18",
    ]
    return "\n".join(lines) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    path = args[0] if args else "brand/THEME.json"
    theme = load(path)
    errors, warns = check(theme)
    for w in warns:
        warn(w)
    if errors:
        for e in errors:
            print("✗ " + e)
        sys.exit(1)
    print("✓ THEME.json سليم.")
    if "--check" in flags:
        return
    root = os.path.dirname(os.path.dirname(os.path.abspath(path if os.path.isabs(path) else os.path.abspath(path))))
    out = os.path.join(root, "build")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "theme.resolved.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out, "caption.css"), "w", encoding="utf-8") as f:
        f.write(caption_css(theme))
    with open(os.path.join(out, "ffmpeg_drawtext.txt"), "w", encoding="utf-8") as f:
        f.write(ffmpeg_drawtext(theme))
    print(f"✓ تولّدت ملفات الهوية في build/ : theme.resolved.json · caption.css · ffmpeg_drawtext.txt")
    print(f"  الألوان: أساسي {theme['colors']['primary']} · تمييز {theme['colors']['accent']} · كلمة ساخنة {theme['colors']['hot_word']}")
    print(f"  الخطوط: كابشن {theme['fonts']['caption']} · عناوين {theme['fonts']['heading']}")


if __name__ == "__main__":
    main()
