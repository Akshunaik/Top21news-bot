"""
Top21News — Daily Pipeline
==========================
Posts 21 news stories as 3 Instagram carousels.

Each carousel = 8 slides:
  Slide 1  →  Branded cover card (Part X/3, Stories N–M)
  Slides 2–8 →  7 individual news story cards

Structure:
  Post 1:  Cover (Part 1/3, Stories 1–7)  + Stories 1–7
  Post 2:  Cover (Part 2/3, Stories 8–14) + Stories 8–14
  Post 3:  Cover (Part 3/3, Stories 15–21)+ Stories 15–21

Required GitHub Actions secrets:
  GEMINI_API_KEY, IMGBB_API_KEY, IG_USER_ID, IG_ACCESS_TOKEN
"""

import os, json, time, base64, tempfile, requests
from datetime import datetime
from generate_card import create_news_card, create_cover_card

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
IMGBB_API_KEY   = os.environ["IMGBB_API_KEY"]
IG_USER_ID      = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]

TOTAL_STORIES   = 21
STORIES_PER_POST = 7          # 7 news + 1 cover = 8 slides per carousel
TOTAL_POSTS     = 3           # 3 × 7 = 21
DATE_STR        = datetime.now().strftime("%B %d, %Y")

HASHTAGS = (
    "#Top21News #NewsToday #BreakingNews #DailyNews #WorldNews "
    "#Headlines #NewsUpdate #InstaNews #trending #news"
)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Fetch 21 stories from Gemini
# ─────────────────────────────────────────────────────────────────────────────

def fetch_news_gemini() -> list[dict]:
    prompt = f"""Today is {DATE_STR}.

Return exactly 21 of today's most important global news stories.
Respond ONLY with a valid JSON array — no markdown, no backticks, no explanation.

Each item must have these exact keys:
  "headline"  – concise headline, max 12 words
  "summary"   – 2-3 sentence plain-English summary, max 60 words
  "category"  – one of: World, Business, Tech, Science, Sports, Health, Entertainment
  "source"    – original news outlet name

Return exactly 21 items. Diverse categories. No duplicates."""

    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        params={"key": GEMINI_API_KEY},
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 4096},
        },
        timeout=60,
    )
    resp.raise_for_status()
    raw  = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    raw  = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    news = json.loads(raw)
    print(f"   Gemini returned {len(news)} stories")
    return news[:TOTAL_STORIES]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Generate all cards grouped by post
# ─────────────────────────────────────────────────────────────────────────────

def generate_cards(news: list[dict], work_dir: str) -> list[list[str]]:
    """
    Returns a list of 3 groups, each group = list of image paths:
      Group 0: [cover_p1.jpg, story_01.jpg … story_07.jpg]  ← 8 slides
      Group 1: [cover_p2.jpg, story_08.jpg … story_14.jpg]  ← 8 slides
      Group 2: [cover_p3.jpg, story_15.jpg … story_21.jpg]  ← 8 slides
    """
    groups = []

    for post_idx in range(TOTAL_POSTS):
        story_start = post_idx * STORIES_PER_POST + 1           # 1, 8, 15
        story_end   = story_start + STORIES_PER_POST - 1        # 7, 14, 21
        part_num    = post_idx + 1

        group_paths = []

        # Cover card for this carousel
        cover_path = os.path.join(work_dir, f"p{part_num}_cover.jpg")
        create_cover_card(
            date_str    = DATE_STR,
            part_num    = part_num,
            total_parts = TOTAL_POSTS,
            story_start = story_start,
            story_end   = story_end,
            output_path = cover_path,
        )
        group_paths.append(cover_path)
        print(f"  ✅ Cover — Part {part_num}/{TOTAL_POSTS} (Stories {story_start}–{story_end})")

        # 7 news cards for this carousel
        batch = news[story_start - 1 : story_end]
        for i, item in enumerate(batch):
            global_num = story_start + i          # 1-based story number across all 21
            card_path  = os.path.join(work_dir, f"story_{global_num:02d}.jpg")
            create_news_card(
                headline     = item.get("headline", ""),
                summary      = item.get("summary", ""),
                category     = item.get("category", "NEWS"),
                source       = item.get("source", ""),
                date_str     = DATE_STR,
                slide_num    = global_num,
                total_slides = TOTAL_STORIES,
                output_path  = card_path,
            )
            group_paths.append(card_path)
            print(f"     Story {global_num}/{TOTAL_STORIES}")

        groups.append(group_paths)

    return groups


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Upload a single image to ImgBB
# ─────────────────────────────────────────────────────────────────────────────

def upload_to_imgbb(path: str) -> str:
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": encoded},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]["url"]


