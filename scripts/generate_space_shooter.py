#!/usr/bin/env python3
"""Generate a looping pixel-art shooter over real public GitHub contributions."""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import random
import re
import sys

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

USERNAME = "kishore8807"
WIDTH, HEIGHT = 1000, 360
CELL, GAP = 12, 3
GRID_X, GRID_Y = 116, 92
BG = (13, 17, 23)
TEXT = (201, 209, 217)
MUTED = (139, 148, 158)
LEVELS = [(22, 27, 34), (14, 68, 41), (0, 109, 50), (38, 166, 65), (57, 211, 83)]
OUT = Path("assets/space-shooter.gif")


def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def get_contributions():
    end = date.today()
    start = end - timedelta(days=363)
    url = f"https://github.com/users/{USERNAME}/contributions"
    response = requests.get(
        url, params={"from": start.isoformat(), "to": end.isoformat()},
        headers={"User-Agent": "kishore8807-space-shooter/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    cells = {}
    for rect in soup.select("rect[data-date]"):
        day = rect.get("data-date")
        count = rect.get("data-count")
        level = rect.get("data-level")
        if day and count is not None:
            try:
                cells[date.fromisoformat(day)] = (int(count), max(0, min(4, int(level or 0))))
            except ValueError:
                continue
    if len(cells) < 300:
        raise RuntimeError(
            f"Could not read enough real contribution cells (found {len(cells)}). "
            "GitHub may have changed its page markup; refusing to generate a fake graph."
        )
    return start, end, cells


def draw_ship(draw, cx, y):
    # Small vertical pixel-art spaceship pointing upward.
    draw.polygon([(cx, y), (cx - 9, y + 14), (cx - 6, y + 22),
                  (cx + 6, y + 22), (cx + 9, y + 14)], fill=(230, 237, 243))
    draw.rectangle((cx - 3, y + 8, cx + 3, y + 15), fill=(88, 166, 255))
    draw.rectangle((cx - 5, y + 18, cx - 2, y + 23), fill=(255, 166, 87))
    draw.rectangle((cx + 2, y + 18, cx + 5, y + 23), fill=(255, 166, 87))


def main():
    start, end, contributions = get_contributions()
    # Align the first column to Sunday, like GitHub's contribution calendar.
    first_sunday = start - timedelta(days=(start.weekday() + 1) % 7)
    last_saturday = end + timedelta(days=(5 - end.weekday()) % 7 + 1)
    weeks = []
    cursor = first_sunday
    while cursor <= last_saturday:
        weeks.append([cursor + timedelta(days=i) for i in range(7)])
        cursor += timedelta(days=7)

    grid_width = len(weeks) * (CELL + GAP) - GAP
    x0 = (WIDTH - grid_width) // 2
    y0 = GRID_Y
    cell_xy = {}
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week):
            if day < start or day > end:
                continue
            cell_xy[day] = (x0 + wi * (CELL + GAP), y0 + di * (CELL + GAP))

    targets = [
        (day, contributions.get(day, (0, 0))[0], xy)
        for day, xy in cell_xy.items()
        if contributions.get(day, (0, 0))[0] > 0
    ]
    if not targets:
        raise RuntimeError("No contribution squares with activity were found; no animation generated.")
    # Spread targets across the calendar so the animation showcases multiple real cells.
    targets.sort(key=lambda item: item[0])
    count = min(7, len(targets))
    targets = [targets[round(i * (len(targets) - 1) / max(1, count - 1))] for i in range(count)]

    base = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(base)
    d.text((40, 22), f"{USERNAME}  /  CONTRIBUTION SPACE SHOOTER", font=font(17, True), fill=TEXT)
    d.text((40, 49), f"Real contribution activity  •  {start.isoformat()} — {end.isoformat()}",
           font=font(11), fill=MUTED)

    # Weekday labels, month labels, and the original contribution-cell grid.
    for label, row in [("Mon", 1), ("Wed", 3), ("Fri", 5)]:
        d.text((x0 - 38, y0 + row * (CELL + GAP) - 1), label, font=font(9), fill=MUTED)
    month_seen = set()
    for wi, week in enumerate(weeks):
        for day in week:
            if day.month not in month_seen and day >= start and day <= end and day.day <= 7:
                d.text((x0 + wi * (CELL + GAP), y0 - 23), day.strftime("%b"),
                       font=font(10), fill=MUTED)
                month_seen.add(day.month)
                break
        for di, day in enumerate(week):
            if day not in cell_xy:
                continue
            _, level = contributions.get(day, (0, 0))
            x, y = cell_xy[day]
            d.rounded_rectangle((x, y, x + CELL, y + CELL), radius=2, fill=LEVELS[level])

    # Simple movement/laser/explosion loop. Cell values are only visually covered in frames;
    # the real contribution data is never changed.
    frames = []
    ship_y = HEIGHT - 50
    current_x = x0
    rng = random.Random(8807)
    for _, _, (tx, ty) in targets:
        target_x = tx + CELL // 2
        # Move the ship horizontally toward the selected green cell.
        move_frames = 7
        for f in range(move_frames):
            t = (f + 1) / move_frames
            sx = round(current_x + (target_x - current_x) * t)
            frame = base.copy()
            fd = ImageDraw.Draw(frame)
            draw_ship(fd, sx, ship_y)
            frames.append(frame)
        current_x = target_x

        # Laser travel frames.
        for f in range(5):
            frame = base.copy()
            fd = ImageDraw.Draw(frame)
            laser_bottom = ship_y
            laser_top = laser_bottom - round((laser_bottom - (ty + CELL // 2)) * (f + 1) / 5)
            fd.line((current_x, laser_bottom, current_x, laser_top), fill=(88, 166, 255), width=3)
            fd.line((current_x, laser_bottom, current_x, laser_top), fill=(230, 237, 243), width=1)
            draw_ship(fd, current_x, ship_y)
            frames.append(frame)

        # Pixel explosion over the actual target square.
        for f in range(6):
            frame = base.copy()
            fd = ImageDraw.Draw(frame)
            radius = 3 + f * 2
            cx, cy = tx + CELL // 2, ty + CELL // 2
            fd.rectangle((tx, ty, tx + CELL, ty + CELL), fill=BG)
            for _ in range(12):
                px = cx + rng.randint(-radius, radius)
                py = cy + rng.randint(-radius, radius)
                colour = rng.choice([(57, 211, 83), (166, 255, 191), (255, 214, 102)])
                fd.rectangle((px, py, px + 2, py + 2), fill=colour)
            draw_ship(fd, current_x, ship_y)
            frames.append(frame)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=65,
                   loop=0, optimize=True, disposal=2)
    print(f"Generated {OUT} using {len(contributions)} real contribution dates and {len(targets)} targets.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
