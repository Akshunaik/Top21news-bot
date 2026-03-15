import os
import requests
import feedparser
import google.genai as genai
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import textwrap
import json
import time
import base64

# ── CONFIG ────────────────────────────────────────────────
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_ACCOUNT_ID   = os.environ.get("IG_ACCOUNT_ID", "")
IMGBB_API_KEY   = os.environ.get("IMGBB_API_KEY", "")

CATEGORIES = [
    {"name": "Technology",     "query": "technology+AI",       "count": 6, "color": "#00D4FF"},
    {"name": "Business",       "query": "business+economy",    "count": 5, "color": "#00FF88"},
    {"name": "Politics",       "query": "world+politics",      "count": 4, "color": "#FF6B35"},
    {"name": "Science",        "query": "science+health",      "count": 3, "color": "#B66DFF"},
    {"name": "Entertainment",  "query": "entertainment",       "count": 2, "color": "#FFD700"},
    {"name": "Sports",         "query": "sports",              "count": 1, "color": "#FF4081"},
]

# ── STEP 1: FETCH NEWS ────────────────────────────────────
def fetch_news(query, count):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:count*3]:
        articles.append({
            "title": entry.title,
            "summary": entry.get("summary", "")[:300],
        })
    return articles

# ── STEP 2: GEMINI AI SUMMARIZE ───────────────────────────
def ai_summarize(articles, category, count):
    client = genai.Client(api_key=GEMINI_API_KEY)
    headlines = "\n".join([f"{i+1}. {a['title']}" for i, a in enumerate(articles)])

    prompt = f"""You are a news editor for Instagram account @Top21News.
From these {category} headlines, pick the {count} most interesting ones.
For each, write:
- A punchy 1-sentence Instagram caption (max 150 chars)
- 5 relevant hashtags

Headlines:
{headlines}

Respond ONLY in this exact JSON format, no extra text, no markdown:
[
  {{
    "headline": "original headline here",
    "caption": "your punchy caption here",
    "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5"
  }}
]"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

# ── STEP 3: CREATE IMAGE ──────────────────────────────────
def create_post_image(headline, caption, category, color, index):
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), color="#0A0A0F")
    draw = ImageDraw.Draw(img)

    hex_color = color.lstrip("#")
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    # Top color bar
    draw.rectangle([0, 0, W, 12], fill=(r, g, b))

    # Category badge
    draw.rectangle([40, 40, 40+len(category)*13+20, 85], outline=(r, g, b), width=2)
    draw.text((55, 62), f"#{category.upper()}", fill=(r, g, b), anchor="lm")

    # Account name
    draw.text((W-55, 62), "@Top21News", fill="#FFFFFF", anchor="rm")

    # Headline
    wrapped = textwrap.wrap(headline, width=28)[:5]
    y = 220
    for line in wrapped:
        draw.text((W//2, y), line, fill="#FFFFFF", anchor="mm")
        y += 90

    # Divider
    draw.line([(80, y+20), (W-80, y+20)], fill=(r, g, b), width=2)

    # Caption
    wrapped_caption = textwrap.wrap(caption, width=48)[:3]
    y += 60
    for line in wrapped_caption:
        draw.text((W//2, y), line, fill="#AAAAAA", anchor="mm")
        y += 48

    # Post number
    draw.ellipse([W-105, H-105, W-35, H-35], outline=(r, g, b), width=2)
    draw.text((W-70, H-70), str(index), fill=(r, g, b), anchor="mm")

    # Bottom bar
    draw.rectangle([0, H-12, W, H], fill=(r, g, b))

    # Date
    draw.text((W//2, H-35), datetime.now().strftime("%B %d, %Y"), fill="#555555", anchor="mm")

    filename = f"post_{index:02d}.png"
    img.save(filename)
    return filename

# ── STEP 4: UPLOAD TO IMGBB ───────────────────────────────
def upload_image(filepath):
    with open(filepath, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": img_data}
    )
    return response.json()["data"]["url"]

# ── STEP 5: POST TO INSTAGRAM ─────────────────────────────
def post_to_instagram(image_url, caption, hashtags):
    if not IG_ACCESS_TOKEN:
        print(f"  [SKIP] Instagram not configured yet.")
        return True

    full_caption = f"{caption}\n\n{hashtags}\n\n#Top21News #DailyNews #NewsUpdate"
    container_url = f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media"
    r = requests.post(container_url, data={
        "image_url": image_url,
        "caption": full_caption,
        "access_token": IG_ACCESS_TOKEN,
    })
    container_id = r.json().get("id")
    if not container_id:
        print(f"  [ERROR] {r.json()}")
        return False

    time.sleep(5)
    r2 = requests.post(f"https://graph.facebook.com/v18.0/{IG_ACCOUNT_ID}/media_publish", data={
        "creation_id": container_id,
        "access_token": IG_ACCESS_TOKEN,
    })
    result = r2.json()
    if "id" in result:
        print(f"  ✅ Posted! ID: {result['id']}")
        return True
    print(f"  [ERROR] {result}")
    return False

# ── MAIN ──────────────────────────────────────────────────
def main():
    print(f"\n🚀 Top21News Bot — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    post_index = 1

    for category in CATEGORIES:
        print(f"\n📡 Fetching {category['name']} news...")
        articles = fetch_news(category["query"], category["count"])
        print(f"  Found {len(articles)} articles")

        print(f"  🧠 AI picking top {category['count']}...")
        try:
            posts = ai_summarize(articles, category["name"], category["count"])
        except Exception as e:
            print(f"  [ERROR] AI failed: {e}")
            continue

        for post in posts:
            print(f"  🎨 Creating image {post_index}...")
            img_file = create_post_image(
                post["headline"], post["caption"],
                category["name"], category["color"], post_index
            )

            print(f"  ☁️  Uploading...")
            try:
                img_url = upload_image(img_file)
            except Exception as e:
                print(f"  [ERROR] Upload failed: {e}")
                post_index += 1
                continue

            print(f"  📸 Posting to Instagram...")
            post_to_instagram(img_url, post["caption"], post["hashtags"])
            post_index += 1
            time.sleep(30)

    print(f"\n✅ Done! {post_index-1} posts processed.")

if __name__ == "__main__":
    main()
```

4. Also update **`requirements.txt`** — click it, edit, replace with:
```
feedparser
google-genai
Pillow
requests
