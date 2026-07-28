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
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
IG_ACCESS_TOKEN   = os.environ.get("IG_ACCESS_TOKEN", "")
IG_ACCOUNT_ID     = os.environ.get("IG_ACCOUNT_ID", "")
GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")

# ── CATEGORIES ────────────────────────────────────────────────────────────────
CATEGORIES = [
    {"name": "Technology",    "query": "technology+AI",     "count": 6, "color": "#00D4FF"},
    {"name": "Business",      "query": "business+economy",  "count": 5, "color": "#00FF88"},
    {"name": "Politics",      "query": "world+politics",    "count": 4, "color": "#FF6B35"},
    {"name": "Science",       "query": "science+health",    "count": 3, "color": "#B66DFF"},
    {"name": "Entertainment", "query": "entertainment",     "count": 2, "color": "#FFD700"},
    {"name": "Sports",        "query": "sports",            "count": 1, "color": "#FF4081"},
]

# ── DESIGN ────────────────────────────────────────────────────────────────────
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

For each story:
1. "headline": Rewrite as a SHORT punchy title (max 8 words, no source name like "- CNN" or "- Reuters")
2. "caption": Write 4-5 complete sentences explaining the full story. Every sentence MUST end with a full stop. Never cut off mid-sentence. Include context, impact and key details.
3. "source": The publication name from the original headline

Headlines:
{headlines}

