#!/bin/sh
# Regenerate the README media in docs/images (demo.gif, folie.jpg, agenda.png, dienstplan.png).
#
# Runs the app from source against fake_churchtools.py (invented sample data) with a throwaway
# database, drives it with Playwright (capture.py) and builds the GIF with ffmpeg.
# Needs: ffmpeg, ImageMagick (magick), poppler (pdftoppm), uv, and the project .venv (mise run install).
#
# Usage: mise run readme-media
set -eu

cd "$(dirname "$0")/../.."
REPO=$(pwd)
HERE="$REPO/scripts/readme_media"
OUT="$REPO/docs/images"
CT_PORT="${FAKE_CT_PORT:-5900}"
APP_PORT="${APP_PORT:-5905}"
APP_URL="http://127.0.0.1:$APP_PORT"

for tool in ffmpeg ffprobe magick pdftoppm uv; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Missing tool: $tool" >&2; exit 1; }
done

WORK=$(mktemp -d)
PIDS=""
cleanup() {
    for pid in $PIDS; do kill "$pid" 2>/dev/null || true; done
    rm -rf "$WORK"
}
trap cleanup EXIT

echo "Creating background image and placeholder logo"
magick -size 1920x1080 -define gradient:direction=east gradient:'#1f3b33'-'#6b8f71' \
    \( -size 1920x1080 radial-gradient:'#f2d49b'-none -alpha set -channel A -evaluate multiply 0.55 +channel \
       -geometry +700-300 \) -compose over -composite -quality 90 "$WORK/bg.jpg"
magick -size 860x200 xc:none -fill white -draw "rectangle 60,30 78,170" -draw "rectangle 24,70 114,88" \
    -font "$REPO/app/resources/fonts/Bahnschrift.ttf" -pointsize 52 -annotate +150+92 "Ev. Kirchengemeinde" \
    -pointsize 40 -fill '#ffffffcc' -annotate +150+148 "Musterstadt" -trim +repage -bordercolor none -border 10 \
    "$WORK/logo.png"

echo "Starting fake ChurchTools on :$CT_PORT and the app on :$APP_PORT"
.venv/bin/uvicorn --app-dir "$HERE" fake_churchtools:app --port "$CT_PORT" --log-level warning &
PIDS="$PIDS $!"
export DB_PATH="$WORK/demo.db" CHURCHTOOLS_BASE=demo.invalid CHURCHTOOLS_BASE_URL="http://127.0.0.1:$CT_PORT"
export ALLOWED_GROUP_IDS="" ALLOWED_PERSON_IDS="" TIMEZONE=Europe/Berlin
.venv/bin/alembic upgrade head >/dev/null 2>&1
.venv/bin/uvicorn app.main:app --port "$APP_PORT" --log-level warning &
PIDS="$PIDS $!"
i=0
until curl -sf "$APP_URL/health" >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -lt 30 ] || { echo "App did not start" >&2; exit 1; }
    sleep 1
done

echo "Recording with Playwright"
uv run --no-project --with playwright playwright install chromium >/dev/null
uv run --no-project --with playwright python "$HERE/capture.py" "$WORK" "$APP_URL"

echo "Building demo.gif"
VIDEO=$(ls "$WORK"/video/*.webm)
SKIP=1.2      # idle start of the recording
SPEED=1.15
FPS=10
WIDTH=580
HEIGHT=820
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
FADE_AT=$(echo "($DURATION - $SKIP) / $SPEED - 0.7" | bc -l)
# End frame: the exported slide on the page background
pdftoppm -r 110 -png -f 1 -l 1 -singlefile "$WORK/demo.pdf" "$WORK/end_slide"
magick "$WORK/end_slide.png" -resize "$((WIDTH - 32))x" -background '#F2F3EE' -gravity center \
    -extent "${WIDTH}x${HEIGHT}" "$WORK/end.png"
ffmpeg -v error -y -ss "$SKIP" -i "$VIDEO" -loop 1 -t 3.5 -i "$WORK/end.png" -filter_complex \
    "[0:v]setpts=PTS/$SPEED,fps=$FPS,format=yuv420p[a];[1:v]fps=$FPS,format=yuv420p[b];\
[a][b]xfade=transition=fade:duration=0.5:offset=$FADE_AT[v];[v]split[s0][s1];\
[s0]palettegen=max_colors=128:stats_mode=full[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
    "$OUT/demo.gif"

echo "Writing folie.jpg, agenda.png, dienstplan.png"
pdftoppm -jpeg -jpegopt quality=92 -f 1 -l 1 -singlefile -scale-to-x 1600 -scale-to-y -1 "$WORK/demo.pdf" "$WORK/folie"
cp "$WORK/folie.jpg" "$OUT/folie.jpg"
for image in agenda dienstplan; do
    magick "$WORK/$image.png" -strip -define png:compression-level=9 "$OUT/$image.png"
done

ls -l "$OUT"
