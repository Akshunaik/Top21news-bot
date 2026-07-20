import os
import requests
import feedparser
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import textwrap
import json
import time
import base64
from collections import defaultdict

# ── ENV ───────────────────────────────────────────────────────────────────────
GEMINI_API_KEY       = os.environ["GEMINI_API_KEY"]
IG_ACCESS_TOKEN      = os.environ.get("IG_ACCESS_TOKEN", "")
IG_ACCOUNT_ID        = os.environ.get("IG_ACCOUNT_ID", "")
CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")

# ── CATEGORIES (21 stories total) ────────────────────────────────────────────
CATEGORIES = [
    {"name": "Technology",    "query": "technology+AI",     "count": 6, "color": "#00D4FF"},
    {"name": "Business",      "query": "business+economy",  "count": 5, "color": "#00FF88"},
    {"name": "Politics",      "query": "world+politics",    "count": 4, "color": "#FF6B35"},
    {"name": "Science",       "query": "science+health",    "count": 3, "color": "#B66DFF"},
    {"name": "Entertainment", "query": "entertainment",     "count": 2, "color": "#FFD700"},
    {"name": "Sports",        "query": "sports",            "count": 1, "color": "#FF4081"},
]

# ── DESIGN CONSTANTS ──────────────────────────────────────────────────────────
BG_COLOR      = "#0D1B2A"
BG_CARD_COLOR = "#0A1628"
ACCENT_COLOR  = "#00D4FF"
W, H          = 1080, 1080

# ── HELPERS ───────────────────────────────────────────────────────────────────
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def load_font(size, bold=False):
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

def draw_rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.ellipse([x1, y1, x1 + radius*2, y1 + radius*2], fill=fill)
    draw.ellipse([x2 - radius*2, y1, x2, y1 + radius*2], fill=fill)
    draw.ellipse([x1, y2 - radius*2, x1 + radius*2, y2], fill=fill)
    draw.ellipse([x2 - radius*2, y2 - radius*2, x2, y2], fill=fill)

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
For each, write a complete 2-3 sentence summary. Every sentence MUST end with a full stop.
Also identify the likely publication name from the headline.

Headlines:
{headlines}

