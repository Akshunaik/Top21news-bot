import os
import requests
import feedparser
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import textwrap
import json
import time
import base64

# ── ENV ───────────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_ACCOUNT_ID   = os.environ.get("IG_ACCOUNT_ID", "")
IMGBB_API_KEY   = os.environ.get("IMGBB_API_KEY", "")

# ── CATEGORIES (21 stories total) ────────────────────────────────────────────
CATEGORIES = [
    {"name": "Technology",    "query": "technology+AI",      "count": 6, "color": "#00D4FF"},
    {"name": "Business",      "query": "business+economy",   "count": 5, "color": "#00FF88"},
    {"name": "Politics",      "query": "world+politics",     "count": 4, "color": "#FF6B35"},
    {"name": "Science",       "query": "science+health",     "count": 3, "color": "#B66DFF"},
    {"name": "Entertainment", "query": "entertainment",      "count": 2, "color": "#FFD700"},
    {"name": "Sports",        "query": "sports",             "count": 1, "color": "#FF4081"},
]

# ── DESIGN CONSTANTS ──────────────────────────────────────────────────────────
BG_COLOR     = "#0D1B2A"   # Navy dark blue
ACCENT_COLOR = "#00D4FF"   # Cyan accent
W, H         = 1080, 1080

# ── HELPERS ───────────────────────────────────────────────────────────────────
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def load_font(size, bold=False):
    """Try system fonts on Ubuntu runner, fallback to PIL default."""
    paths = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ] if bold else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    )
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

# ── NEWS FETCHING ─────────────────────────────────────────────────────────────
def fetch_news(query, count):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[: count * 3]:
        articles.append({
            "title":   entry.title,
            "summary": entry.get("summary", "")[:300],
        })
    return articles

# ── AI SUMMARIZE ──────────────────────────────────────────────────────────────
def ai_summarize(articles, category, count):
    headlines = "\n".join([f"{i+1}. {a['title']}" for i, a in enumerate(articles)])
    prompt = f"""You are a news editor for Instagram account @Top21News.
From these {category} headlines, pick the {count} most interesting ones.
For each, write a punchy 1-sentence Instagram caption (max 150 chars) and 5 relevant hashtags.

Headlines:
{headlines}

Respond ONLY in this exact JSON format with no extra text and no markdown backticks:
[
  {{
    "headline": "original headline here",
    "caption": "your punchy caption here",
    "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5"
  }}
]"""

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
    )
    result = response.json()
    if "error" in result:
        raise Exception(f"{result['error']['code']} {result['error']['message']}")
    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

