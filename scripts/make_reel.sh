#!/usr/bin/env bash
# make_reel.sh — المسار الخفيف: فيديو كلام → ريل 9:16 بكابشن محروق بألوان الهوية + مقدمة/نهاية.
#
# المتطلبات:
#   - ffmpeg            (إلزامي)      قص، مقاس، صوت، كابشن، مقدمة/نهاية
#   - python3           (إلزامي)      قراءة الهوية
#   - whisper (اختياري): لتوقيت الكلمة. بدونه يُحرق نص السكريبت يدوياً عبر captions.srt
#
# الاستخدام:
#   bash scripts/make_reel.sh <input.mov> [captions.srt]
#
# ملاحظة: هذا مسار مبسّط لكابشن نظيف ومقدمة/نهاية. للموشن قرافيكس المتقدم استخدم محرّك الرسم
#          (references/engine.md). الأرقام والنصوص تأتي من سكريبت المستخدم، لا تُخترع.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IN="${1:-}"
SRT="${2:-}"
[ -z "$IN" ] && { echo "الاستخدام: bash scripts/make_reel.sh <input.mov> [captions.srt]"; exit 1; }
[ -f "$IN" ] || { echo "الملف غير موجود: $IN"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg غير مثبّت. ثبّته أولاً."; exit 1; }

# 1) طبّق الهوية
python3 "$ROOT/scripts/apply_theme.py" "$ROOT/brand/THEME.json"
DT="$ROOT/build/ffmpeg_drawtext.txt"
# shellcheck disable=SC1090
FONTCOLOR=$(grep '^FONTCOLOR=' "$DT" | cut -d= -f2)
BOXCOLOR=$(grep '^BOXCOLOR=' "$DT" | cut -d= -f2)
CAPTION_Y=$(grep '^CAPTION_Y=' "$DT" | cut -d= -f2)
FONTFILE=$(grep '^FONTFILE=' "$DT" | cut -d= -f2-)
TARGET_LUFS=$(python3 -c "import json;print(json.load(open('$ROOT/brand/THEME.json'))['audio']['target_lufs'])")

WORK="$(mktemp -d)"
echo "مجلد العمل المؤقت: $WORK"

# 2) قص السكتات الطويلة (الصمت > 0.45 ث، عتبة -30dB)، وتطبيع المقاس إلى 1080x1920
#    (ملاحظة: silenceremove يقصّ الصمت؛ لإبقاء سكوت «لأ.» المتعمّد استخدم محرّك الرسم بدل هذا المسار)
ffmpeg -y -i "$IN" \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30" \
  -af "silenceremove=stop_periods=-1:stop_duration=0.45:stop_threshold=-30dB,loudnorm=I=${TARGET_LUFS}:TP=-1.5:LRA=11" \
  -c:v libx264 -preset medium -crf 18 -c:a aac -b:a 192k \
  "$WORK/cut.mp4"

# 3) الكابشن
VF_CAP=""
if [ -n "$SRT" ] && [ -f "$SRT" ]; then
  FF=""
  [ -n "$FONTFILE" ] && [ -f "$ROOT/$FONTFILE" ] && FF=":force_style='FontName=caption,Fontfile=$ROOT/$FONTFILE'"
  VF_CAP="subtitles='$SRT':force_style='PrimaryColour=&H00FFFFFF,BackColour=${BOXCOLOR//0x/&H},BorderStyle=4,MarginV=60'"
elif command -v whisper >/dev/null; then
  echo "أفرّغ الكلام بتوقيت الكلمة عبر whisper…"
  whisper "$WORK/cut.mp4" --language ar --model medium --output_format srt --output_dir "$WORK" >/dev/null 2>&1 || true
  AUTO_SRT="$WORK/cut.srt"
  [ -f "$AUTO_SRT" ] && VF_CAP="subtitles='$AUTO_SRT':force_style='PrimaryColour=&H00FFFFFF,BorderStyle=4,MarginV=60'"
else
  echo "⚠ لا whisper ولا ملف SRT — سأصدّر بلا كابشن محروق. مرّر captions.srt أو ثبّت whisper."
fi

OUT="$ROOT/build/reel_$(date +%s).mp4"
if [ -n "$VF_CAP" ]; then
  ffmpeg -y -i "$WORK/cut.mp4" -vf "$VF_CAP" -c:v libx264 -preset medium -crf 18 -c:a copy "$WORK/capped.mp4"
else
  cp "$WORK/cut.mp4" "$WORK/capped.mp4"
fi

# 4) المقدمة والنهاية من الهوية (كروت ملوّنة)
python3 - "$ROOT" "$WORK" <<'PY'
import json, os, subprocess, sys
root, work = sys.argv[1], sys.argv[2]
t = json.load(open(os.path.join(root, "brand", "THEME.json"), encoding="utf-8"))
W, H = 1080, 1920
def card(name, dur, bg, texts):
    # texts: list of (text, y, size, color)
    draws = []
    for txt, y, size, color in texts:
        safe = txt.replace(":", r"\:").replace("'", "")
        draws.append(f"drawtext=text='{safe}':x=(w-text_w)/2:y={y}:fontsize={size}:fontcolor={color}:box=0")
    vf = ",".join(draws) if draws else "null"
    out = os.path.join(work, name)
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c={bg}:s={W}x{H}:d={dur}",
                    "-vf", vf, "-r","30", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out
made = []
intro = t.get("intro", {})
if intro.get("enabled"):
    made.append(("intro", card("intro.mp4", intro.get("duration",1.5), intro.get("bg","#1F3864").lstrip("#"),
        [(intro.get("text",""), H//2-40, 70, "white")])))
outro = t.get("outro", {})
if outro.get("enabled"):
    made.append(("outro", card("outro.mp4", outro.get("duration",3.0), outro.get("bg","#1F3864").lstrip("#"),
        [(outro.get("headline",""), H//2-140, 64, "white"),
         (outro.get("subline",""), H//2, 48, outro.get("accent","#E8B23A").lstrip("#")),
         (outro.get("handle",""), H//2+120, 44, "white")])))
open(os.path.join(work, "cards.txt"), "w").write("\n".join(k for k,_ in made))
print("كروت:", [k for k,_ in made])
PY

# 5) الدمج: مقدمة + الفيديو + نهاية (إن وُجدت)
LIST="$WORK/concat.txt"
: > "$LIST"
[ -f "$WORK/intro.mp4" ] && echo "file '$WORK/intro.mp4'" >> "$LIST"
echo "file '$WORK/capped.mp4'" >> "$LIST"
[ -f "$WORK/outro.mp4" ] && echo "file '$WORK/outro.mp4'" >> "$LIST"
# توحيد الترميز قبل الدمج
while read -r line; do
  f=$(echo "$line" | sed "s/file '//;s/'//")
  ffmpeg -y -i "$f" -vf "scale=1080:1920,fps=30,format=yuv420p" -c:v libx264 -crf 18 -c:a aac -ar 48000 -b:a 192k "${f%.mp4}.norm.mp4" >/dev/null 2>&1
  sed -i "s|$f|${f%.mp4}.norm.mp4|" "$LIST"
done < "$LIST"
ffmpeg -y -f concat -safe 0 -i "$LIST" -c copy "$OUT"

echo "✓ الريل جاهز: $OUT"
echo "  افتحه وعاينه قبل النشر. للموشن المتقدم (أرقام متحركة، عمق خلف الرأس) استخدم محرّك الرسم."
