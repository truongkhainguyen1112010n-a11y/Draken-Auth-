import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import base64
import re
import time
import urllib.parse
import os
import io
from urllib.parse import quote, unquote
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────

BOT_TOKEN             = os.environ.get("BOT_TOKEN",             "")
GITHUB_TOKEN          = os.environ.get("GITHUB_TOKEN",          "")
GITHUB_USER           = os.environ.get("GITHUB_USER",           "truongkhainguyen1112010n-a11y")
GITHUB_REPO           = os.environ.get("GITHUB_REPO",           "thumbnails.json")
GITHUB_FILE           = os.environ.get("GITHUB_FILE",           "thumbnails.json")
GITHUB_BRANCH         = os.environ.get("GITHUB_BRANCH",         "main")
GITHUB_JSON_FILE      = os.environ.get("GITHUB_JSON_FILE",      "thumbnails1.json")
GITHUB_EMOJI_FILE     = os.environ.get("GITHUB_EMOJI_FILE",     "emojis.lua")
GITHUB_TRAITS_FILE    = os.environ.get("GITHUB_TRAITS_FILE",    "traits.lua")
GITHUB_MUTATIONS_FILE = os.environ.get("GITHUB_MUTATIONS_FILE", "mutations.lua")
SCRAPER_API_KEY       = os.environ.get("SCRAPER_API_KEY",       "")
RAILWAY_PROXY         = os.environ.get("RAILWAY_PROXY",         "https://proxy-production-22ad.up.railway.app/img")
FANDOM_BASE           = "https://stealabrainrot.fandom.com/wiki/"
FLAGS_V2              = 32768
OWNER_ID              = 1498384419805986886
MAX_EMOJI_SLOTS       = 50   # Server without boost

def title_case(s: str) -> str:
    """Capitalize first letter of every word."""
    return ' '.join(w[0].upper() + w[1:] if w else w for w in s.split(' '))

# ── Bot Setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ── Owner Guard ───────────────────────────────────────────────────────────────

async def owner_check(interaction: discord.Interaction) -> bool:
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "Access Denied — This Command Is For The Owner Only.",
            ephemeral=True
        )
        return False
    return True

async def global_owner_check(interaction: discord.Interaction) -> bool:
    """Block ALL slash command interactions for non-owners at the tree level."""
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "Access Denied — This Bot Is Private.",
            ephemeral=True
        )
        return False
    return True

tree.interaction_check = global_owner_check

# ── UI Components ─────────────────────────────────────────────────────────────

def txt(content: str) -> dict:
    return {"type": 10, "content": content}

def sep() -> dict:
    return {"type": 14, "divider": True, "spacing": 1}

def sep_sm() -> dict:
    return {"type": 14, "divider": False, "spacing": 1}

def section(content: str, thumbnail_url: str) -> dict:
    return {
        "type": 9,
        "components": [{"type": 10, "content": content}],
        "accessory": {
            "type": 11,
            "media": {"url": thumbnail_url, "loading_state": 2},
            "spoiler": False,
        },
    }

def container(*items: dict) -> dict:
    return {"type": 17, "components": list(items)}

def action_row(*buttons: dict) -> dict:
    return {"type": 1, "components": list(buttons)}

def btn(label: str, custom_id: str, style: int = 2) -> dict:
    return {"type": 2, "style": style, "label": label, "custom_id": custom_id}

def btn_yes(custom_id: str) -> dict:
    return btn("Yes", custom_id, style=3)

def btn_no(custom_id: str) -> dict:
    return btn("No", custom_id, style=4)

def progress_bar(done: int, total: int, width: int = 20) -> str:
    pct    = done / total if total else 1
    filled = int(pct * width)
    return f"`[{'█' * filled}{'░' * (width - filled)}]` {done}/{total} ({int(pct * 100)}%)"

# ── Discord Helpers ───────────────────────────────────────────────────────────

def webhook_url(interaction: discord.Interaction) -> str:
    return f"https://discord.com/api/v10/webhooks/{interaction.application_id}/{interaction.token}"

async def send_v2(interaction: discord.Interaction, components: list[dict]):
    url = webhook_url(interaction)
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json={"flags": FLAGS_V2, "components": components}) as r:
            if r.status not in (200, 204):
                raise Exception(f"Discord {r.status}: {(await r.text())[:200]}")

async def followup(interaction: discord.Interaction, components: list[dict]):
    url     = f"https://discord.com/api/v10/webhooks/{interaction.application_id}/{interaction.token}"
    payload = {"flags": FLAGS_V2, "components": components}
    for _ in range(5):
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload) as r:
                if r.status in (200, 204):
                    return
                body = await r.text()
                if r.status == 429:
                    try:    retry_after = json.loads(body).get("retry_after", 1.5)
                    except: retry_after = 1.5
                    await asyncio.sleep(float(retry_after) + 0.2)
                    continue
                raise Exception(f"Discord {r.status}: {body[:200]}")
    raise Exception("Rate Limited  Max Retries Exceeded")

async def patch_msg(interaction: discord.Interaction, components: list[dict]):
    url = f"{webhook_url(interaction)}/messages/@original"
    async with aiohttp.ClientSession() as s:
        await s.patch(url, json={"flags": FLAGS_V2, "components": components})

# ── URL Helpers ───────────────────────────────────────────────────────────────

def is_railway(url: str) -> bool:
    return "up.railway.app" in url or "railway.app" in url

def is_cdn(url: str) -> bool:
    return "media.discordapp.net/attachments" in url or "cdn.discordapp.com/attachments" in url

def _clean_wikia_url(url: str) -> str:
    """Normalize Fandom/wikia URL to a clean static.wikia.nocookie.net URL."""
    url = re.sub(r'https?://vignette\d*\.wikia\.nocookie\.net', 'https://static.wikia.nocookie.net', url)
    url = re.sub(r'/scale-to-width-down/\d+', '', url)
    # Keep ?cb=... so Discord CDN caches correctly
    return url

def via_proxy(url: str) -> str:
    """Proxy any image URL through Railway with auto resize."""
    if not url: return url
    encoded = quote(url, safe='')
    return f"{RAILWAY_PROXY}?url={encoded}"

def extract_wikia_url(url: str) -> str | None:
    if is_railway(url) or is_cdn(url):
        return None
    if re.match(r'https?://(?:static|vignette\d*)\.wikia\.nocookie\.net', url):
        return _clean_wikia_url(url)
    decoded = url
    for _ in range(5):
        new = unquote(decoded)
        if new == decoded: break
        decoded = new
    m = re.search(r'/https/((?:static|vignette\d*)\.wikia\.nocookie\.net/[^\s?#]+)', decoded)
    if m: return _clean_wikia_url("https://" + m.group(1))
    m = re.search(r'(https?://(?:static|vignette\d*)\.wikia\.nocookie\.net/[^\s"\'<>?#]+)', decoded)
    if m: return _clean_wikia_url(m.group(1))
    return None

def to_railway(url: str) -> str:
    """Normalize and proxy the URL through Railway for proper thumbnail display."""
    if is_cdn(url): return url          # Discord CDN — keep as-is
    if is_railway(url):
        # Already proxied — extract inner URL and re-proxy with current config
        m = re.search(r'[?&]url=(.+)', url)
        if m:
            inner = unquote(m.group(1))
            return via_proxy(inner)
        return url
    wikia = extract_wikia_url(url)
    target = wikia if wikia else url
    return via_proxy(target)

def shorten(url: str, limit: int = 400) -> str:
    if len(url) > limit: url = url[:limit] + "..."
    return "\n".join(url[i:i+90] for i in range(0, len(url), 90))

# ── GitHub Helpers ────────────────────────────────────────────────────────────

def parse_lua(text: str) -> dict:
    data = {}
    for m in re.finditer(r'\["([^"\\]|\\.)*?"\]\s*=\s*"([^"\\]|\\.)*?"', text):
        raw = m.group(0)
        km  = re.match(r'\["((?:[^"\\]|\\.)*)"\]', raw)
        vm  = re.search(r'=\s*"((?:[^"\\]|\\.)*)"', raw)
        if km and vm:
            k = km.group(1).replace('\\"', '"').replace("\\\\", "\\")
            v = vm.group(1).replace('\\"', '"').replace("\\\\", "\\")
            data[k] = v
    return data

def to_lua(data: dict) -> str:
    max_len = max((len(k) for k in data), default=0)
    lines   = []
    for k, v in data.items():
        ek  = k.replace("\\", "\\\\").replace('"', '\\"')
        ev  = v.replace("\\", "\\\\").replace('"', '\\"')
        pad = " " * (max_len - len(k) + 1)
        lines.append('    ["' + ek + '"]' + pad + '= "' + ev + '",')
    return "\n".join(lines)

async def gh_fetch(filename: str) -> tuple[dict, str]:
    url     = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            if r.status == 404: return {}, ""
            if r.status != 200: raise Exception(f"GitHub {r.status}: {(await r.text())[:200]}")
            result  = await r.json()
            content = base64.b64decode(result["content"]).decode()
            try:    data = json.loads(content)
            except: data = parse_lua(content)
            return data, result["sha"]

async def gh_push(filename: str, data: dict, sha: str, msg: str):
    sorted_data = dict(sorted(data.items(), key=lambda x: x[0].lower()))
    url     = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
    }
    # Always re-fetch latest SHA to avoid 409 conflicts
    fresh_sha = await _gh_latest_sha(filename, headers)
    encoded   = base64.b64encode(to_lua(sorted_data).encode()).decode()
    body      = {"message": msg, "content": encoded, "branch": GITHUB_BRANCH}
    if fresh_sha or sha:                     # Only Send SHA When File Already Exists
        body["sha"] = fresh_sha or sha
    async with aiohttp.ClientSession() as s:
        async with s.put(url, headers=headers, json=body) as r:
            if r.status not in (200, 201):
                raise Exception(f"GitHub Push {r.status}: {(await r.text())[:300]}")

# ── Pet GitHub ────────────────────────────────────────────────────────────────

async def fetch_pets() -> tuple[dict, str]:
    url     = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}?ref={GITHUB_BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            if r.status == 404: return {}, ""          # File Does Not Exist — Will Be Created On Push
            if r.status != 200: raise Exception(f"GitHub {r.status}: {(await r.text())[:200]}")
            result  = await r.json()
            content = base64.b64decode(result["content"]).decode()
            try:    data = json.loads(content)
            except: data = parse_lua(content)
            return data, result["sha"]

async def _gh_latest_sha(filename: str, headers: dict) -> str:
    """Always fetch the latest SHA for a file to avoid 409 conflicts."""
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            if r.status == 200:
                return (await r.json()).get("sha", "")
            return ""

def _encode_for_file(filename: str, data: dict) -> str:
    """Encode data as JSON for .json files, Lua table for .lua files."""
    if filename.endswith(".json"):
        return base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
    return base64.b64encode(to_lua(data).encode()).decode()

async def push_pets(data: dict, sha: str, msg: str):
    sorted_data = dict(sorted(data.items(), key=lambda x: x[0].lower()))
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
    }

    async def _push_file(filename: str):
        fresh_sha = await _gh_latest_sha(filename, headers)
        url       = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}"
        encoded   = _encode_for_file(filename, sorted_data)
        body      = {"message": msg, "content": encoded, "branch": GITHUB_BRANCH}
        if fresh_sha:                        # Only Send SHA When File Already Exists
            body["sha"] = fresh_sha
        async with aiohttp.ClientSession() as s:
            async with s.put(url, headers=headers, json=body) as r:
                if r.status not in (200, 201):
                    raise Exception(f"GitHub Push [{filename}] {r.status}: {(await r.text())[:300]}")

    # Push both files (thumbnails.json as JSON, thumbnails1.json as JSON)
    await _push_file(GITHUB_FILE)
    await _push_file(GITHUB_JSON_FILE)


# ── Wiki Scrapers ─────────────────────────────────────────────────────────────