def upload_group(paths: list[str]) -> list[str]:
    urls = []
    for path in paths:
        url = upload_to_imgbb(path)
        urls.append(url)
        print(f"     ⬆️  {os.path.basename(path)}  → {url}")
        time.sleep(1)
    return urls


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Instagram Graph API helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ig_post(endpoint: str, data: dict) -> dict:
    resp = requests.post(
        f"https://graph.facebook.com/v19.0/{endpoint}",
        data={**data, "access_token": IG_ACCESS_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def ig_create_item(image_url: str) -> str:
    """Create a carousel item container. Returns media ID."""
    return _ig_post(f"{IG_USER_ID}/media", {
        "image_url": image_url,
        "is_carousel_item": "true",
    })["id"]


def ig_create_carousel(children_ids: list[str], caption: str) -> str:
    """Create carousel container. Returns container ID."""
    return _ig_post(f"{IG_USER_ID}/media", {
        "media_type": "CAROUSEL",
        "children"  : ",".join(children_ids),
        "caption"   : caption,
    })["id"]


def ig_wait_ready(container_id: str, retries=12, delay=6) -> bool:
    for attempt in range(retries):
        resp = requests.get(
            f"https://graph.facebook.com/v19.0/{container_id}",
            params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
            timeout=15,
        )
        status = resp.json().get("status_code", "")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} errored")
        print(f"     ⏳ Status: {status} (attempt {attempt+1}/{retries})")
        time.sleep(delay)
    return False


def ig_publish(container_id: str) -> str:
    """Publish container. Returns published media ID."""
    return _ig_post(f"{IG_USER_ID}/media_publish", {
        "creation_id": container_id,
    })["id"]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Post one carousel
# ─────────────────────────────────────────────────────────────────────────────

def post_carousel(urls: list[str], part_num: int, story_start: int, story_end: int) -> str:
    """
    Upload one carousel (8 slides) to Instagram and publish it.
    Returns published media ID.
    """
    if part_num == 1:
        caption = (
            f"📰 Top21News — {DATE_STR}\n\n"
            f"Today's 21 top stories — swipe to read each one 👉\n\n"
            f"Part {part_num}/3  ·  Stories {story_start}–{story_end}\n\n"
            f"{HASHTAGS}"
        )
    else:
        caption = (
            f"📰 Top21News — {DATE_STR}\n"
            f"Part {part_num}/3  ·  Stories {story_start}–{story_end}\n\n"
            f"{HASHTAGS}"
        )

    print(f"  Creating {len(urls)} carousel item containers…")
    children_ids = []
    for url in urls:
        cid = ig_create_item(url)
        children_ids.append(cid)
        print(f"     Item: {cid}")
        time.sleep(2)

    print(f"  Creating carousel container…")
    carousel_id = ig_create_carousel(children_ids, caption)
    print(f"  Container: {carousel_id}")

    print(f"  Waiting for Instagram to process…")
    time.sleep(10)
    ig_wait_ready(carousel_id)

    print(f"  Publishing…")
    post_id = ig_publish(carousel_id)
    print(f"  ✅ Published! Media ID: {post_id}")
    return post_id


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n🗞️  Top21News Daily Pipeline — {DATE_STR}")
    print("=" * 55)

    with tempfile.TemporaryDirectory() as work_dir:

        # 1. Fetch
        print("\n📡 Step 1 — Fetching 21 stories from Gemini…")
        news = fetch_news_gemini()

        # 2. Generate cards (grouped by post)
        print("\n🎨 Step 2 — Generating cards…")
        groups = generate_cards(news, work_dir)
        # groups = [[p1_cover, story1…story7], [p2_cover, story8…14], [p3_cover, story15…21]]

        # 3. Upload & post each group
        published = []
        for post_idx, group_paths in enumerate(groups):
            part_num    = post_idx + 1
            story_start = post_idx * STORIES_PER_POST + 1
            story_end   = story_start + STORIES_PER_POST - 1

            print(f"\n⬆️  Step 3.{part_num} — Uploading Part {part_num}/3…")
            urls = upload_group(group_paths)

            print(f"\n📲 Step 4.{part_num} — Posting Part {part_num}/3…")
            post_id = post_carousel(urls, part_num, story_start, story_end)
            published.append(post_id)

            if post_idx < TOTAL_POSTS - 1:
                print(f"\n  ⏸️  Waiting 45s before next post…")
                time.sleep(45)

    print(f"\n🎉 Done! {len(published)} posts published.")
    for i, pid in enumerate(published, 1):
        print(f"   Part {i}: https://www.instagram.com/p/{pid}/")


if __name__ == "__main__":
    main()