Respond ONLY in this exact JSON format, no markdown backticks:
[
  {{
    "headline": "short punchy title max 8 words",
    "caption": "Full 4-5 sentence story here. Each sentence complete. Never cut off. Ends with full stop.",
    "source": "publication name e.g. Reuters, CNN, BBC",
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

    draw.rectangle([0, 0, 7, H], fill=ACCENT_COLOR)
    draw.rectangle([0, 0, W, 5], fill=ACCENT_COLOR)

    f_handle = load_font(42, bold=True)
    label    = "@Top21News"
    bbox     = draw.textbbox((0, 0), label, font=f_handle)
    lw       = bbox[2] - bbox[0]
    cx, ty   = W // 2, 68
    draw.text((cx, ty), label, fill=ACCENT_COLOR, font=f_handle, anchor="mm")
    gap = 24
    draw.line([(50, ty), (cx - lw//2 - gap, ty)], fill=ACCENT_COLOR, width=2)
    draw.line([(cx + lw//2 + gap, ty), (W - 50, ty)], fill=ACCENT_COLOR, width=2)

    draw.text((cx, H//2 - 80), "21", fill="#FFFFFF",
              font=load_font(320, bold=True), anchor="mm")
    draw.text((cx, H//2 + 145), "NEWS STORIES", fill=ACCENT_COLOR,
              font=load_font(80, bold=True), anchor="mm")
    draw.line([(120, H//2 + 198), (W - 120, H//2 + 198)], fill=ACCENT_COLOR, width=2)

    part_text = f"PART {part_num} OF {total_parts}   \u00b7   STORIES {story_start} \u2013 {story_end}"
    draw.text((cx, H//2 + 252), part_text, fill="#FFFFFF",
              font=load_font(40, bold=True), anchor="mm")
    draw.text((cx, H//2 + 316), "Swipe left to read  \u203a", fill="#4A7A9B",
              font=load_font(34), anchor="mm")
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
    MARGIN  = 60

    draw.rectangle([0, 0, 7, H], fill=(r, g, b))
    draw.rectangle([0, 0, W, 5], fill=(r, g, b))

    # Category pill
    f_cat   = load_font(30, bold=True)
    cat_lbl = f"#{category.upper()}"
    cbbox   = draw.textbbox((0, 0), cat_lbl, font=f_cat)
    cw      = cbbox[2] - cbbox[0] + 36
    draw_rounded_rect(draw, [MARGIN, 38, MARGIN + cw, 88], radius=10, fill=(r, g, b))
    draw.text((MARGIN + cw//2, 63), cat_lbl, fill="#FFFFFF", font=f_cat, anchor="mm")

    # Story counter
    draw.text((W - MARGIN, 38), f"{index} / {total}", fill=ACCENT_COLOR,
              font=load_font(42, bold=True), anchor="rt")
    draw.text((W - MARGIN, 90), "swipe for more  \u203a", fill="#3A5A7A",
              font=load_font(26), anchor="rt")

    # Headline — smaller font, single line, truncated cleanly
    f_hl      = load_font(40, bold=True)
    # Truncate headline to fit one line (max 42 chars)
    hl_text   = headline if len(headline) <= 42 else headline[:39] + "..."
    hl_y      = 130
    # Allow up to 3 lines max with wrapping at 36 chars
    wrapped   = textwrap.wrap(hl_text, width=36)[:3]
    for line in wrapped:
        draw.text((MARGIN, hl_y), line, fill="#FFFFFF", font=f_hl)
        hl_y += 52

    # Underline
    draw.rectangle([MARGIN, hl_y + 6, MARGIN + 70, hl_y + 13], fill=(r, g, b))
    hl_y += 32

    # Content box — taller now since headline is smaller
    draw_rounded_rect(draw, [MARGIN, hl_y, W - MARGIN, H - 140],
                      radius=18, fill=hex_to_rgb(BG_CARD_COLOR))

    # Caption — smaller font, more lines, NEVER truncate mid-sentence
    f_cap     = load_font(33)
    # Split into sentences and rebuild to fit
    sentences = [s.strip() + "." for s in caption.replace("..","").split(".") if s.strip()]
    full_text = " ".join(sentences)
    cap_lines = textwrap.wrap(full_text, width=42)
    # Calculate how many lines fit in the box
    box_height = (H - 140) - hl_y
    max_lines  = min(len(cap_lines), (box_height - 80) // 46)
    # Find last complete sentence within max_lines
    fitted_text = " ".join(cap_lines[:max_lines])
    # Cut at last full stop to never leave incomplete sentence
    last_stop = fitted_text.rfind(".")
    if last_stop > 0:
        fitted_text = fitted_text[:last_stop + 1]
    display_lines = textwrap.wrap(fitted_text, width=42)
    cap_y = hl_y + 36
    for line in display_lines:
        if cap_y + 46 > H - 150:
            break
        draw.text((MARGIN + 30, cap_y), line, fill="#C8D8E8", font=f_cap)
        cap_y += 46

    # Source + date
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

# ── UPLOAD: GitHub Releases (no external service needed) ─────────────────────
def get_or_create_release(tag="image-hosting"):
    """Get existing release upload URL or create one."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
    }
    # Try to get existing release
    r = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/tags/{tag}",
        headers=headers,
    )
    if r.status_code == 200:
        return r.json()["upload_url"].split("{")[0]

    # Create new release
    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases",
        headers=headers,
        json={
            "tag_name":   tag,
            "name":       "Bot Image Hosting",
            "body":       "Auto-generated images for Top21News bot. Do not delete.",
            "draft":      False,
            "prerelease": False,
        },
    )
    data = r.json()
    if "upload_url" not in data:
        raise Exception(f"Failed to create release: {data}")
    return data["upload_url"].split("{")[0]

# ── UPLOAD: commit to repo → raw.githubusercontent.com (Instagram-friendly) ──
def upload_image(filepath, upload_url=None):
    """Commit image to repo and return raw.githubusercontent.com URL.
    These are direct URLs with no redirects — Instagram can always fetch them."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
    }
    # Use a fixed folder in the repo — images folder
    unique_name = f"{int(time.time())}_{os.path.basename(filepath)}"
    api_url     = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/contents/images/{unique_name}"

    with open(filepath, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    for attempt in range(1, 4):
        try:
            r = requests.put(
                api_url,
                headers=headers,
                json={
                    "message": f"bot: add {unique_name}",
                    "content": content_b64,
                },
                timeout=60,
            )
            data = r.json()
            if "content" not in data:
                raise Exception(f"Commit error: {data.get('message', data)}")

            # raw.githubusercontent.com = direct URL, no auth, no redirect
            raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/images/{unique_name}"
            print(f"      ✅ {os.path.basename(filepath)} → {raw_url[:70]}...")
            time.sleep(2)  # Let GitHub CDN propagate
            return raw_url
        except Exception as e:
            if attempt < 3:
                wait = attempt * 10
                print(f"      [RETRY {attempt}/3] {e} — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise Exception(f"Upload failed after 3 attempts: {e}")


# ── INSTAGRAM CAROUSEL ────────────────────────────────────────────────────────
def post_carousel(image_urls, caption):
    if not IG_ACCESS_TOKEN:
        print("  [SKIP] Instagram not configured.")
        return True

    # Create individual containers
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
                print(f"    [TRANSIENT] Retrying in {attempt*15}s...")
                time.sleep(attempt * 15)
            else:
                print(f"    [ERROR] Container failed: {result}")
                return False
        container_ids.append(result["id"])
        time.sleep(4)

    # Create carousel container
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
        print(f"    [ERROR] Carousel failed: {result}")
        return False
    carousel_id = result["id"]
    time.sleep(10)

    # Publish with retry
    print(f"    Publishing carousel...")
    for attempt in range(1, 4):
        r2 = requests.post(
            f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media_publish",
            data={"creation_id": carousel_id, "access_token": IG_ACCESS_TOKEN},
        )
        result = r2.json()
        if "id" in result:
            print(f"    ✅ Published! ID: {result['id']}")
            return True
        is_transient = result.get("error", {}).get("is_transient", False)
        if is_transient and attempt < 3:
            print(f"    [TRANSIENT] Retrying publish in {attempt*20}s...")
            time.sleep(attempt * 20)
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
    print(f"\nTotal stories: {len(all_posts)}")
    if len(all_posts) == 0:
        print("No stories. Exiting.")
        return

    # 2. Round-robin category mix
    buckets      = defaultdict(list)
    for post in all_posts:
        buckets[post["category"]].append(post)
    mixed        = []
    bucket_lists = list(buckets.values())
    for i in range(max(len(b) for b in bucket_lists)):
        for bucket in bucket_lists:
            if i < len(bucket):
                mixed.append(bucket[i])
    all_posts = mixed[:21]
    print(f"Category mix: {[p['category'] for p in all_posts]}")

    # 3. Split into 3 parts of 7 and post
    STORIES_PER_PART = 7
    parts       = [all_posts[i: i + STORIES_PER_PART] for i in range(0, len(all_posts), STORIES_PER_PART)]
    total_parts = len(parts)

    for part_idx, part_stories in enumerate(parts):
        part_num    = part_idx + 1
        story_start = part_idx * STORIES_PER_PART + 1
        story_end   = story_start + len(part_stories) - 1

        print(f"\n{'='*55}")
        print(f"  PART {part_num}/{total_parts}  |  Stories {story_start}–{story_end}")
        print(f"{'='*55}")

        # Create images
        image_files = []
        print(f"  Creating cover...")
        image_files.append(create_cover_image(part_num, total_parts, story_start, story_end))
        for i, post in enumerate(part_stories):
            idx = story_start + i
            print(f"  Creating story {idx}...")
            image_files.append(create_story_image(
                post["headline"], post["caption"],
                post.get("source", "Top21News"),
                post["category"], post["color"], idx,
            ))

        # Upload to GitHub Releases
        print(f"  Uploading {len(image_files)} images...")
        image_urls = []
        for img_file in image_files:
            try:
                url = upload_image(img_file)
                image_urls.append(url)
                time.sleep(1)
            except Exception as e:
                print(f"    ❌ Failed: {img_file}: {e}")

        if len(image_urls) < len(image_files):
            print(f"  ⚠️ Upload incomplete ({len(image_urls)}/{len(image_files)}), skipping Part {part_num}")
            continue

        # Post carousel
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

        if part_num < total_parts:
            print(f"  ⏳ Waiting 60s before next carousel...")
            time.sleep(60)

    print(f"\n✅ Done! {len(all_posts)} stories in {total_parts} carousels.")

if __name__ == "__main__":
    main()