async def scrape_pet_image(pet_name: str) -> tuple[str | None, str]:
    slug     = pet_name.replace(" ", "_")
    page_url = f"https://stealabrainrot.fandom.com/wiki/{urllib.parse.quote(slug)}"
    debug    = []
    timeout  = aiohttp.ClientTimeout(total=40)
    async with aiohttp.ClientSession() as session:
        try:
            hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"}
            async with session.get(page_url, headers=hdrs, timeout=timeout) as r:
                body = await r.text()
                debug.append(f"Direct {r.status}")
                if r.status == 200 and "<!DOCTYPE" in body: html = body
                else: raise Exception(f"Blocked ({r.status})")
        except Exception as e:
            debug.append(f"Fallback  ScraperAPI")
            async with session.get(
                "https://api.scraperapi.com",
                params={"api_key": SCRAPER_API_KEY, "url": page_url, "render": "false"},
                timeout=timeout,
            ) as r:
                body = await r.text()
                if r.status != 200: return None, "\n".join(debug)
                html = body
        m = re.search(r'<meta property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
        if not m: m = re.search(r'<meta content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html)
        if m:
            img_url = m.group(1)
            if "wikia.nocookie.net" in img_url:
                return _clean_wikia_url(img_url), "\n".join(debug)
        imgs = re.findall(r'https://static\.wikia\.nocookie\.net/[^"\'.\s<>]+\.(?:png|jpg|webp)', html)
        imgs = [u for u in imgs if not any(x in u.lower() for x in ["icon","logo","favicon","placeholder","wordmark","fandom-heart"])]
        if imgs: return re.sub(r'/revision/latest.*', '', imgs[0]), "\n".join(debug)
        debug.append("No Image Found.")
    return None, "\n".join(debug)

def _best_wikia_img(cell_html: str) -> str | None:
    for attr in ('data-src', 'data-image-key', 'src'):
        for m in re.finditer(rf'{attr}=["\'"]([^"\'"]+)["\'"]', cell_html, re.IGNORECASE):
            url = m.group(1)
            if "wikia.nocookie.net" in url and "placeholder" not in url.lower():
                return to_railway(_clean_wikia_url(url))
    return None

async def _scrape_wiki_table(page_url: str) -> list[tuple[str, str | None]]:
    timeout = aiohttp.ClientTimeout(total=40)
    hdrs    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(page_url, headers=hdrs, timeout=timeout) as r:
                if r.status == 200 and "<!DOCTYPE" in (body := await r.text()): html = body
                else: raise Exception(f"Blocked ({r.status})")
        except Exception:
            async with session.get(
                "https://api.scraperapi.com",
                params={"api_key": SCRAPER_API_KEY, "url": page_url, "render": "false"},
                timeout=timeout,
            ) as r:
                if r.status != 200: return []
                html = await r.text()

    def clean(s): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s)).strip()

    NAME_COL = 1
    ICON_COL = 3
    row_pat  = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    td_pat   = re.compile(r'<td[^>]*>(.*?)</td>',  re.DOTALL | re.IGNORECASE)
    th_pat   = re.compile(r'<th[^>]*>(.*?)</th>',  re.DOTALL | re.IGNORECASE)

    entries    = []
    seen_names = set()

    for row_m in row_pat.finditer(html):
        row_html = row_m.group(1)
        ths = th_pat.findall(row_html)
        if ths:
            headers = [clean(h).lower() for h in ths]
            for i, h in enumerate(headers):
                if h == 'name': NAME_COL = i
                if h in ('icon', 'image', 'img'): ICON_COL = i
            continue
        cells = td_pat.findall(row_html)
        if len(cells) <= max(NAME_COL, ICON_COL): continue
        name = clean(cells[NAME_COL])
        if not name or name.lower() in ('name', 'multi', 'icon', 'image', 'rarity', 'effect', 'description', ''): continue
        if name in seen_names: continue
        seen_names.add(name)
        thumb = _best_wikia_img(cells[ICON_COL])
        if not thumb:
            for cell in cells:
                thumb = _best_wikia_img(cell)
                if thumb: break
        if not thumb:
            all_wikia = re.findall(r'https://static\.wikia\.nocookie\.net/[^"\'>\s]+\.(?:png|jpg|webp|gif)', row_html, re.IGNORECASE)
            for u in all_wikia:
                if not any(x in u.lower() for x in ['placeholder','wordmark','fandom','favicon']):
                    thumb = to_railway(re.sub(r'/revision/latest.*', '', u).split('?')[0])
                    break
        entries.append((name, thumb))

    return entries

async def scrape_mutations() -> list[tuple[str, str | None]]:
    return await _scrape_wiki_table("https://stealabrainrot.fandom.com/wiki/Mutations")

async def scrape_traits() -> list[tuple[str, str | None]]:
    return await _scrape_wiki_table("https://stealabrainrot.fandom.com/wiki/Traits")

async def scrape_category_brainrots() -> list[tuple[str, str | None]]:
    """
    Scrape ALL brainrot names + images directly from Category:Listed_Brainrots.
    Images are grabbed from category thumbnails  no need to visit each page.
    Handles pagination via ?from= query param with visited-URL dedup.
    """
    BASE_URL  = "https://stealabrainrot.fandom.com"
    start_url = BASE_URL + "/wiki/Category:Listed_Brainrots"
    timeout   = aiohttp.ClientTimeout(total=40)
    hdrs      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"}

    LI_PAT   = re.compile('<li class="category-page__member">(.*?)</li>', re.DOTALL)
    NAME_PAT = re.compile('class="category-page__member-link"[^>]*>([^<]+)<')
    SRC_PAT  = re.compile(r'\bsrc=["\'](https://static\.wikia\.nocookie\.net/[^"\']+)["\'"]')
    NEXT_PAT = re.compile(r'href=["\'](/wiki/Category:Listed_Brainrots[?]from=[^"\']+)["\']')

    all_results:  list[tuple[str, str | None]] = []
    seen_names:   set[str] = set()
    visited_urls: set[str] = set()
    next_url: str | None   = start_url

    async with aiohttp.ClientSession() as session:
        while next_url and next_url not in visited_urls:
            visited_urls.add(next_url)
            html: str | None = None

            try:
                async with session.get(next_url, headers=hdrs, timeout=timeout) as r:
                    if r.status == 200 and "<!DOCTYPE" in (body := await r.text()):
                        html = body
                    else:
                        raise Exception(f"HTTP {r.status}")
            except Exception:
                try:
                    async with session.get(
                        "https://api.scraperapi.com",
                        params={"api_key": SCRAPER_API_KEY, "url": next_url, "render": "false"},
                        timeout=timeout,
                    ) as r:
                        if r.status == 200:
                            html = await r.text()
                except Exception:
                    pass

            if not html:
                break

            for li in LI_PAT.finditer(html):
                block = li.group(1)

                nm = NAME_PAT.search(block)
                name = nm.group(1).strip() if nm else None
                if not name:
                    t = re.search('title="([^"]+)"', block)
                    name = t.group(1) if t else None
                if not name or name in seen_names:
                    continue
                seen_names.add(name)

                # Image is in src= before <noscript>  thumbnail on category page
                ns_idx = block.find("<noscript>")
                look   = block[:ns_idx] if ns_idx > 0 else block
                im     = SRC_PAT.search(look)
                if im:
                    img_url = to_railway(_clean_wikia_url(im.group(1)))
                else:
                    img_url = None

                all_results.append((name, img_url))

            nm = NEXT_PAT.search(html)
            if nm:
                next_url = BASE_URL + nm.group(1).replace("&amp;", "&")
            else:
                next_url = None

    return all_results
# ── Image Processing ──────────────────────────────────────────────────────────

async def download_and_resize(url: str, session: aiohttp.ClientSession) -> bytes | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200: return None
            raw = await r.read()
    except Exception: return None
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img = img.resize((256, 256), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        data = buf.getvalue()
        return data if len(data) <= 256_000 else None
    except Exception: return None

def sanitize_name(name: str) -> str:
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    clean = re.sub(r'_+', '_', clean).strip('_')
    if len(clean) < 2: clean = clean + '_e'
    return clean[:32]

async def upload_emoji(guild_id: int, bot_token: str, name: str, image_bytes: bytes, session: aiohttp.ClientSession) -> tuple[dict | None, str]:
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n': mime = "image/png"
    elif image_bytes[:3] == b'GIF':             mime = "image/gif"
    else:                                        mime = "image/jpeg"
    b64     = base64.b64encode(image_bytes).decode()
    payload = {"name": name, "image": f"data:{mime};base64,{b64}"}
    url     = f"https://discord.com/api/v10/guilds/{guild_id}/emojis"
    headers = {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
    for _ in range(4):
        async with session.post(url, json=payload, headers=headers) as r:
            if r.status in (200, 201): return await r.json(), ""
            body = await r.text()
            if r.status == 429:
                try:    retry_after = json.loads(body).get("retry_after", 2.0)
                except: retry_after = 2.0
                await asyncio.sleep(float(retry_after) + 0.5)
                continue
            try:
                err_json = json.loads(body)
                err_msg  = err_json.get("message", body[:100])
                if r.status == 400:
                    if "File cannot be larger" in err_msg or "2048" in err_msg: err_msg = "Image Too Large (>256KB After Resize)"
                    elif "Invalid image" in err_msg:                             err_msg = "Invalid Image Format"
                    elif "Maximum number" in err_msg:                            err_msg = "SERVER_FULL"
                    elif "Invalid Form Body" in err_msg:
                        details = err_json.get("errors", {})
                        err_msg = f"Form Error: {str(details)[:80]}"
                elif r.status in (401, 403): err_msg = f"No Permission ({r.status})  Bot Needs Manage Emojis"
                else:                        err_msg = f"HTTP {r.status}: {err_msg}"
            except Exception: err_msg = f"HTTP {r.status}: {body[:100]}"
            return None, err_msg
    return None, "Rate Limited  Max Retries"

def parse_emoji_input(raw: str) -> dict[str, str]:
    result = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line: continue
        m = re.search(r'<:([A-Za-z0-9_]+):(\d+)>', line)
        if m:
            result[m.group(1)] = f"<:{m.group(1)}:{m.group(2)}>"
            continue
        m = re.match(r'^([A-Za-z0-9_ ]+?)\s*:\s*(\d{10,25})$', line)
        if m:
            name = m.group(1).strip()
            result[name] = f"<:{name}:{m.group(2)}>"
    return result

# ══════════════════════════════════  COMMANDS  ══════════════════════════════════

# ── /Ping ─────────────────────────────────────────────────────────────────────

@tree.command(name="ping", description="Check The Bot's Latency And Connection Status.")
@discord.app_commands.default_permissions(administrator=True)
async def ping(interaction: discord.Interaction):
    start = time.monotonic()
    await interaction.response.defer(thinking=True)
    latency_ms = round((time.monotonic() - start) * 1000)
    ws_ms      = round(bot.latency * 1000)
    status     = "Excellent" if ws_ms < 80 else "Normal" if ws_ms < 150 else "Slow"
    await send_v2(interaction, [container(
        txt("## Pong"), sep(),
        txt(f"**Websocket Latency:** `{ws_ms}ms`\n**Response Time:** `{latency_ms}ms`\n**Status:** {status}"),
    )])

# ── /Addpet ───────────────────────────────────────────────────────────────────

@tree.command(name="addpet", description="Add A New Pet With Its Thumbnail URL To GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def addpet(interaction: discord.Interaction, name: str, url: str):
    await interaction.response.defer(thinking=True)
    converted = to_railway(url)
    label     = "Railway Proxy - Converted" if converted != url else "Discord CDN - Kept As-Is"
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Add Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))])
        return
    if name in data:
        exist = data[name]
        await send_v2(interaction, [container(
            txt("## Pet Already Exists"), sep(),
            section(f"**{name}**\n\n Already In GitHub!\n\n**Current URL**\n```\n{shorten(exist, 240)}\n```", exist),
            sep(), txt(f"Use `/updatepet` To Change The URL.\n**New URL You Tried:**\n```\n{shorten(converted, 240)}\n```"),
        )])
        return
    try:
        data[name] = converted
        await push_pets(data, sha, f"[DK] Added: {name}")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if ok:
        label_text = "Railway Proxy - Converted" if converted != url else "Discord CDN - Kept As-Is"
        await send_v2(interaction, [container(txt("## Pet Added Successfully"), sep(), section(f"**{title_case(name)}**\n\n{label_text}\n```\n{shorten(converted)}\n```", converted), sep(), txt("**GitHub**  Pushed & Sorted A To Z"))])
    else:
        await send_v2(interaction, [container(txt("## Failed To Add Pet"), sep(), txt(f"**Pet:** `{name}`\n\n**GitHub**  Push Failed\n```\n{err[:200]}\n```"))])