Respond ONLY in this exact JSON format with no extra text and no markdown backticks:
[
  {{
    "headline": "original headline here",
    "caption": "your complete 2-3 sentence summary here. Each sentence ends with a full stop.",
    "source": "publication name e.g. Reuters, CNN, BBC, TechCrunch",
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

# ── COVER IMAGE ───────────────────────────────────────────────────────────────
def create_cover_image(part_num, total_parts, story_start, story_end):
    img  = Image.new("RGB", (W, H), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Left vertical cyan bar + top line
    draw.rectangle([0, 0, 7, H], fill=ACCENT_COLOR)
    draw.rectangle([0, 0, W, 5], fill=ACCENT_COLOR)

    # @Top21News centered with lines on both sides
    f_handle = load_font(42, bold=True)
    label    = "@Top21News"
    bbox     = draw.textbbox((0, 0), label, font=f_handle)
    lw       = bbox[2] - bbox[0]
    cx, ty   = W // 2, 68
    draw.text((cx, ty), label, fill=ACCENT_COLOR, font=f_handle, anchor="mm")
    gap = 24
    draw.line([(50, ty), (cx - lw//2 - gap, ty)], fill=ACCENT_COLOR, width=2)
    draw.line([(cx + lw//2 + gap, ty), (W - 50, ty)], fill=ACCENT_COLOR, width=2)

    # Giant "21"
    draw.text((cx, H//2 - 80), "21", fill="#FFFFFF",
              font=load_font(320, bold=True), anchor="mm")

    # "NEWS STORIES" in cyan
    draw.text((cx, H//2 + 145), "NEWS STORIES", fill=ACCENT_COLOR,
              font=load_font(80, bold=True), anchor="mm")

    # Cyan separator
    draw.line([(120, H//2 + 198), (W - 120, H//2 + 198)], fill=ACCENT_COLOR, width=2)

    # Part info
    part_text = f"PART {part_num} OF {total_parts}   \u00b7   STORIES {story_start} \u2013 {story_end}"
    draw.text((cx, H//2 + 252), part_text, fill="#FFFFFF",
              font=load_font(40, bold=True), anchor="mm")

    # Swipe hint
    draw.text((cx, H//2 + 316), "Swipe left to read  \u203a", fill="#4A7A9B",
              font=load_font(34), anchor="mm")

    # Date
    draw.text((cx, H - 48), datetime.now().strftime("%B %d, %Y"), fill="#2A4A6A",
              font=load_font(30), anchor="mm")

    filename = f"cover_{part_num}.png"
    img.save(filename)
    return filename

# ── STORY IMAGE ───────────────────────────────────────────────────────────────
def create_story_image(headline, caption, source, category, color, index, total=21):
    img  = Image.new("RGB", (W, H), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    r, g, b = hex_to_rgb(color)

    # Left bar + top line
    draw.rectangle([0, 0, 7, H], fill=(r, g, b))
    draw.rectangle([0, 0, W, 5], fill=(r, g, b))

    MARGIN = 60

    # Category pill (solid filled)
    f_cat  = load_font(30, bold=True)
    cat_lbl = f"#{category.upper()}"
    cbbox   = draw.textbbox((0, 0), cat_lbl, font=f_cat)
    cw      = cbbox[2] - cbbox[0] + 36
    draw_rounded_rect(draw, [MARGIN, 38, MARGIN + cw, 88], radius=10, fill=(r, g, b))
    draw.text((MARGIN + cw//2, 63), cat_lbl, fill="#FFFFFF", font=f_cat, anchor="mm")

    # Story number top right
    num_str = f"{index} / {total}"
    draw.text((W - MARGIN, 38), num_str, fill=ACCENT_COLOR,
              font=load_font(42, bold=True), anchor="rt")
    draw.text((W - MARGIN, 90), "swipe for more  \u203a", fill="#3A5A7A",
              font=load_font(26), anchor="rt")

    # Headline — left aligned, large bold
    hl_y    = 130
    wrapped = textwrap.wrap(headline, width=24)[:5]
    for line in wrapped:
        draw.text((MARGIN, hl_y), line, fill="#FFFFFF", font=load_font(58, bold=True))
        hl_y += 72

    # Short underline below headline
    draw.rectangle([MARGIN, hl_y + 8, MARGIN + 90, hl_y + 16], fill=(r, g, b))
    hl_y += 38

    # Content box
    box_y2 = H - 140
    draw_rounded_rect(draw, [MARGIN, hl_y, W - MARGIN, box_y2],
                      radius=18, fill=hex_to_rgb(BG_CARD_COLOR))

    # Caption inside box
    cap_lines = textwrap.wrap(caption, width=38)[:6]
    cap_y     = hl_y + 44
    for line in cap_lines:
        draw.text((MARGIN + 36, cap_y), line, fill="#C8D8E8", font=load_font(38))
        cap_y += 56

    # Bottom: source + date
    draw.text((MARGIN, H - 110), f"Source: {source}", fill="#3A5A7A", font=load_font(30))
    draw.text((W - MARGIN, H - 110), datetime.now().strftime("%B %d, %Y"),
              fill="#3A5A7A", font=load_font(30), anchor="rt")

    # Branding bar
    draw.rectangle([0, H - 62, W, H], fill="#060E18")
    draw.text((W//2, H - 31), "TOP21NEWS  \u2022\u2022\u2022  21 STORIES DAILY",
              fill="#1A3A5A", font=load_font(26, bold=True), anchor="mm")

    filename = f"story_{index:02d}.png"
    img.save(filename)
    return filename

# ── UPLOAD TO CLOUDINARY ──────────────────────────────────────────────────────
def upload_image(filepath):
    """Upload to Cloudinary — reliable, fast, Instagram-friendly URLs."""
    import hashlib, hmac
    timestamp = str(int(time.time()))

    # Build signature
    params_to_sign = f"timestamp={timestamp}"
    signature = hmac.new(
        CLOUDINARY_API_SECRET.encode(),
        params_to_sign.encode(),
        hashlib.sha1
    ).hexdigest()

    for attempt in range(1, 4):
        try:
            with open(filepath, "rb") as f:
                response = requests.post(
                    f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
                    data={
                        "api_key":   CLOUDINARY_API_KEY,
                        "timestamp": timestamp,
                        "signature": signature,
                    },
                    files={"file": f},
                    timeout=30,
                )
            result = response.json()
            if "secure_url" not in result:
                raise Exception(f"Cloudinary error: {result}")
            url = result["secure_url"]
            print(f"      URL: {url}")
            return url
        except Exception as e:
            if attempt < 3:
                wait = attempt * 10
                print(f"      [UPLOAD RETRY {attempt}/3] {e} — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise Exception(f"Cloudinary upload failed after 3 attempts: {e}")

# ── INSTAGRAM CAROUSEL POST ───────────────────────────────────────────────────
def post_carousel(image_urls, caption):
    if not IG_ACCESS_TOKEN:
        print("  [SKIP] Instagram not configured.")
        return True

    # Step 1: individual containers with retry
    container_ids = []
    for i, url in enumerate(image_urls):
        print(f"    Creating container {i+1}/{len(image_urls)}...")
        for attempt in range(1, 4):
            r = requests.post(
                f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media",
                data={
                    "image_url":        url,
                    "is_carousel_item": "true",
                    "access_token":     IG_ACCESS_TOKEN,
                },
            )
            result = r.json()
            if "id" in result:
                break
            is_transient = result.get("error", {}).get("is_transient", False)
            if is_transient and attempt < 3:
                wait = attempt * 15
                print(f"    [TRANSIENT] Attempt {attempt} failed, retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"    [ERROR] Container failed: {result}")
                return False
        container_ids.append(result["id"])
        time.sleep(4)

    # Step 2: carousel container
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
    time.sleep(10)

    # Step 3: publish with retry
    print(f"    Publishing carousel...")
    for attempt in range(1, 4):
        r2 = requests.post(
            f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media_publish",
            data={"creation_id": carousel_id, "access_token": IG_ACCESS_TOKEN},
        )
        result = r2.json()
        if "id" in result:
            print(f"    ✅ Published! Carousel ID: {result['id']}")
            return True
        is_transient = result.get("error", {}).get("is_transient", False)
        if is_transient and attempt < 3:
            wait = attempt * 20
            print(f"    [TRANSIENT] Publish attempt {attempt} failed, retrying in {wait}s...")
            time.sleep(wait)
        else:
            print(f"    [ERROR] Publish failed: {result}")
            return False

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Top21News Bot starting {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 1. Collect all 21 stories
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
                if "source" not in post:
                    post["source"] = category["name"]
            all_posts.extend(posts)
            print(f"  Summarised {len(posts)} stories")
        except Exception as e:
            print(f"  AI failed: {e}")

    all_posts = all_posts[:21]
    print(f"\nTotal stories collected: {len(all_posts)}")
    if len(all_posts) == 0:
        print("No stories collected. Exiting.")
        return

    # 2. Round-robin mix by category
    buckets      = defaultdict(list)
    for post in all_posts:
        buckets[post["category"]].append(post)
    mixed        = []
    bucket_lists = list(buckets.values())
    max_len      = max(len(b) for b in bucket_lists)
    for i in range(max_len):
        for bucket in bucket_lists:
            if i < len(bucket):
                mixed.append(bucket[i])
    all_posts = mixed[:21]
    print(f"Category order: {[p['category'] for p in all_posts]}")

    # 3. Split into 3 parts of 7
    STORIES_PER_PART = 7
    parts       = [all_posts[i: i + STORIES_PER_PART] for i in range(0, len(all_posts), STORIES_PER_PART)]
    total_parts = len(parts)

    # 4. Build & post each carousel
    for part_idx, part_stories in enumerate(parts):
        part_num    = part_idx + 1
        story_start = part_idx * STORIES_PER_PART + 1
        story_end   = story_start + len(part_stories) - 1

        print(f"\n{'='*55}")
        print(f"  PART {part_num} of {total_parts}  |  Stories {story_start}–{story_end}")
        print(f"{'='*55}")

        image_files = []
        image_urls  = []

        # Cover image
        print(f"  Creating cover image...")
        image_files.append(create_cover_image(part_num, total_parts, story_start, story_end))

        # 7 story images
        for i, post in enumerate(part_stories):
            story_idx = story_start + i
            print(f"  Creating story image {story_idx}...")
            image_files.append(create_story_image(
                post["headline"], post["caption"],
                post.get("source", "Top21News"),
                post["category"], post["color"],
                story_idx, total=21,
            ))

        # Upload all 8
        print(f"  Uploading {len(image_files)} images to Cloudinary...")
        for img_file in image_files:
            try:
                url = upload_image(img_file)
                image_urls.append(url)
                print(f"    ✅ Uploaded: {img_file}")
                time.sleep(1)
            except Exception as e:
                print(f"    ❌ Upload failed for {img_file}: {e}")

        if len(image_urls) < len(image_files):
            print(f"  ⚠️ Upload incomplete ({len(image_urls)}/{len(image_files)}), skipping Part {part_num}")
            continue

        # Caption + hashtags
        hashtags = (
            "#Top21News #DailyNews #NewsUpdate #NewsReel #BreakingNews #StayInformed "
            "#WorldNews #NewsOfTheDay #CurrentEvents #Headlines #NewsAlert #TodaysNews "
            "#InformationIsPower #NewsDigest #GlobalNews #NewsIn21 #TopStories "
            "#MustRead #NewsForYou #DailyUpdate #SwipeToRead"
        )
        caption = (
            f"📰 21 News Stories — Part {part_num} of {total_parts} · Stories {story_start}–{story_end}\n\n"
            f"Top news delivered daily — fully automated ⚡\n"
            f"Swipe. Read. Stay Informed. 👋\n\n"
            f"{hashtags}"
        )
        post_carousel(image_urls, caption)

        # Wait between carousels
        if part_num < total_parts:
            print(f"  ⏳ Waiting 60s before next carousel...")
            time.sleep(60)

    print(f"\n✅ Done! {len(all_posts)} stories in {total_parts} carousels.")

if __name__ == "__main__":
    main()