# ── IMAGE CREATION ────────────────────────────────────────────────────────────
def create_cover_image(part_num, total_parts, story_start, story_end):
    """Navy blue cover card: big '21 NEWS STORIES' with part info."""
    img  = Image.new("RGB", (W, H), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    bg_r, bg_g, bg_b = hex_to_rgb(BG_COLOR)

    # Top cyan accent line
    draw.rectangle([0, 0, W, 8], fill=ACCENT_COLOR)

    # @Top21News — top left
    f_handle = load_font(36)
    draw.text((50, 45), "@Top21News", fill="#FFFFFF", font=f_handle)

    # Bookmark icon — top right (two rectangles simulate icon)
    bx1, by1, bx2, by2 = W - 85, 32, W - 52, 74
    draw.rectangle([bx1, by1, bx2, by2], outline="#FFFFFF", width=2)
    draw.polygon([(bx1, by2), (bx1 + (bx2 - bx1) // 2, by2 - 14), (bx2, by2)],
                 fill=(bg_r, bg_g, bg_b))

    # Subtle horizontal rule below header
    draw.line([(50, 95), (W - 50, 95)], fill="#1E3048", width=1)

    # Giant "21"
    f_huge = load_font(300, bold=True)
    draw.text((W // 2, H // 2 - 90), "21", fill="#FFFFFF", font=f_huge, anchor="mm")

    # "NEWS STORIES"
    f_title = load_font(74, bold=True)
    draw.text((W // 2, H // 2 + 125), "NEWS STORIES", fill="#FFFFFF", font=f_title, anchor="mm")

    # Part info
    f_part = load_font(38)
    part_text = f"PART {part_num} OF {total_parts}   ·   STORIES {story_start} \u2013 {story_end}"
    draw.text((W // 2, H // 2 + 210), part_text, fill=ACCENT_COLOR, font=f_part, anchor="mm")

    # Tagline
    f_tag = load_font(30)
    draw.text((W // 2, H // 2 + 275), "Subscribe to more \u2193", fill="#4A6A8A", font=f_tag, anchor="mm")

    # Bottom date
    f_date = load_font(28)
    draw.text((W // 2, H - 42), datetime.now().strftime("%B %d, %Y"), fill="#2A3A4A", font=f_date, anchor="mm")

    filename = f"cover_{part_num}.png"
    img.save(filename)
    return filename


def create_story_image(headline, caption, category, color, index):
    """Navy blue story card matching the approved design."""
    img  = Image.new("RGB", (W, H), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    r, g, b = hex_to_rgb(color)

    # Top category-color accent line
    draw.rectangle([0, 0, W, 8], fill=(r, g, b))

    # Category pill — top left
    f_cat  = load_font(28, bold=True)
    f_hdl  = load_font(28)
    cat_w  = len(category) * 15 + 40
    draw.rectangle([40, 32, 40 + cat_w, 76], outline=(r, g, b), width=2)
    draw.text((55, 54), f"#{category.upper()}", fill=(r, g, b), font=f_cat, anchor="lm")

    # @Top21News — top right
    draw.text((W - 55, 54), "@Top21News", fill="#FFFFFF", font=f_hdl, anchor="rm")

    # Subtle rule
    draw.line([(50, 95), (W - 50, 95)], fill="#1E3048", width=1)

    # Headline — smaller font, more lines, wider wrap
    f_headline = load_font(42, bold=True)
    wrapped = textwrap.wrap(headline, width=30)[:6]
    y = 180
    for line in wrapped:
        draw.text((W // 2, y), line, fill="#FFFFFF", font=f_headline, anchor="mm")
        y += 62

    # Divider line
    draw.line([(80, y + 22), (W - 80, y + 22)], fill=(r, g, b), width=2)

    # Caption — longer, more lines, brighter
    f_caption = load_font(34)
    wrapped_cap = textwrap.wrap(caption, width=52)[:5]
    y += 56
    for line in wrapped_cap:
        draw.text((W // 2, y), line, fill="#8AACCC", font=f_caption, anchor="mm")
        y += 46

    # Story number badge — bottom right
    f_num = load_font(34, bold=True)
    draw.ellipse([W - 112, H - 112, W - 42, H - 42], outline=(r, g, b), width=2)
    draw.text((W - 77, H - 77), str(index), fill=(r, g, b), font=f_num, anchor="mm")

    # Bottom accent bar
    draw.rectangle([0, H - 10, W, H], fill=(r, g, b))

    # Date
    f_date = load_font(28)
    draw.text((W // 2, H - 35), datetime.now().strftime("%B %d, %Y"), fill="#2A3A4A", font=f_date, anchor="mm")

    filename = f"story_{index:02d}.png"
    img.save(filename)
    return filename

# ── UPLOAD ────────────────────────────────────────────────────────────────────
def upload_image(filepath):
    with open(filepath, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": img_data},
    )
    return response.json()["data"]["url"]

# ── INSTAGRAM CAROUSEL POST ───────────────────────────────────────────────────
def post_carousel(image_urls, caption):
    if not IG_ACCESS_TOKEN:
        print("  [SKIP] Instagram not configured.")
        return True

    # Step 1 — individual carousel item containers
    container_ids = []
    for i, url in enumerate(image_urls):
        print(f"    Creating container {i+1}/{len(image_urls)}...")
        r = requests.post(
            f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media",
            data={
                "image_url":         url,
                "is_carousel_item":  "true",
                "access_token":      IG_ACCESS_TOKEN,
            },
        )
        result = r.json()
        if "id" not in result:
            print(f"    [ERROR] Container failed: {result}")
            return False
        container_ids.append(result["id"])
        time.sleep(3)

    # Step 2 — carousel container
    print(f"    Creating carousel ({len(container_ids)} items)...")
    r = requests.post(
        f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media",
        data={
            "media_type":   "CAROUSEL",
            "children":     ",".join(container_ids),
            "caption":      caption,
            "access_token": IG_ACCESS_TOKEN,
        },
    )
    result = r.json()
    if "id" not in result:
        print(f"    [ERROR] Carousel container failed: {result}")
        return False
    carousel_id = result["id"]
    time.sleep(8)

    # Step 3 — publish
    print(f"    Publishing carousel...")
    r2 = requests.post(
        f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media_publish",
        data={"creation_id": carousel_id, "access_token": IG_ACCESS_TOKEN},
    )
    result = r2.json()
    if "id" in result:
        print(f"    ✅ Published! Carousel ID: {result['id']}")
        return True
    print(f"    [ERROR] Publish failed: {result}")
    return False

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Top21News Bot starting {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # ── 1. Collect all 21 stories ──
    all_posts = []
    for category in CATEGORIES:
        print(f"Fetching {category['name']} news...")
        articles = fetch_news(category["query"], category["count"])
        print(f"  Found {len(articles)} raw articles")
        try:
            posts = ai_summarize(articles, category["name"], category["count"])
            for post in posts:
                post["category"] = category["name"]
                post["color"]    = category["color"]
            all_posts.extend(posts)
            print(f"  Summarised {len(posts)} stories")
        except Exception as e:
            print(f"  AI failed: {e}")

    # Trim to exactly 21
    all_posts = all_posts[:21]
    print(f"\nTotal stories collected: {len(all_posts)}")

    if len(all_posts) == 0:
        print("No stories collected. Exiting.")
        return

    # ── 2. Interleave by category so each carousel gets a mix ──
    from collections import defaultdict
    buckets = defaultdict(list)
    for post in all_posts:
        buckets[post["category"]].append(post)

    # Round-robin: pick one story from each category in turn
    mixed = []
    bucket_lists = list(buckets.values())
    max_len = max(len(b) for b in bucket_lists)
    for i in range(max_len):
        for bucket in bucket_lists:
            if i < len(bucket):
                mixed.append(bucket[i])
    all_posts = mixed[:21]
    print(f"Category order after mixing: {[p['category'] for p in all_posts]}")

    # ── 3. Group into 3 parts of 7 ──
    STORIES_PER_PART = 7
    parts       = [all_posts[i: i + STORIES_PER_PART] for i in range(0, len(all_posts), STORIES_PER_PART)]
    total_parts = len(parts)

    # ── 3. Build & post each carousel ──
    for part_idx, part_stories in enumerate(parts):
        part_num    = part_idx + 1
        story_start = part_idx * STORIES_PER_PART + 1
        story_end   = story_start + len(part_stories) - 1

        print(f"\n{'='*55}")
        print(f"  PART {part_num} of {total_parts}  |  Stories {story_start}–{story_end}")
        print(f"{'='*55}")

        image_files = []
        image_urls  = []

        # Cover
        print(f"  Creating cover image...")
        cover_file = create_cover_image(part_num, total_parts, story_start, story_end)
        image_files.append(cover_file)

        # 7 story images
        for i, post in enumerate(part_stories):
            story_idx = story_start + i
            print(f"  Creating story image {story_idx}...")
            story_file = create_story_image(
                post["headline"], post["caption"],
                post["category"], post["color"], story_idx,
            )
            image_files.append(story_file)

        # Upload all 8 images
        print(f"  Uploading {len(image_files)} images to ImgBB...")
        for img_file in image_files:
            try:
                url = upload_image(img_file)
                image_urls.append(url)
                print(f"    ✅ Uploaded: {img_file}")
                time.sleep(2)
            except Exception as e:
                print(f"    ❌ Upload failed for {img_file}: {e}")

        if len(image_urls) < len(image_files):
            print(f"  ⚠️  Upload incomplete ({len(image_urls)}/{len(image_files)}), skipping Part {part_num}")
            continue

        # Post carousel
        caption = (
            f"📰 21 News Stories — Part {part_num} of {total_parts} · Stories {story_start}–{story_end}\n\n"
            f"Top news delivered daily — fully automated ⚡\n"
            f"Swipe. Read. Stay Informed. 👋\n\n"
            f"#Top21News #DailyNews #NewsUpdate #NewsReel #BreakingNews #StayInformed"
        )
        post_carousel(image_urls, caption)

        # Pause between carousels (avoid rate limit)
        if part_num < total_parts:
            print(f"  ⏳ Waiting 60s before next carousel...")
            time.sleep(60)

    print(f"\n✅ Done! {len(all_posts)} stories posted in {total_parts} carousels.")

if __name__ == "__main__":
    main()