# ── /Updatepet ────────────────────────────────────────────────────────────────

@tree.command(name="updatepet", description="Update The Thumbnail URL Of An Existing Pet.")
@discord.app_commands.default_permissions(administrator=True)
async def updatepet(interaction: discord.Interaction, name: str, url: str):
    await interaction.response.defer(thinking=True)
    converted = to_railway(url)
    label     = "Railway Proxy - Converted" if converted != url else "Discord CDN - Kept As-Is"
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Update Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))])
        return
    if name not in data:
        suggestions = [k for k in data if name.lower() in k.lower()]
        items = [txt(f"## Pet Not Found\n**Pet:** `{name}`")]
        if suggestions: items += [sep(), txt("**Similar Pets:**\n" + "\n".join(f" `{s}`" for s in suggestions[:8]))]
        await send_v2(interaction, [container(*items)]); return
    old_url = data[name]
    try:
        data[name] = converted
        await push_pets(data, sha, f"[DK] Updated: {name}")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if ok:
        await send_v2(interaction, [container(txt("## Pet Updated Successfully"), sep(), section(f"**{name}**\n\n{label}\n```\n{shorten(converted, 240)}\n```", converted), sep(), txt(f"**Previous URL:**\n```\n{shorten(old_url, 200)}\n```"), sep(), txt("**GitHub**  Pushed & Sorted A To Z"))])
    else:
        await send_v2(interaction, [container(txt("## Failed To Update Pet"), sep(), txt(f"**Pet:** `{name}`\n\n **GitHub**   Push Failed\n```\n{err[:200]}\n```"))])

# ── /Deletepet ────────────────────────────────────────────────────────────────

@tree.command(name="deletepet", description="Delete A Pet And Its Thumbnail URL From GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def deletepet(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Delete Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))])
        return
    if name not in data:
        suggestions = [k for k in data if name.lower() in k.lower()]
        items = [txt(f"##  Pet Not Found\n**Pet:** `{name}`")]
        if suggestions: items += [sep(), txt("**Similar Pets:**\n" + "\n".join(f" `{s}`" for s in suggestions[:8]))]
        await send_v2(interaction, [container(*items)]); return
    deleted_url = data[name]
    wh_url      = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [
            container(
                txt("## Confirm Delete Pet"), sep(),
                section(f"**{name}**\n\n Are You Sure You Want To Delete This Pet?\n\n**URL:**\n```\n{shorten(deleted_url, 200)}\n```", deleted_url),
                action_row(btn_yes(f"delpet_yes:{name}"), btn_no("delpet_no")),
            ),
        ],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
    bot._delpet_pending = getattr(bot, "_delpet_pending", {})
    bot._delpet_pending[name] = {"data": data, "sha": sha, "url": deleted_url}

# ── /Getpet ───────────────────────────────────────────────────────────────────

@tree.command(name="getpet", description="Get The Thumbnail URL Of A Specific Pet.")
@discord.app_commands.default_permissions(administrator=True)
async def getpet(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    try:
        data, _ = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Get Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))]); return
    if name not in data:
        suggestions = [k for k in data if name.lower() in k.lower()]
        items = [txt(f"##  Pet Not Found\n**Pet:** `{name}`")]
        if suggestions: items += [sep(), txt("** Did You Mean:**\n" + "\n".join(f" `{s}`" for s in suggestions[:5]))]
        await send_v2(interaction, [container(*items)]); return
    url_val = data[name]
    await send_v2(interaction, [container(txt("## Pet Thumbnail"), sep(), section(f"**{name}**\n\n**URL:**\n```\n{shorten(url_val)}\n```", url_val))])

# ── /Searchpet ────────────────────────────────────────────────────────────────

@tree.command(name="searchpet", description="Search For Pets By Name Or Keyword.")
@discord.app_commands.default_permissions(administrator=True)
async def searchpet(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    try:
        data, _ = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Search Pets\n **Query:** `{query}`\n\n**Error:**\n```\n{e}\n```"))]); return
    matches = sorted([k for k in data if query.lower() in k.lower()])
    if not matches:
        await send_v2(interaction, [container(txt(f"## No Results Found\n **Query:** `{query}`"))]); return
    top     = matches[0]
    top_url = data[top]
    items   = [txt(f"## Search Results For `{query}`"), sep(), section(f"**Top Match:** `{top}`\n\n**URL:**\n```\n{shorten(top_url, 240)}\n```", top_url)]
    if len(matches) > 1:
        items += [sep(), txt(f"**Other Matches ({len(matches)-1}):**\n" + "\n".join(f" `{m}`" for m in matches[1:26]))]
    items += [sep(), txt(f"**Total Matches:** {len(matches)} / {len(data)} Pets")]
    await send_v2(interaction, [container(*items)])

# ── /Listpets ─────────────────────────────────────────────────────────────────

@tree.command(name="listpets", description="List All Pets And Their Thumbnails Stored In GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def listpets(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        data, _ = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** List Pets\n\n**Error:**\n```\n{e}\n```"))]); return
    railway_count = sum(1 for v in data.values() if is_railway(v))
    cdn_count     = sum(1 for v in data.values() if is_cdn(v))
    other_count   = len(data) - railway_count - cdn_count
    pet_names     = sorted(data.keys(), key=lambda x: x.lower())
    await followup(interaction, [container(
        txt("## Full Pet List"), sep(),
        txt(f"**Total Pets:** {len(data)}    **Railway:** {railway_count}    **CDN:** {cdn_count}    **Other:** {other_count}"),
        sep_sm(), txt("**All Pets (A To Z)  Loading Thumbnails Below...**"),
    )])
    for i in range(0, len(pet_names), 5):
        chunk = pet_names[i:i+5]
        items = [txt(f"**Pets ({i+1}{i+len(chunk)}):**")]
        for j, pname in enumerate(chunk):
            if j > 0: items.append(sep())
            items.append(section(f"**{pname}**", data[pname]))
        await followup(interaction, [container(*items)])
        await asyncio.sleep(0.8)
    await followup(interaction, [container(txt(f"**Done  {len(pet_names)} Pets Listed.**"))])

# ── /Fetchpet ─────────────────────────────────────────────────────────────────

