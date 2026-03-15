import os
import sys
import requests
import feedparser
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import textwrap
import json
import time

# ── CONFIG ────────────────────────────────────────────────
GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
IG_ACCESS_TOKEN     = os.environ.get("IG_ACCESS_TOKEN", "")
IG_ACCOUNT_ID       = os.environ.get("IG_ACCOUNT_ID", "")
IMGBB_API_KEY       = os.environ.get("IMGBB_API_KEY", "")

# News category mix (total = 21)
CATEGORIES = [
    {"name": "Technology", "query": "technology AI",        "count": 6, "color": "#00D4FF"},
    {"name": "Business",   "query": "business economy",     "count": 5, "color": "#00FF88"},
    {"name": "Politics",   "query": "world politics",       "count": 4, "color": "#FF6B35"},
    {"name": "Science",    "query": "science health",       "count": 3, "color": "#B66DFF"},
    {"name": "Entertainment","query": "entertainment",      "count": 2, "color": "#FFD700"},
    {"name": "Sports",     "query": "sports",               "count": 1, "color": "#FF4081"},
]

# ── STEP 1: FETCH NEWS FROM RSS ───────────────────────────
def fetch_news(query, count):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:count*3]:  # fetch 3x, AI will pick best
        articles.append({
            "title": entry.title,
            "summary": entry.get("summary", "")[:300],
            "link": entry.link,
        })
    return articles

# ── STEP 2: USE GEMINI TO PICK & SUMMARIZE ────────────────
def ai_summarize(articles, category, count):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    headlines = "\n".join([f"{i+1}. {a['title']}" for i, a in enumerate(articles)])

    prompt = f"""You are a news editor for Instagram account @Top21News.
From these {category} headlines, pick the {count} most interesting and engaging ones.
For each picked headline, write:
- A punchy 1-sentence Instagram caption (max 150 chars)
- 5 relevant hashtags

Headlines:
{headlines}

Respond ONLY in this exact JSON format, no extra text:
[
  {{
    "headline": "original headline here",
    "caption": "your punchy caption here",
    "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5"
  }}
]"""

    response = model.generate_content(prompt)
    text = response.text.strip()
    # Clean up any markdown code fences
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

# ── STEP 3: GENERATE IMAGE WITH PILLOW ────────────────────
def create_post_image(headline, caption, category, color, index):
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), color="#0A0A0F")
    draw = ImageDraw.Draw(img)

    # Background gradient effect (simple)
    for i in range(H):
        alpha = int(20 * (1 - i/H))
        draw.line([(0, i), (W, i)], fill=(10, 10, 15))

    # Color accent bar at top
    hex_color = color.lstrip("#")
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    draw.rectangle([0, 0, W, 12], fill=(r, g, b))

    # Category badge
    draw.rounded_rectangle([40, 40, 40+len(category)*14+20, 90],
                           radius=8, fill=(r, g, b, 40))
    draw.rectangle([40, 40, 40+len(category)*14+20, 90], outline=(r, g, b), width=2)

    # Logo / account name
    draw.text((W-60, 55), "@Top21News", fill="#FFFFFF", anchor="rm")

    # Category text
    draw.text((55, 55), f"#{category.upper()}", fill=(r, g, b), anchor="lm")

    # Headline (large text, wrapped)
    wrapped = textwrap.wrap(headline, width=30)[:5]  # max 5 lines
    y = 200
    for line in wrapped:
        draw.text((W//2, y), line, fill="#FFFFFF", anchor="mm")
        y += 85

    # Divider line
    draw.line([(80, y+30), (W-80, y+30)], fill=(r, g, b), width=2)

    # Caption text (smaller)
    wrapped_caption = textwrap.wrap(caption, width=50)[:3]
    y += 70
    for line in wrapped_caption:
        draw.text((W//2, y), line, fill="#AAAAAA", anchor="mm")
        y += 45

    # Post number badge
    draw.ellipse([W-100, H-100, W-40, H-40], outline=(r, g, b), width=2)
    draw.text((W-70, H-70), str(index), fill=(r, g, b), anchor="mm")

    # Bottom bar
    draw.rectangle([0, H-12, W, H], fill=(r, g, b))

    # Date
    date_str = datetime.now().strftime("%B %d, %Y")
    draw.text((W//2, H-35), date_str, fill="#555555", anchor="mm")

    filename = f"post_{index:02d}.png"
    img.save(filename)
    return filename

# ── STEP 4: UPLOAD IMAGE TO IMGBB ─────────────────────────
def upload_image(filepath):
    with open(filepath, "rb") as f:
        import base64
        img_data = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": img_data}
    )
    result = response.json()
    return result["data"]["url"]

# ── STEP 5: POST TO INSTAGRAM ─────────────────────────────
def post_to_instagram(image_url, caption, hashtags):
    if not IG_ACCESS_TOKEN or IG_ACCESS_TOKEN == "":
        print(f"  [SKIP] Instagram not configured yet. Would post: {caption[:60]}...")
        return True

    full_caption = f"{caption}\n\n{hashtags}\n\n#Top21News #DailyNews #NewsUpdate"

    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media"
    container_data = {
        "image_url": image_url,
        "caption": full_caption,
        "access_token": IG_ACCESS_TOKEN,
    }
    r = requests.post(container_url, data=container_data)
    container_id = r.json().get("id")

    if not container_id:
        print(f"  [ERROR] Container creation failed: {r.json()}")
        return False

    time.sleep(5)  # wait for media to process

    # Step 2: Publish
    publish_url = f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media_publish"
    publish_data = {
        "creation_id": container_id,
        "access_token": IG_ACCESS_TOKEN,
    }
    r2 = requests.post(publish_url, data=publish_data)
    result = r2.json()

    if "id" in result:
        print(f"  ✅ Posted successfully! Post ID: {result['id']}")
        return True
    else:
        print(f"  [ERROR] Publish failed: {result}")
        return False

# ── MAIN ──────────────────────────────────────────────────
def main():
    print(f"\n🚀 Top21News Bot starting — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    post_index = 1

    for category in CATEGORIES:
        print(f"\n📡 Fetching {category['name']} news...")
        articles = fetch_news(category["query"], category["count"])
        print(f"  Found {len(articles)} articles")

        print(f"  🧠 AI summarizing top {category['count']}...")
        try:
            posts = ai_summarize(articles, category["name"], category["count"])
        except Exception as e:
            print(f"  [ERROR] AI failed for {category['name']}: {e}")
            continue

        for post in posts:
            print(f"  🎨 Creating image for post {post_index}...")
            img_file = create_post_image(
                post["headline"],
                post["caption"],
                category["name"],
                category["color"],
                post_index
            )

            print(f"  ☁️  Uploading image...")
            try:
                img_url = upload_image(img_file)
            except Exception as e:
                print(f"  [ERROR] Upload failed: {e}")
                post_index += 1
                continue

            print(f"  📸 Posting to Instagram...")
            post_to_instagram(img_url, post["caption"], post["hashtags"])

            post_index += 1
            time.sleep(30)  # 30s gap between posts (Instagram rate limit)

    print(f"\n✅ Done! {post_index-1} posts processed.")

if __name__ == "__main__":
    main()