@tree.command(name="fetchpet", description="Auto-Fetch A Pet's Image From The Fandom Wiki And Save It.")
@discord.app_commands.default_permissions(administrator=True)
async def fetchpet(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    try:
        wikia_url, debug_info = await scrape_pet_image(name)
    except Exception as e:
        await send_v2(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Pet:** `{name}`\n\n**Exception:**\n```\n{e}\n```"))]); return
    if not wikia_url:
        page_url = FANDOM_BASE + quote(name.replace(" ", "_"))
        await send_v2(interaction, [container(txt("## Image Not Found On Wiki"), sep(), txt(f"**Pet:** `{name}`\n\n No Image Found On The Wiki Page.\n\n**Page Checked:**\n```\n{page_url}\n```\n\n**Debug Info:**\n```\n{debug_info[:600]}\n```"))]); return
    railway_url = to_railway(wikia_url)
    short_url   = shorten(railway_url)
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Fetch Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))]); return
    if name in data:
        existing_url = data[name]
        wh_url       = webhook_url(interaction)
        payload = {
            "flags": FLAGS_V2,
            "components": [
                container(
                    txt("## Pet Already Exists"), sep(),
                    section(f"**{name}**\n\nAlready In GitHub  Overwrite?\n\n**Current URL:**\n```\n{shorten(existing_url)}\n```\n\n**Fetched URL:**\n```\n{short_url}\n```", existing_url),
                    action_row(btn_yes(f"overwrite_yes:{name}"), btn_no(f"overwrite_no:{name}")),
                ),
            ],
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(wh_url, json=payload) as r:
                if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
        bot._fetchpet_pending       = getattr(bot, "_fetchpet_pending", {})
        bot._fetchpet_pending[name] = {"railway_url": railway_url, "data": data, "sha": sha}
        return
    try:
        data[name] = railway_url
        await push_pets(data, sha, f"[DK] Auto-Fetch Added: {name}")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if ok:
        await send_v2(interaction, [container(txt("## Pet Image Added Successfully"), sep(), section(f"**{name}**\n\n**Railway URL:**\n```\n{short_url}\n```", railway_url), sep(), txt("**GitHub**  Pushed & Sorted A To Z"))])
    else:
        await send_v2(interaction, [container(txt("## Failed To Save Pet"), sep(), txt(f"**Pet:** `{name}`\n\n **GitHub**   Push Failed\n```\n{err[:200]}\n```"))])

# ── /Syncpets ─────────────────────────────────────────────────────────────────

@tree.command(name="syncpets", description="Sync All Pet URLs To Railway Proxy Format.")
@discord.app_commands.default_permissions(administrator=True)
async def syncpets(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Sync Pets\n\n**Error:**\n```\n{e}\n```"))]); return
    to_convert = {n: u for n, u in data.items() if not is_railway(u) and extract_wikia_url(u)}
    to_refetch = {n: u for n, u in data.items() if not is_railway(u) and not extract_wikia_url(u)}
    needs_sync = {**to_convert, **to_refetch}
    if not needs_sync:
        await send_v2(interaction, [container(txt("## Already Fully Synced"), sep(), txt(f"**Total Pets:** {len(data)}\n\nAll URLs Are Already On Railway! Nothing To Sync."))]); return
    preview_lines = "\n".join(f" `{n}`{' (Re-Fetch)' if n in to_refetch else ''}" for n in sorted(needs_sync.keys())[:10])
    more_note     = f"\n*...And {len(needs_sync)-10} More*" if len(needs_sync) > 10 else ""
    wh_url        = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [
            container(
                txt("## Sync Pets"), sep(),
                txt(f"**Total Pets:** {len(data)}\n**Found {len(needs_sync)} Pet(s) Not Synced:**\n\n{preview_lines}{more_note}\n\nConvert All?"),
                action_row(btn_yes("syncpets_yes"), btn_no("syncpets_no")),
            ),
        ],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
    bot._syncpets_pending = getattr(bot, "_syncpets_pending", {})
    bot._syncpets_pending["latest"] = {"data": data, "sha": sha, "to_convert": to_convert, "to_refetch": to_refetch}

# ── /Scrapeallbrainrots ───────────────────────────────────────────────────────

@tree.command(name="scrapeallbrainrots", description="Auto-Scrape All Brainrots From Category:Listed_Brainrots And Save To GitHub.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(skip_existing="Skip Brainrots Already In GitHub (Default: True)", dry_run="Preview Only — Do Not Save To GitHub")
async def scrapeallbrainrots(
    interaction: discord.Interaction,
    skip_existing: bool = True,
    dry_run: bool = False,
):
    await interaction.response.defer(thinking=True)

    await followup(interaction, [container(
        txt("## Scraping Category: Listed Brainrots..."),
        sep(),
        txt(
            f"Fetching All Brainrots From `stealabrainrot.fandom.com/wiki/Category:Listed_Brainrots`\n\n"
            f"This May Take A Few Minutes — Each Brainrot Will Be Scraped For Its Image.\n\n"
            f"**Options:** Skip Existing = `{skip_existing}` | Dry Run = `{dry_run}`"
        ),
    )])

    # Load current GitHub data
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await followup(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    # Scrape the category
    try:
        all_brainrots = await scrape_category_brainrots()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    if not all_brainrots:
        await followup(interaction, [container(
            txt("## No Brainrots Found"),
            sep(),
            txt("No Brainrots Found On The Category Page.\n\nThe Page Layout May Have Changed Or The Wiki Is Blocking Requests."),
        )]); return

    # Filter
    to_add   = [(n, u) for n, u in all_brainrots if n not in data]
    existing = [(n, u) for n, u in all_brainrots if n in data]

    await followup(interaction, [container(
        txt("## Category Scan Complete"),
        sep(),
        txt(
            f"**Total Found On Wiki:** {len(all_brainrots)}\n"
            f"**Already In GitHub:** {len(existing)}\n"
            f"**New (Will Add):** {len(to_add)}\n\n"
            + (f"Dry Run  Nothing Will Be Saved." if dry_run else
               f"Saving {len(to_add)} New Brainrots To GitHub..." if to_add else
               f"All Brainrots Already In GitHub  Nothing New!")
        ),
    )])

    if not to_add:
        await followup(interaction, [container(txt("## Nothing New"), sep(), txt(f"All {len(all_brainrots)} Brainrots From The Category Are Already Saved In GitHub."))])
        return

    if dry_run:
        preview = "\n".join(f" `{n}`{' - Has Image' if u else ' - No Image'}" for n, u in to_add[:30])
        more    = f"\n*...And {len(to_add)-30} More*" if len(to_add) > 30 else ""
        await followup(interaction, [container(
            txt("## Dry Run  Preview New Brainrots"),
            sep(),
            txt(f"**{len(to_add)} New Brainrots Will Be Added:**\n\n{preview}{more}"),
        )])
        return

    # Save to GitHub  track recent adds for live display
    added_ok:    list[str] = []
    no_image:    list[str] = []
    recent_done: list[str] = []   # last few added names (for live log)

    def _build_progress_msg(i: int, cur_name: str) -> list[dict]:
        bar      = progress_bar(i, len(to_add))
        done_log = "\n".join(f" `{n}`" for n in recent_done[-8:]) if recent_done else "*(None Yet...)*"
        return [container(
            txt("## Adding Brainrots..."),
            sep(),
            txt(
                f"**Progress:** {bar}\n"
                f"**Processing:** `{cur_name}`\n\n"
                f"**Recently Added:**\n{done_log}"
            ),
        )]

    # Send initial progress message (will be patched in-place)
    await followup(interaction, _build_progress_msg(0, to_add[0][0] if to_add else "..."))

    for i, (name, img_url) in enumerate(to_add):
        # Patch the SAME message every item for live progress
        await patch_msg(interaction, _build_progress_msg(i, name))

        final_url: str | None = None
        if img_url:
            final_url = img_url
        else:
            try:
                wikia_url, _ = await scrape_pet_image(name)
                if wikia_url:
                    final_url = to_railway(wikia_url)
            except Exception:
                final_url = None

        if final_url:
            data[name]  = final_url
            added_ok.append(name)
            recent_done.append(title_case(name))
        else:
            data[name] = ""
            no_image.append(name)

        # Per-item notification (channel message)
        await asyncio.sleep(0.15)

    # Final patch to show 100%
    await patch_msg(interaction, [container(
        txt("## Pushing To GitHub..."),
        sep(),
        txt(f"**Progress:** {progress_bar(len(to_add), len(to_add))}\n**Processed:** {len(to_add)} Brainrots  Saving..."),
    )])

    # Push once at the end
    try:
        await push_pets(data, sha, f"[DK] ScrapeAll: Added {len(added_ok)} Brainrots From Category")
        push_ok = True
    except Exception as pe:
        push_ok = False; push_err = str(pe)

    if push_ok:
        all_added_log = "\n".join(f" `{title_case(n)}`" for n in added_ok[:25])
        more_added    = f"\n*...And {len(added_ok)-25} More*" if len(added_ok) > 25 else ""
        no_img_txt    = (
            f"\n\n**{len(no_image)} Without Image:**\n"
            + "\n".join(f" `{title_case(n)}`" for n in no_image[:10])
        ) if no_image else ""
        await followup(interaction, [container(
            txt("## Scrape All Brainrots  Done!"),
            sep(),
            txt(
                f"**Total On Wiki:** {len(all_brainrots)}\n"
                f"**Added:** {len(added_ok)}\n"
                f"**Skipped (Already Exists):** {len(existing)}\n"
                f"**No Image:** {len(no_image)}\n\n"
                f"**Brainrots Added:**\n{all_added_log}{more_added}"
                f"{no_img_txt}\n\n"
                f"**GitHub**  Pushed & Sorted A To Z"
            ),
        )])
    else:
        await followup(interaction, [container(txt("## GitHub Push Failed"), sep(), txt(f"**Error:**\n```\n{push_err[:300]}\n```"))])

# ── /Listmutations ────────────────────────────────────────────────────────────

@tree.command(name="listmutations", description="Scrape & List All Mutations From The Fandom Wiki With Thumbnails.")
@discord.app_commands.default_permissions(administrator=True)
async def listmutations(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await followup(interaction, [container(txt("##  Scanning Mutations Wiki Page..."), sep(), txt(" Scraping `stealabrainrot.fandom.com/wiki/Mutations`  Please Wait..."))])
    try:
        mutations = await scrape_mutations()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not mutations:
        await followup(interaction, [container(txt("## No Mutations Found"), sep(), txt("Could Not Find Any Mutations On The Wiki Page.\n\n The Page Layout May Have Changed."))]); return
    with_thumb = sum(1 for _, u in mutations if u)
    await followup(interaction, [container(txt("##  Mutations List"), sep(), txt(f"**Total:** {len(mutations)}    **With Thumbnail:** {with_thumb}    **No Image:** {len(mutations)-with_thumb}\n\n **Loading All Below...**"))])
    for i in range(0, len(mutations), 5):
        chunk = mutations[i:i+5]
        items = [txt(f"**Mutations ({i+1}{i+len(chunk)}):**")]
        for j, (name, thumb) in enumerate(chunk):
            if j > 0: items.append(sep())
            items.append(section(f"**{name}**", thumb) if thumb else txt(f"**{name}**  *(No Image Found)*"))
        await followup(interaction, [container(*items)])
        await asyncio.sleep(0.8)
    name_lines = "\n".join(f"`{i+1}.` **{name}**" for i, (name, _) in enumerate(mutations))
    await followup(interaction, [container(txt("## All Mutations  Quick Reference"), sep(), txt(f"**{len(mutations)} Mutations (Wiki Order):**\n\n{name_lines}"))])

# ── /Listtraits ───────────────────────────────────────────────────────────────

@tree.command(name="listtraits", description="Scrape & List All Traits From The Fandom Wiki With Thumbnails.")
@discord.app_commands.default_permissions(administrator=True)
async def listtraits(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await followup(interaction, [container(txt("## Scanning Traits Wiki Page..."), sep(), txt(" Scraping `stealabrainrot.fandom.com/wiki/Traits`  Please Wait..."))])
    try:
        traits = await scrape_traits()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not traits:
        await followup(interaction, [container(txt("## No Traits Found"), sep(), txt("Could Not Find Any Traits On The Wiki Page.\n\n The Page Layout May Have Changed."))]); return
    with_thumb = sum(1 for _, u in traits if u)
    await followup(interaction, [container(txt("## Traits List"), sep(), txt(f"**Total:** {len(traits)}    **With Thumbnail:** {with_thumb}    **No Image:** {len(traits)-with_thumb}\n\n **Loading All Below...**"))])
    for i in range(0, len(traits), 5):
        chunk = traits[i:i+5]
        items = [txt(f"**Traits ({i+1}{i+len(chunk)}):**")]
        for j, (name, thumb) in enumerate(chunk):
            if j > 0: items.append(sep())
            items.append(section(f"**{name}**", thumb) if thumb else txt(f"**{name}**  *(No Image Found)*"))
        await followup(interaction, [container(*items)])
        await asyncio.sleep(0.8)
    name_lines = "\n".join(f"`{i+1}.` **{name}**" for i, (name, _) in enumerate(traits))
    await followup(interaction, [container(txt("## All Traits  Quick Reference"), sep(), txt(f"**{len(traits)} Traits (Wiki Order):**\n\n{name_lines}"))])

# ── /Getemojis ────────────────────────────────────────────────────────────────

@tree.command(name="getemojis", description="Get All Trait & Mutation Names From Wiki With Emoji Mapping Status.")
@discord.app_commands.default_permissions(administrator=True)
async def getemojis(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await followup(interaction, [container(txt("## Scanning Wiki For Names..."), sep(), txt("Scraping Traits & Mutations Pages  Please Wait..."))])
    try:
        traits, mutations = await asyncio.gather(scrape_traits(), scrape_mutations())
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    try:
        existing_emojis, _ = await gh_fetch(GITHUB_EMOJI_FILE)
    except Exception:
        existing_emojis = {}
    trait_names    = [n for n, _ in traits]
    mutation_names = [n for n, _ in mutations]
    def status_lines(names):
        return "\n".join(
            f"`{'' if n in existing_emojis else ''}` **{n}**{f'    {existing_emojis[n]}' if n in existing_emojis else ''}"
            for n in names
        )
    mapped_t   = [n for n in trait_names    if n in existing_emojis]
    unmapped_t = [n for n in trait_names    if n not in existing_emojis]
    mapped_m   = [n for n in mutation_names if n in existing_emojis]
    unmapped_m = [n for n in mutation_names if n not in existing_emojis]
    await followup(interaction, [container(txt("## Traits  Emoji Status"), sep(), txt(f"**{len(trait_names)} Traits    Mapped: {len(mapped_t)}    Missing: {len(unmapped_t)}**\n\n{status_lines(trait_names)}\n\nMapped / Missing"))])
    await asyncio.sleep(0.5)
    await followup(interaction, [container(txt("## Mutations  Emoji Status"), sep(), txt(f"**{len(mutation_names)} Mutations    Mapped: {len(mapped_m)}    Missing: {len(unmapped_m)}**\n\n{status_lines(mutation_names)}\n\nMapped / Missing"))])
    await asyncio.sleep(0.5)
    if unmapped_t:
        await followup(interaction, [container(txt("## Unmapped Traits"), sep(), txt(f"**{len(unmapped_t)} Traits Still Need Emoji IDs:**\n\n```\n{chr(10).join(unmapped_t)[:1800]}\n```\n\nUse `/addemojis` To Bulk-Add."))])
        await asyncio.sleep(0.5)
    if unmapped_m:
        await followup(interaction, [container(txt("## Unmapped Mutations"), sep(), txt(f"**{len(unmapped_m)} Mutations Still Need Emoji IDs:**\n\n```\n{chr(10).join(unmapped_m)[:1800]}\n```\n\nUse `/addemojis` To Bulk-Add."))])
        await asyncio.sleep(0.5)
    total        = len(trait_names) + len(mutation_names)
    total_mapped = len(mapped_t) + len(mapped_m)
    await followup(interaction, [container(txt("## Summary"), sep(), txt(f"**Traits:** {len(trait_names)}  ( {len(mapped_t)} Mapped     {len(unmapped_t)} Missing)\n**Mutations:** {len(mutation_names)}  ( {len(mapped_m)} Mapped     {len(unmapped_m)} Missing)\n\n**Total Mapped:** {total_mapped}    **Total Unmapped:** {total-total_mapped}\n\n**GitHub File:** `{GITHUB_EMOJI_FILE}`"))])

# ── /Addemojis ────────────────────────────────────────────────────────────────

@tree.command(name="addemojis", description="Bulk-Add Trait/Mutation Emoji IDs  Saved To GitHub As Lua Table.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(emoji_data="Paste Lines Of  name:emoji_id  Or  <:name:id>  (One Per Line)")
async def addemojis(interaction: discord.Interaction, emoji_data: str):
    await interaction.response.defer(thinking=True)
    parsed = parse_emoji_input(emoji_data)
    if not parsed:
        await send_v2(interaction, [container(txt("## No Valid Emojis Parsed"), sep(), txt("**Accepted Formats (One Per Line):**\n```\nDefault:1498945977409863751\n<:Default:1498945977409863751>\n```"))]); return
    try:
        data, sha = await gh_fetch(GITHUB_EMOJI_FILE)
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Add Emojis\n\n**Error:**\n```\n{e}\n```"))]); return
    new_entries       = {k: v for k, v in parsed.items() if k not in data}
    overwrite_entries = {k: v for k, v in parsed.items() if k in data}
    data.update(parsed)
    try:
        await gh_push(GITHUB_EMOJI_FILE, data, sha, f"[DK] Emojis Added/Updated: {', '.join(list(parsed.keys())[:5])}")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if not ok:
        await send_v2(interaction, [container(txt("## Failed To Save Emojis"), sep(), txt(f" **GitHub**   Push Failed\n```\n{err[:200]}\n```"))]); return
    max_len     = max((len(k) for k in parsed), default=0)
    lua_lines   = []
    for k, v in sorted(parsed.items(), key=lambda x: x[0].lower()):
        ek  = k.replace("\\", "\\\\").replace('"', '\\"')
        ev  = v.replace("\\", "\\\\").replace('"', '\\"')
        pad = " " * (max_len - len(k) + 1)
        lua_lines.append('    ["' + ek + '"]' + pad + '= "' + ev + '",')
    lua_preview = "\n".join(lua_lines[:30])
    if len(lua_lines) > 30: lua_preview += f"\n    ... And {len(lua_lines)-30} More"
    new_list = "\n".join(f" `{k}`  `{v}`" for k in sorted(new_entries)[:15])
    ow_list  = "\n".join(f" `{k}`  `{v}`" for k in sorted(overwrite_entries)[:10])
    summary  = "\n".join(p for p in [f"**{len(new_entries)} New** Emoji(s) Added." if new_entries else "", f"**{len(overwrite_entries)} Existing** Emoji(s) Overwritten." if overwrite_entries else ""] if p)
    items    = [txt("## Emojis Saved Successfully"), sep(), txt(f"{summary}\n\n**GitHub File:** `{GITHUB_EMOJI_FILE}`\n **Pushed & Sorted AZ**")]
    if new_list:  items += [sep(), txt(f"**New Entries:**\n{new_list}")]
    if ow_list:   items += [sep(), txt(f"**Overwritten:**\n{ow_list}")]
    items += [sep(), txt(f"**Lua Preview:**\n```lua\n{lua_preview}\n```")]
    await send_v2(interaction, [container(*items)])

# ── /Listemojis ───────────────────────────────────────────────────────────────

@tree.command(name="listemojis", description="List All Saved Emoji Mappings From GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def listemojis(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        data, _ = await gh_fetch(GITHUB_EMOJI_FILE)
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** List Emojis\n\n**Error:**\n```\n{e}\n```"))]); return
    if not data:
        await send_v2(interaction, [container(txt("## No Emojis Saved Yet"), sep(), txt(f" **File:** `{GITHUB_EMOJI_FILE}` Is Empty.\n\nUse `/addemojis` To Start Adding Emoji IDs."))]); return
    sorted_items = sorted(data.items(), key=lambda x: x[0].lower())
    max_len      = max((len(k) for k in data), default=0)
    lua_lines    = ['    ["' + k + '"]' + " " * (max_len - len(k) + 1) + '= "' + v + '",' for k, v in sorted_items]
    await followup(interaction, [container(txt("## All Saved Emojis"), sep(), txt(f" **File:** `{GITHUB_EMOJI_FILE}`    **{len(data)} Entries**"))])
    for i in range(0, len(lua_lines), 30):
        await followup(interaction, [container(txt(f"```lua\n{chr(10).join(lua_lines[i:i+30])}\n```"))])
        await asyncio.sleep(0.5)
    await followup(interaction, [container(txt(f"**Done  {len(data)} Emoji Mappings Listed.**"))])

# ── /Deleteemoji ──────────────────────────────────────────────────────────────

@tree.command(name="deleteemoji", description="Delete An Emoji Mapping From GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def deleteemoji(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    try:
        data, sha = await gh_fetch(GITHUB_EMOJI_FILE)
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Delete Emoji\n**Name:** `{name}`\n\n**Error:**\n```\n{e}\n```"))]); return
    if name not in data:
        suggestions = [k for k in data if name.lower() in k.lower()]
        items = [txt(f"## Emoji Not Found\n**Name:** `{name}`")]
        if suggestions: items += [sep(), txt("**Similar Names:**\n" + "\n".join(f" `{s}`" for s in suggestions[:8]))]
        await send_v2(interaction, [container(*items)]); return
    deleted_val = data.pop(name)
    try:
        await gh_push(GITHUB_EMOJI_FILE, data, sha, f"[DK] Emoji Deleted: {name}")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if ok:
        await send_v2(interaction, [container(txt("## Emoji Deleted"), sep(), txt(f"**Name:** `{name}`\n**Deleted Value:** `{deleted_val}`\n\n**GitHub**  Pushed & Sorted A To Z\n**Remaining:** {len(data)} Emojis"))])
    else:
        await send_v2(interaction, [container(txt("## Failed To Delete Emoji"), sep(), txt(f"**Name:** `{name}`\n\n **GitHub**   Push Failed\n```\n{err[:200]}\n```"))])

# ── /Clearemojis ──────────────────────────────────────────────────────────────

@tree.command(name="clearemojis", description="Clear All Emoji IDs From GitHub Files.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(target="Which File(s) To Clear")
@discord.app_commands.choices(target=[
    discord.app_commands.Choice(name="emojis.lua (All)",              value="all"),
    discord.app_commands.Choice(name="traits.lua Only",               value="traits"),
    discord.app_commands.Choice(name="mutations.lua Only",            value="mutations"),
    discord.app_commands.Choice(name="traits.lua + mutations.lua",    value="both"),
])
async def clearemojis(interaction: discord.Interaction, target: str = "all"):
    await interaction.response.defer(thinking=True)
    files_desc = {
        "all":       f"`{GITHUB_EMOJI_FILE}` (All Emoji IDs)",
        "traits":    f"`{GITHUB_TRAITS_FILE}`",
        "mutations": f"`{GITHUB_MUTATIONS_FILE}`",
        "both":      f"`{GITHUB_TRAITS_FILE}` + `{GITHUB_MUTATIONS_FILE}`",
    }
    wh_url  = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [
            container(
                txt("## Confirm Clear Emoji IDs"), sep(),
                txt(f"**About To Clear All Emoji IDs In:**\n {files_desc.get(target, target)}\n\n**This Action Cannot Be Undone!**\nAre You Sure?"),
                action_row(btn_yes(f"clearemojis_yes:{target}"), btn_no("clearemojis_no")),
            ),
        ],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")

# ── /Syncemojis ───────────────────────────────────────────────────────────────

@tree.command(name="syncemojis", description="Scrape Wiki Names & Show Which Ones Are Missing Emoji IDs.")
@discord.app_commands.default_permissions(administrator=True)
async def syncemojis(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await followup(interaction, [container(txt("## Syncing Emoji Map With Wiki..."), sep(), txt("Scraping Traits & Mutations + Loading GitHub  Please Wait..."))])
    try:
        traits, mutations, (existing_emojis, sha) = await asyncio.gather(scrape_traits(), scrape_mutations(), gh_fetch(GITHUB_EMOJI_FILE))
    except Exception as e:
        await followup(interaction, [container(txt("## Error"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    trait_names    = [n for n, _ in traits]
    mutation_names = [n for n, _ in mutations]
    all_names      = trait_names + [n for n in mutation_names if n not in trait_names]
    unmapped       = [n for n in all_names if n not in existing_emojis]
    mapped         = [n for n in all_names if n in existing_emojis]
    if not unmapped:
        await followup(interaction, [container(txt("## All Names Are Fully Mapped"), sep(), txt(f"**{len(all_names)} Names** All Have Emoji IDs In `{GITHUB_EMOJI_FILE}`. Nothing To Add!"))]); return
    unmapped_block = "\n".join(unmapped)
    await followup(interaction, [container(txt("## Names Missing Emoji IDs"), sep(), txt(f"**{len(unmapped)} / {len(all_names)} Names Need Emoji IDs:**\n\n```\n{unmapped_block[:1800]}\n```\n\nAdd `:emoji_id` After Each Name, Then Run `/addemojis`"))])
    if mapped:
        max_len           = max((len(k) for k in mapped[:20]), default=0)
        lua_preview_lines = ['    ["' + k + '"]' + " " * (max_len - len(k) + 1) + '= "' + existing_emojis[k] + '",' for k in sorted(mapped[:20])]
        if len(mapped) > 20: lua_preview_lines.append(f"    -- ... And {len(mapped)-20} More")
        await followup(interaction, [container(txt("## Already Mapped (Preview)"), sep(), txt(f"```lua\n{chr(10).join(lua_preview_lines)}\n```"))])

# ── /Autoemojis ───────────────────────────────────────────────────────────────

@tree.command(name="autoemojis", description="Auto-Scrape Wiki Icons  Upload To This Server As Emojis  Save IDs To GitHub.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(mode="Which Items To Process", skip_existing="Skip Names Already Mapped In GitHub (Default: True)")
@discord.app_commands.choices(mode=[
    discord.app_commands.Choice(name="Traits Only",               value="traits"),
    discord.app_commands.Choice(name="Mutations Only",            value="mutations"),
    discord.app_commands.Choice(name="Both (Traits + Mutations)", value="both"),
])
async def autoemojis(interaction: discord.Interaction, mode: str = "both", skip_existing: bool = True):
    if interaction.guild is None:
        await interaction.response.send_message("This Command Must Be Used Inside A Server.", ephemeral=True); return
    await interaction.response.defer(thinking=True)

    guild_id  = interaction.guild.id
    bot_token = BOT_TOKEN

    # Get Available Emoji Slots
    async with aiohttp.ClientSession() as s:
        async with s.get(f"https://discord.com/api/v10/guilds/{guild_id}/emojis", headers={"Authorization": f"Bot {bot_token}"}) as r:
            if r.status == 200:
                current_emojis = await r.json()
                slots_used = len(current_emojis)
                slots_free = MAX_EMOJI_SLOTS - slots_used
            else:
                slots_used = 0
                slots_free = MAX_EMOJI_SLOTS

    await followup(interaction, [container(
        txt("## Auto Emoji Upload Starting..."), sep(),
        txt(f"**Step 1/4:** Scraping Wiki & Loading GitHub...\n**Mode:** `{mode}`    **Skip Existing:** `{skip_existing}`\n**Server Slots:** {slots_used}/{MAX_EMOJI_SLOTS} Used    {slots_free} Free"),
    )])

    try:
        if mode == "traits":
            traits_data, mutations_data = await scrape_traits(), []
        elif mode == "mutations":
            traits_data, mutations_data = [], await scrape_mutations()
        else:
            traits_data, mutations_data = await asyncio.gather(scrape_traits(), scrape_mutations())
    except Exception as e:
        await followup(interaction, [container(txt("## Wiki Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    try:
        existing_emojis, emoji_sha = await gh_fetch(GITHUB_EMOJI_FILE)
    except Exception as e:
        await followup(interaction, [container(txt("## GitHub Load Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    candidates: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for name, thumb in traits_data:
        if name not in seen: seen.add(name); candidates.append((name, thumb))
    for name, thumb in mutations_data:
        if name not in seen: seen.add(name); candidates.append((name, thumb))
    if skip_existing:
        candidates = [(n, t) for n, t in candidates if n not in existing_emojis]

    no_image  = [(n, t) for n, t in candidates if not t]
    to_upload = [(n, t) for n, t in candidates if t]

    # Limit By Available Slots
    skipped_by_limit = []
    if len(to_upload) > slots_free:
        skipped_by_limit = [n for n, _ in to_upload[slots_free:]]
        to_upload        = to_upload[:slots_free]

    await followup(interaction, [container(txt("##  Auto Emoji  Plan"), sep(), txt(
        f" **Traits Scraped:** {len(traits_data)}     **Mutations Scraped:** {len(mutations_data)}\n"
        f" **To Upload:** {len(to_upload)}     **No Image (Skip):** {len(no_image)}\n"
        f" **Already Mapped (Skipped):** {len(seen)-len(candidates) if skip_existing else 0}\n"
        + (f" **Slot Full  Cannot Upload ({len(skipped_by_limit)}):** {', '.join(f'`{n}`' for n in skipped_by_limit[:10])}{'...' if len(skipped_by_limit)>10 else ''}\n" if skipped_by_limit else "")
        + f"\n **Step 2/4:** Downloading, Resizing & Uploading To `{interaction.guild.name}`..."
    ))])

    if not to_upload:
        msg = "All Items Either Have No Image, Or Are Already Mapped."
        if skipped_by_limit:
            msg += f"\n\n **Server Is Full ({slots_used}/{MAX_EMOJI_SLOTS})!**\nUse `/deleteserveremojis` To Free Up Slots First."
        await followup(interaction, [container(txt("##  Nothing To Upload"), sep(), txt(f"{msg}\n\n Run `/getemojis` To See Current Status."))]); return

    uploaded_ok:   list[tuple[str, str]] = []
    failed_upload: list[str]             = []
    failed_dl:     list[str]             = []

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(to_upload), 3):
            batch    = to_upload[i:i+3]
            bar_pct  = i / len(to_upload) if to_upload else 1
            bar_fill = int(bar_pct * 20)
            bar      = f"`[{'█' * bar_fill}{'░' * (20-bar_fill)}]` {i}/{len(to_upload)} ({int(bar_pct*100)}%)"
            await followup(interaction, [container(txt(f" **Downloading & Uploading...** {bar}\n *Auto-Resizing Images > 256KB*"))])

            tasks = []
            for name, thumb in batch:
                async def process_one(n=name, t=thumb):
                    img = await download_and_resize(t, session)
                    if img is None: return ("dl_fail", n, "Could Not Download Image")
                    ename       = sanitize_name(n)
                    result, err = await upload_emoji(guild_id, bot_token, ename, img, session)
                    if result and "id" in result:
                        return ("ok", n, f"<:{result['name']}:{result['id']}>")
                    return ("up_fail", n, err)
                tasks.append(process_one())

            slot_full = False
            for res in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(res, Exception):
                    failed_upload.append(f"Exception: {str(res)[:80]}")
                elif res[0] == "ok":
                    uploaded_ok.append((res[1], res[2]))
                elif res[0] == "dl_fail":
                    failed_dl.append(f"{res[1]}  {res[2]}")
                else:
                    err_detail = res[2] if len(res) > 2 else "Unknown Error"
                    if err_detail == "SERVER_FULL":
                        slot_full = True
                        skipped_by_limit.append(res[1])
                    else:
                        failed_upload.append(f"{res[1]}  {err_detail}")

            if slot_full:
                # Get Remaining Unprocessed Items
                remaining = [n for n, _ in to_upload[i+3:]]
                skipped_by_limit.extend(remaining)
                await followup(interaction, [container(
                    txt("## Server Emoji Slots Are Full"), sep(),
                    txt(
                        f"**Server Has Reached The Emoji Limit ({MAX_EMOJI_SLOTS} Slots).**\n\n"
                        f"**Uploaded This Session:** {len(uploaded_ok)}\n"
                        f"**Could Not Upload ({len(skipped_by_limit)}):**\n"
                        + "\n".join(f" `{n}`" for n in skipped_by_limit[:30])
                        + (f"\n*...And {len(skipped_by_limit)-30} More*" if len(skipped_by_limit) > 30 else "")
                        + "\n\nUse `/deleteserveremojis` To Free Up Slots, Then Run `/autoemojis` Again."
                    ),
                )])
                break
            await asyncio.sleep(3.0)

    # Step 3: Save to GitHub
    await followup(interaction, [container(txt("## Step 3/4  Saving To GitHub..."), sep(), txt(f"**Uploaded:** {len(uploaded_ok)}    **Failed:** {len(failed_upload)+len(failed_dl)}\nPushing To `{GITHUB_EMOJI_FILE}`..."))])

    push_ok  = True
    push_err = ""
    if uploaded_ok:
        try:
            existing_emojis, emoji_sha = await gh_fetch(GITHUB_EMOJI_FILE)
        except Exception: pass
        for name, emoji_str in uploaded_ok:
            existing_emojis[name] = emoji_str
        try:
            await gh_push(GITHUB_EMOJI_FILE, existing_emojis, emoji_sha, f"[DK] AutoEmojis: Added {len(uploaded_ok)} Emojis")
        except Exception as pe:
            push_ok  = False
            push_err = str(pe)
        try:
            trait_names_set    = {n for n, _ in traits_data}
            mutation_names_set = {n for n, _ in mutations_data}
            t_data, t_sha = await gh_fetch(GITHUB_TRAITS_FILE)
            m_data, m_sha = await gh_fetch(GITHUB_MUTATIONS_FILE)
            changed_t = changed_m = False
            for name, emoji_str in uploaded_ok:
                if name in trait_names_set:    t_data[name] = emoji_str; changed_t = True
                if name in mutation_names_set: m_data[name] = emoji_str; changed_m = True
            if changed_t: await gh_push(GITHUB_TRAITS_FILE, t_data, t_sha, f"[DK] Traits Emoji: +{len(uploaded_ok)}")
            if changed_m: await gh_push(GITHUB_MUTATIONS_FILE, m_data, m_sha, f"[DK] Mutations Emoji: +{len(uploaded_ok)}")
        except Exception: pass

    # Final report
    ok_preview   = "\n".join(f" {es}  `{n}`" for n, es in uploaded_ok[:30])
    if len(uploaded_ok) > 30: ok_preview += f"\n*...And {len(uploaded_ok)-30} More*"
    other_fails  = [e for e in failed_upload]
    all_not_done = failed_dl + other_fails
    fail_txt     = ""
    if all_not_done:
        fail_txt += f"\n\n**Failed ({len(all_not_done)}):**\n" + "\n".join(f" {e}" for e in all_not_done[:10])
    no_img_txt = ""
    if no_image:
        no_img_names = ", ".join(f"`{n}`" for n, _ in no_image[:15])
        more_img     = f" *+{len(no_image)-15} More*" if len(no_image) > 15 else ""
        no_img_txt   = f"\n\n**No Wiki Image ({len(no_image)}):** {no_img_names}{more_img}"
    skipped_txt = ""
    if skipped_by_limit:
        skipped_txt  = f"\n\n**Not Uploaded  Server Full ({len(skipped_by_limit)}):**\n"
        skipped_txt += "\n".join(f" `{n}`" for n in skipped_by_limit[:20])
        if len(skipped_by_limit) > 20: skipped_txt += f"\n*...And {len(skipped_by_limit)-20} More*"
        skipped_txt += "\n\nUse `/deleteserveremojis` Then Re-Run `/autoemojis`"

    await followup(interaction, [container(
        txt("## Auto Emoji Upload Complete"), sep(),
        txt(
            f"**Uploaded & Saved:** {len(uploaded_ok)}\n"
            f"**Failed:** {len(all_not_done)}\n"
            f" **GitHub**  {' Pushed' if push_ok else f' Failed: {push_err[:100]}'}"
            f"{fail_txt}{no_img_txt}{skipped_txt}"
        ),
    )])
    if ok_preview:
        await followup(interaction, [container(txt("## Emojis Added"), sep(), txt(f"**New Emojis (Preview):**\n\n{ok_preview}"))])

# ── /Savemutations ────────────────────────────────────────────────────────────

@tree.command(name="savemutations", description="Scrape Mutations From Wiki & Sync Emoji IDs To GitHub (mutations.lua).")
@discord.app_commands.default_permissions(administrator=True)
async def savemutations(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await followup(interaction, [container(txt("## Saving Mutations To GitHub..."), sep(), txt(f"Scraping Wiki + Loading Emoji IDs  Pushing To `{GITHUB_MUTATIONS_FILE}`  Please Wait..."))])
    try:
        mutations = await scrape_mutations()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not mutations:
        await followup(interaction, [container(txt("## No Mutations Found"), sep(), txt("Could Not Find Any Mutations On The Wiki Page."))]); return
    try:
        emoji_map, _ = await gh_fetch(GITHUB_EMOJI_FILE)
    except Exception:
        emoji_map = {}
    try:
        existing, sha = await gh_fetch(GITHUB_MUTATIONS_FILE)
    except Exception:
        existing, sha = {}, ""
    data = dict(existing)
    for name, _ in mutations:
        if name in emoji_map: data[name] = emoji_map[name]
        elif name not in data: data[name] = ""
    try:
        await gh_push(GITHUB_MUTATIONS_FILE, data, sha, f"[DK] Mutations: Synced {len(data)} Entries")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if ok:
        mapped   = sum(1 for v in data.values() if v.startswith("<:"))
        unmapped = len(data) - mapped
        preview  = "\n".join('["' + k + '"] = "' + v + '",' for k, v in list(data.items())[:8] if v)
        await followup(interaction, [container(
            txt("## Mutations Saved To GitHub"), sep(),
            txt(f"**Total Mutations:** {len(data)}\n**With Emoji:** {mapped}    **Missing:** {unmapped}\n\n**GitHub File:** `{GITHUB_MUTATIONS_FILE}`\n**Format:** `[\"Name\"] = \"<:Name:id>\",`\n\n**Preview:**\n```lua\n{preview}\n```"),
        )])
    else:
        await followup(interaction, [container(txt("## Failed To Save Mutations"), sep(), txt(f" **GitHub**   Push Failed\n```\n{err[:200]}\n```"))])

# ── /Savetraits ───────────────────────────────────────────────────────────────

@tree.command(name="savetraits", description="Scrape Traits From Wiki & Sync Emoji IDs To GitHub (traits.lua).")
@discord.app_commands.default_permissions(administrator=True)
async def savetraits(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await followup(interaction, [container(txt("## Saving Traits To GitHub..."), sep(), txt(f"Scraping Wiki + Loading Emoji IDs  Pushing To `{GITHUB_TRAITS_FILE}`  Please Wait..."))])
    try:
        traits = await scrape_traits()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not traits:
        await followup(interaction, [container(txt("## No Traits Found"), sep(), txt("Could Not Find Any Traits On The Wiki Page."))]); return
    try:
        emoji_map, _ = await gh_fetch(GITHUB_EMOJI_FILE)
    except Exception:
        emoji_map = {}
    try:
        existing, sha = await gh_fetch(GITHUB_TRAITS_FILE)
    except Exception:
        existing, sha = {}, ""
    data = dict(existing)
    for name, _ in traits:
        if name in emoji_map: data[name] = emoji_map[name]
        elif name not in data: data[name] = ""
    try:
        await gh_push(GITHUB_TRAITS_FILE, data, sha, f"[DK] Traits: Synced {len(data)} Entries")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if ok:
        mapped   = sum(1 for v in data.values() if v.startswith("<:"))
        unmapped = len(data) - mapped
        preview  = "\n".join('["' + k + '"] = "' + v + '",' for k, v in list(data.items())[:8] if v)
        await followup(interaction, [container(
            txt("## Traits Saved To GitHub"), sep(),
            txt(f"**Total Traits:** {len(data)}\n**With Emoji:** {mapped}    **Missing:** {unmapped}\n\n**GitHub File:** `{GITHUB_TRAITS_FILE}`\n**Format:** `[\"Name\"] = \"<:Name:id>\",`\n\n**Preview:**\n```lua\n{preview}\n```"),
        )])
    else:
        await followup(interaction, [container(txt("## Failed To Save Traits"), sep(), txt(f" **GitHub**   Push Failed\n```\n{err[:200]}\n```"))])

# ── /Deleteserveremojis ───────────────────────────────────────────────────────

@tree.command(name="deleteserveremojis", description="Delete All Or Some Emojis From The Discord Server.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(mode="Which Emojis To Delete")
@discord.app_commands.choices(mode=[
    discord.app_commands.Choice(name="All Emojis In Server",           value="all"),
    discord.app_commands.Choice(name="Only Emojis Uploaded By Bot",    value="bot_only"),
])
async def deleteserveremojis(interaction: discord.Interaction, mode: str = "all"):
    if interaction.guild is None:
        await interaction.response.send_message(" Must Be Used Inside A Server!", ephemeral=True); return
    await interaction.response.defer(thinking=True)
    wh_url  = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [
            container(
                txt("## Confirm Delete Server Emojis"), sep(),
                txt(
                    f"**Mode:** `{'All Emojis In Server' if mode == 'all' else 'Only Bot-Uploaded Emojis'}`\n\n"
                    f"**This Will Permanently Delete Emojis From `{interaction.guild.name}`!**\n"
                    f"This Action **Cannot Be Undone**.\n\n"
                    f"Are You Sure You Want To Continue?"
                ),
                action_row(btn_yes(f"delserver_yes:{mode}"), btn_no("delserver_no")),
            ),
        ],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
    bot._delserver_guild = interaction.guild.id

# ══════════════════════════════  BUTTON HANDLERS  ═══════════════════════════════

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component: return
    custom_id = interaction.data.get("custom_id", "")

    # ── Delete Pet ────────────────────────────────────────────────────────────

    if custom_id.startswith("delpet_yes:"):
        name = custom_id[len("delpet_yes:"):]
        info = getattr(bot, "_delpet_pending", {}).pop(name, None)
        if not info: await interaction.response.send_message("Session Expired.", ephemeral=True); return
        await interaction.response.defer()
        data = info["data"]; sha = info["sha"]; deleted_url = info["url"]
        del data[name]
        try:
            await push_pets(data, sha, f"[DK] Deleted: {name}")
            ok = True
        except Exception as e:
            ok = False; err = str(e)
        if ok:
            await patch_msg(interaction, [container(txt("## Pet Deleted Successfully"), sep(), section(f"**{name}**\n\n**Deleted URL:**\n```\n{shorten(deleted_url, 240)}\n```", deleted_url), sep(), txt(f" **GitHub**   Deleted & Sorted AZ\n**Remaining Pets:** {len(data)}"))])
        else:
            await patch_msg(interaction, [container(txt("## Failed To Delete Pet"), sep(), txt(f" **GitHub**   Push Failed\n```\n{err[:200]}\n```"))])

    elif custom_id == "delpet_no":
        getattr(bot, "_delpet_pending", {})
        await interaction.response.defer()
        await patch_msg(interaction, [container(txt("## Delete Cancelled"), sep(), txt("No Changes Were Made."))])

    # ── Fetchpet Overwrite ────────────────────────────────────────────────────

    elif custom_id.startswith("overwrite_yes:"):
        pet_name = custom_id[len("overwrite_yes:"):]
        info     = getattr(bot, "_fetchpet_pending", {}).pop(pet_name, None)
        if not info: await interaction.response.send_message("Session Expired.", ephemeral=True); return
        await interaction.response.defer()
        railway_url = info["railway_url"]; data = info["data"]; sha = info["sha"]; old_url = data.get(pet_name, "")
        try:
            data[pet_name] = railway_url
            await push_pets(data, sha, f"[DK] Auto-Fetch Updated: {pet_name}")
            ok = True
        except Exception as e:
            ok = False; err = str(e)
        extra = f"\n\n**Previous URL:**\n```\n{shorten(old_url, 200)}\n```" if old_url else ""
        if ok:
            await patch_msg(interaction, [container(txt("## Pet Image Updated Successfully"), sep(), section(f"**{pet_name}**\n\n**Railway URL:**\n```\n{shorten(railway_url)}\n```{extra}", railway_url), sep(), txt("**GitHub**  Pushed & Sorted A To Z"))])
        else:
            await patch_msg(interaction, [container(txt("## Failed To Save Pet"), sep(), txt(f" **GitHub**   Push Failed\n```\n{err[:200]}\n```"))])

    elif custom_id.startswith("overwrite_no:"):
        pet_name = custom_id[len("overwrite_no:"):]
        info     = getattr(bot, "_fetchpet_pending", {}).pop(pet_name, None)
        exist    = info["data"].get(pet_name, "") if info else ""
        await interaction.response.defer()
        await patch_msg(interaction, [container(
            txt("## Overwrite Cancelled"), sep(),
            section(f"**{pet_name}**\n\n**Kept Existing URL:**\n```\n{shorten(exist)}\n```", exist) if exist else txt(f"**{pet_name}**  Kept Existing Entry."),
        )])

    # ── Sync Pets ─────────────────────────────────────────────────────────────

    elif custom_id == "syncpets_yes":
        pending = getattr(bot, "_syncpets_pending", {}).pop("latest", None)
        if not pending: await interaction.response.send_message("Session Expired.", ephemeral=True); return
        await interaction.response.defer()
        data       = pending["data"]; sha = pending["sha"]
        to_convert = pending["to_convert"]; to_refetch = pending["to_refetch"]
        total      = len(to_convert) + len(to_refetch); done = 0
        converted_list = []; failed_list = []
        for cname, old_url in to_convert.items():
            await patch_msg(interaction, [container(txt("## Syncing..."), sep(), txt(f"**Progress:** {progress_bar(done, total)}\n\n**Processing:** `{cname}`"))])
            try:
                data[cname] = to_railway(old_url); converted_list.append(cname)
            except Exception as ce:
                failed_list.append(f"{cname}: {ce}")
            done += 1
        for cname in to_refetch:
            await patch_msg(interaction, [container(txt("## Syncing..."), sep(), txt(f"**Progress:** {progress_bar(done, total)}\n\n**Processing:** `{cname}` *(Re-Fetch)*"))])
            try:
                wikia_url, _ = await scrape_pet_image(cname)
                if wikia_url: data[cname] = to_railway(wikia_url); converted_list.append(cname)
                else:         failed_list.append(f"{cname}: Wiki Image Not Found")
            except Exception as ce:
                failed_list.append(f"{cname}: {ce}")
            done += 1
        try:
            await push_pets(data, sha, f"[DK] SyncPets: Converted {len(converted_list)} URLs")
            push_ok = True
        except Exception as pe:
            push_ok = False; push_err = str(pe)
        if push_ok:
            preview  = "\n".join(f" `{n}`" for n in sorted(converted_list)[:20])
            more     = f"\n*...And {len(converted_list)-20} More*" if len(converted_list) > 20 else ""
            fail_txt = ("\n\n **Failed:**\n" + "\n".join(f" {x}" for x in failed_list[:5])) if failed_list else ""
            await patch_msg(interaction, [container(txt("## Sync Complete"), sep(), txt(f"**Converted {len(converted_list)} Pet(s) To Railway:**\n\n{preview}{more}{fail_txt}\n\n**GitHub**  Pushed & Sorted A To Z"))])
        else:
            await patch_msg(interaction, [container(txt("## Sync Failed"), sep(), txt(f" **GitHub Push Failed:**\n```\n{push_err[:300]}\n```"))])

    elif custom_id == "syncpets_no":
        getattr(bot, "_syncpets_pending", {}).pop("latest", None)
        await interaction.response.defer()
        await patch_msg(interaction, [container(txt("## Sync Cancelled"), sep(), txt("No Changes Were Made To GitHub."))])

    # ── Clear Emojis GitHub ───────────────────────────────────────────────────

    elif custom_id.startswith("clearemojis_yes:"):
        target = custom_id[len("clearemojis_yes:"):]
        await interaction.response.defer()
        results = []
        async def clear_file(filename: str, label: str):
            try:
                _, sha = await gh_fetch(filename)
                await gh_push(filename, {}, sha, f"[DK] Cleared All Emoji IDs: {filename}")
                results.append(f" `{label}`  Cleared Successfully")
            except Exception as e:
                results.append(f" `{label}`  Error: {str(e)[:80]}")
        if target == "all":       await clear_file(GITHUB_EMOJI_FILE, "emojis.lua")
        elif target == "traits":  await clear_file(GITHUB_TRAITS_FILE, "traits.lua")
        elif target == "mutations": await clear_file(GITHUB_MUTATIONS_FILE, "mutations.lua")
        elif target == "both":
            await clear_file(GITHUB_TRAITS_FILE, "traits.lua")
            await clear_file(GITHUB_MUTATIONS_FILE, "mutations.lua")
        result_txt = "\n".join(results)
        await patch_msg(interaction, [container(
            txt("## Clear Emojis  Done"), sep(),
            txt(f"{result_txt}\n\n Run `/autoemojis` To Upload New Emojis\nThen `/savetraits` + `/savemutations` To Sync New IDs."),
        )])

    elif custom_id == "clearemojis_no":
        await interaction.response.defer()
        await patch_msg(interaction, [container(txt("## Clear Cancelled"), sep(), txt("No Changes Were Made."))])

    # ── Delete Server Emojis ──────────────────────────────────────────────────

    elif custom_id.startswith("delserver_yes:"):
        mode     = custom_id[len("delserver_yes:"):]
        guild_id = getattr(bot, "_delserver_guild", None) or (interaction.guild.id if interaction.guild else None)
        if not guild_id: await interaction.response.send_message("Session Expired.", ephemeral=True); return
        await interaction.response.defer()
        headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
        await patch_msg(interaction, [container(txt("## Deleting Server Emojis..."), sep(), txt("Fetching Emoji List From Server..."))])
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://discord.com/api/v10/guilds/{guild_id}/emojis", headers=headers) as r:
                if r.status != 200:
                    await patch_msg(interaction, [container(txt("## Failed To Fetch Emojis"), sep(), txt(f"Discord API Returned {r.status}\n```\n{(await r.text())[:200]}\n```"))]); return
                server_emojis = await r.json()
            if not server_emojis:
                await patch_msg(interaction, [container(txt("## No Emojis In Server"), sep(), txt("There Are No Emojis To Delete!"))]); return
            if mode == "bot_only":
                try:
                    bot_emoji_data, _ = await gh_fetch(GITHUB_EMOJI_FILE)
                    bot_ids = set()
                    for v in bot_emoji_data.values():
                        m = re.search(r"<:[^:]+:(\d+)>", v)
                        if m: bot_ids.add(m.group(1))
                    to_delete = [e for e in server_emojis if str(e["id"]) in bot_ids]
                except Exception:
                    to_delete = server_emojis
            else:
                to_delete = server_emojis
            if not to_delete:
                await patch_msg(interaction, [container(txt("## No Matching Emojis Found"), sep(), txt(f"No Emojis Match The Selected Mode: `{mode}`"))]); return
            await patch_msg(interaction, [container(txt("## Deleting..."), sep(), txt(f"**Total In Server:** {len(server_emojis)}\n**Will Delete:** {len(to_delete)}\n\n Deleting..."))])
            deleted_ok = []; deleted_fail = []
            for i, emoji in enumerate(to_delete):
                eid = emoji["id"]; ename = emoji["name"]
                if i % 10 == 0 and i > 0:
                    bar = progress_bar(i, len(to_delete))
                    await patch_msg(interaction, [container(txt(f" **Deleting...** {bar}\n Done: {len(deleted_ok)}     Failed: {len(deleted_fail)}"))])
                for attempt in range(3):
                    async with session.delete(f"https://discord.com/api/v10/guilds/{guild_id}/emojis/{eid}", headers=headers) as r:
                        if r.status == 204: deleted_ok.append(ename); break
                        elif r.status == 429:
                            body = await r.text()
                            try:    retry_after = json.loads(body).get("retry_after", 1.0)
                            except: retry_after = 1.0
                            await asyncio.sleep(float(retry_after) + 0.3); continue
                        else:
                            err_body = await r.text()
                            deleted_fail.append(f"{ename} (HTTP {r.status}: {err_body[:80]})"); break
                else: deleted_fail.append(f"{ename} (Rate Limited)")
                await asyncio.sleep(0.3)
        fail_txt = ""
        if deleted_fail: fail_txt = "\n\n**Failed To Delete:**\n" + "\n".join(f" `{x}`" for x in deleted_fail[:10])
        await patch_msg(interaction, [container(
            txt("## Server Emojis Deleted"), sep(),
            txt(
                f"**Deleted:** {len(deleted_ok)} Emojis\n"
                f"**Failed:** {len(deleted_fail)} Emojis\n"
                f" **Remaining In Server:** {len(server_emojis)-len(deleted_ok)} Emojis"
                f"{fail_txt}\n\n"
                f"Run `/autoemojis skip_existing:False` To Upload New Emojis."
            ),
        )])

    elif custom_id == "delserver_no":
        await interaction.response.defer()
        await patch_msg(interaction, [container(txt("## Delete Cancelled"), sep(), txt("No Emojis Were Deleted From The Server."))])

# ── /Refetchbroken ────────────────────────────────────────────────────────────

@tree.command(name="refetchbroken", description="Auto-Fetch Images For Pets With Broken Or Missing URLs.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(dry_run="Preview Only — Do Not Fix Anything")
async def refetchbroken(interaction: discord.Interaction, dry_run: bool = False):
    await interaction.response.defer(thinking=True)

    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    # Detect broken entries: empty URL, or URL that isn't Railway and isn't a valid wikia URL
    broken = {
        name: url for name, url in data.items()
        if not url or url.strip() == "" or (not is_railway(url) and not is_cdn(url) and not extract_wikia_url(url))
    }

    if not broken:
        await send_v2(interaction, [container(
            txt("## No Broken Pet Images Found"),
            sep(),
            txt(f"**Total Pets:** {len(data)}\n\nAll Pets Have Valid URLs!"),
        )]); return

    preview = "\n".join(f" `{title_case(n)}`" for n in sorted(broken)[:20])
    more    = f"\n*...And {len(broken)-20} More*" if len(broken) > 20 else ""
    await send_v2(interaction, [container(
        txt("## Broken Pet Images"),
        sep(),
        txt(f"**Found {len(broken)} Broken Pet(s):**\n\n{preview}{more}\n\n"
            + ("Dry Run  Nothing Will Be Changed." if dry_run else "Fetching Images...")),
    )])

    if dry_run: return

    fixed_ok:   list[str] = []
    still_fail: list[str] = []
    broken_list = sorted(broken.items())

    for i, (name, old_url) in enumerate(broken_list):
        await patch_msg(interaction, [container(
            txt("## Refetching Broken Images..."),
            sep(),
            txt(
                f"**Progress:** {progress_bar(i, len(broken_list))}\n"
                f"**Processing:** `{title_case(name)}`\n\n"
                f"**Fixed:** {len(fixed_ok)}    **Still Broken:** {len(still_fail)}"
            ),
        )])
        try:
            wikia_url, _ = await scrape_pet_image(name)
            if wikia_url:
                new_url = to_railway(wikia_url)
                data[name] = new_url
                fixed_ok.append(name)
            else:
                still_fail.append(name)
        except Exception:
            still_fail.append(name)
        await asyncio.sleep(0.3)

    # Final 100% patch
    await patch_msg(interaction, [container(
        txt("## Pushing To GitHub..."),
        sep(),
        txt(f"**Progress:** {progress_bar(len(broken_list), len(broken_list))}\nAll Processed  Saving..."),
    )])

    try:
        await push_pets(data, sha, f"[DK] RefetchBroken: Fixed {len(fixed_ok)} Pets With Broken Images")
        push_ok = True
    except Exception as pe:
        push_ok = False; push_err = str(pe)

    if push_ok:
        fixed_list   = "\n".join(f" `{title_case(n)}`" for n in fixed_ok[:20])
        more_fixed   = f"\n*...And {len(fixed_ok)-20} More*" if len(fixed_ok) > 20 else ""
        fail_list    = ("\n\n**Still No Image Found:**\n" + "\n".join(f" `{title_case(n)}`" for n in still_fail[:10])) if still_fail else ""
        await followup(interaction, [container(
            txt("## Refetch Broken  Done!"),
            sep(),
            txt(
                f"**Total Broken:** {len(broken_list)}\n"
                f"**Fixed:** {len(fixed_ok)}\n"
                f"**Still Broken:** {len(still_fail)}\n\n"
                f"**Pets Fixed:**\n{fixed_list}{more_fixed}"
                f"{fail_list}\n\n"
                f"**GitHub**  Pushed & Sorted A To Z"
            ),
        )])
    else:
        await followup(interaction, [container(txt("## GitHub Push Failed"), sep(), txt(f"**Error:**\n```\n{push_err[:300]}\n```"))])

# ── /Refetchall ───────────────────────────────────────────────────────────────

@tree.command(name="refetchall", description="Re-Fetch The Latest Images From Wiki For All Pets In GitHub.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(dry_run="Preview Only — Do Not Save", overwrite_existing="Overwrite Pets That Already Have Valid Images (Default: Only Fetch Missing)")
async def refetchall(interaction: discord.Interaction, dry_run: bool = False, overwrite_existing: bool = False):
    await interaction.response.defer(thinking=True)

    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    if overwrite_existing:
        to_fetch = list(data.keys())
    else:
        to_fetch = [n for n, u in data.items() if not u or not (is_railway(u) or is_cdn(u) or extract_wikia_url(u))]

    await send_v2(interaction, [container(
        txt("## Refetch All Pets"),
        sep(),
        txt(
            f"**Total Pets In GitHub:** {len(data)}\n"
            f"**Will Refetch:** {len(to_fetch)} Pet(s)\n"
            f"**Overwrite:** `{overwrite_existing}` | **Dry Run:** `{dry_run}`\n\n"
            + ("Dry Run  Nothing Will Be Saved." if dry_run else "Starting Fetch...")
        ),
    )])

    if not to_fetch:
        await followup(interaction, [container(txt("## Nothing To Fetch"), sep(), txt(f"All {len(data)} Pets Already Have Valid URLs.\n\nUse `overwrite_existing: True` To Re-Fetch All."))])
        return

    if dry_run:
        preview = "\n".join(f" `{title_case(n)}`" for n in to_fetch[:25])
        more    = f"\n*...And {len(to_fetch)-25} More*" if len(to_fetch) > 25 else ""
        await followup(interaction, [container(
            txt("## Dry Run  Pets That Will Be Fetched"),
            sep(),
            txt(f"**{len(to_fetch)} Pet(s):**\n\n{preview}{more}"),
        )])
        return

    fetched_ok:   list[str] = []
    fetch_failed: list[str] = []

    for i, name in enumerate(to_fetch):
        await patch_msg(interaction, [container(
            txt("## Refetching All Pets..."),
            sep(),
            txt(
                f"**Progress:** {progress_bar(i, len(to_fetch))}\n"
                f"**Processing:** `{title_case(name)}`\n\n"
                f"**Success:** {len(fetched_ok)}    **Failed:** {len(fetch_failed)}"
            ),
        )])
        try:
            wikia_url, _ = await scrape_pet_image(name)
            if wikia_url:
                data[name] = to_railway(wikia_url)
                fetched_ok.append(name)
            else:
                fetch_failed.append(name)
        except Exception:
            fetch_failed.append(name)
        await asyncio.sleep(0.4)

    await patch_msg(interaction, [container(
        txt("## Pushing To GitHub..."),
        sep(),
        txt(f"**Progress:** {progress_bar(len(to_fetch), len(to_fetch))}\nAll Processed  Saving..."),
    )])

    try:
        await push_pets(data, sha, f"[DK] RefetchAll: Updated {len(fetched_ok)}/{len(to_fetch)} Pets")
        push_ok = True
    except Exception as pe:
        push_ok = False; push_err = str(pe)

    if push_ok:
        ok_list    = "\n".join(f" `{title_case(n)}`" for n in fetched_ok[:20])
        more_ok    = f"\n*...And {len(fetched_ok)-20} More*" if len(fetched_ok) > 20 else ""
        fail_txt   = ("\n\n**No Image Found:**\n" + "\n".join(f" `{title_case(n)}`" for n in fetch_failed[:10])) if fetch_failed else ""
        await followup(interaction, [container(
            txt("## Refetch All  Done!"),
            sep(),
            txt(
                f"**Total Fetched:** {len(to_fetch)}\n"
                f"**Success:** {len(fetched_ok)}\n"
                f"**Failed:** {len(fetch_failed)}\n\n"
                f"**Updated:**\n{ok_list}{more_ok}"
                f"{fail_txt}\n\n"
                f"**GitHub**  Pushed & Sorted A To Z"
            ),
        )])
    else:
        await followup(interaction, [container(txt("## GitHub Push Failed"), sep(), txt(f"**Error:**\n```\n{push_err[:300]}\n```"))])


# ══════════════════════════  PREFIX COMMANDS & EVENTS  ══════════════════════════


# ── Auto-Init GitHub Files ────────────────────────────────────────────────────

async def ensure_files():
    """Auto-Create GitHub Files If They Do Not Exist."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
    }
    files = [
        (GITHUB_FILE,          "{}",  True),   # thumbnails.json  — JSON
        (GITHUB_JSON_FILE,     "{}",  True),   # thumbnails1.json — JSON
        (GITHUB_EMOJI_FILE,    "",    False),   # emojis.lua       — Lua
        (GITHUB_TRAITS_FILE,   "",    False),   # traits.lua       — Lua
        (GITHUB_MUTATIONS_FILE,"",    False),   # mutations.lua    — Lua
    ]
    for filename, empty_content, is_json in files:
        check_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
        async with aiohttp.ClientSession() as s:
            async with s.get(check_url, headers=headers) as r:
                if r.status == 200:
                    continue    # File Already Exists — Skip
                if r.status != 404:
                    print(f"[DK] Could not check {filename}: HTTP {r.status}")
                    continue
            # File Does Not Exist — Create It
            encoded = base64.b64encode(empty_content.encode()).decode()
            body    = {
                "message": f"[DK] Init: Create {filename}",
                "content": encoded,
                "branch":  GITHUB_BRANCH,
            }
            create_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}"
            async with s.put(create_url, headers=headers, json=body) as r:
                if r.status in (200, 201):
                    print(f"[DK] Created missing file: {filename}")
                else:
                    print(f"[DK] Failed to create {filename}: HTTP {r.status} — {(await r.text())[:150]}")

@bot.command(name="sync")
async def sync_cmd(ctx: commands.Context):
    if ctx.author.id != OWNER_ID:
        await ctx.send("Access Denied."); return
    await tree.sync()
    await ctx.send(f"**Slash Commands Synced!** `{len(tree.get_commands())}` Commands Registered.")

@bot.event
async def on_ready():
    await tree.sync()
    await ensure_files()                       # Auto-Create Files If Missing
    print(f"[DK] Logged In As: {bot.user}")
    print(f"[DK] Slash Commands Synced! ({len(tree.get_commands())} Commands)")
    print(f"[DK] GitHub Files:")
    print(f"[DK]    Pets:      {GITHUB_FILE}")
    print(f"[DK]    Emojis:    {GITHUB_EMOJI_FILE}")
    print(f"[DK]    Traits:    {GITHUB_TRAITS_FILE}")
    print(f"[DK]    Mutations: {GITHUB_MUTATIONS_FILE}")
    print(f"[DK] Max Emoji Slots: {MAX_EMOJI_SLOTS}")

bot.run(BOT_TOKEN)
