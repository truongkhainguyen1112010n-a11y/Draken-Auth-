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
GITHUB_TRAITS_FILE    = os.environ.get("GITHUB_TRAITS_FILE",    "traits.lua")
GITHUB_MUTATIONS_FILE = os.environ.get("GITHUB_MUTATIONS_FILE", "mutations.lua")
SCRAPER_API_KEY       = os.environ.get("SCRAPER_API_KEY",       "")

RAILWAY_PROXY         = os.environ.get("RAILWAY_PROXY",         "https://proxy-production-22ad.up.railway.app/img")
FANDOM_BASE           = "https://stealabrainrot.fandom.com/wiki/"

FLAGS_V2              = 32768
FLAGS_V2_EPH          = 32768 | 64
OWNER_ID              = 1498384419805986886

# ── Helpers ───────────────────────────────────────────────────────────────────

def title_case(s: str) -> str:
    return ' '.join(w[0].upper() + w[1:] if w else w for w in s.split(' '))

def max_emoji_slots(premium_tier: int) -> int:
    return {0: 50, 1: 100, 2: 150, 3: 250}.get(premium_tier, 50)

# ── Bot Setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="!", intents=intents)
tree    = bot.tree

# ── Owner Guard ───────────────────────────────────────────────────────────────

async def owner_check(interaction: discord.Interaction) -> bool:
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Access Denied — This Command Is For The Owner Only.", ephemeral=True)
        return False
    return True

async def global_owner_check(interaction: discord.Interaction) -> bool:
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Access Denied — This Bot Is Private.", ephemeral=True)
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
    return btn("Yes", custom_id, style=2)

def btn_no(custom_id: str) -> dict:
    return btn("No", custom_id, style=2)

def progress_bar(done: int, total: int, width: int = 20) -> str:
    pct    = done / total if total else 1
    filled = int(pct * width)
    empty  = width - filled
    if filled == 0:
        inner = "▱" * width
    elif filled == width:
        inner = "▰" * width
    else:
        inner = "▰" * filled + "▱" * empty
    pct_str = f"{int(pct * 100)}%".rjust(4)
    return f"`{inner}` {done}/{total} ({pct_str})"

# ── Discord Helpers ───────────────────────────────────────────────────────────

def webhook_url(interaction: discord.Interaction) -> str:
    return f"https://discord.com/api/v10/webhooks/{interaction.application_id}/{interaction.token}"

async def send_v2(interaction: discord.Interaction, components: list[dict], eph: bool = True):
    url   = webhook_url(interaction)
    flags = FLAGS_V2_EPH if eph else FLAGS_V2
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json={"flags": flags, "components": components}) as r:
            if r.status not in (200, 204):
                raise Exception(f"Discord {r.status}: {(await r.text())[:200]}")

async def followup(interaction: discord.Interaction, components: list[dict], eph: bool = True):
    url     = f"https://discord.com/api/v10/webhooks/{interaction.application_id}/{interaction.token}"
    payload = {"flags": FLAGS_V2_EPH if eph else FLAGS_V2, "components": components}
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

async def patch_msg(interaction: discord.Interaction, components: list[dict], eph: bool = True):
    url   = f"{webhook_url(interaction)}/messages/@original"
    flags = FLAGS_V2_EPH if eph else FLAGS_V2
    async with aiohttp.ClientSession() as s:
        async with s.patch(url, json={"flags": flags, "components": components}) as r:
            await r.read()

# ── URL Helpers ───────────────────────────────────────────────────────────────

def is_railway(url: str) -> bool:
    return "up.railway.app" in url or "railway.app" in url

def is_cdn(url: str) -> bool:
    return "media.discordapp.net/attachments" in url or "cdn.discordapp.com/attachments" in url

def _clean_wikia_url(url: str) -> str:
    url = re.sub(r'https?://vignette\d*\.wikia\.nocookie\.net', 'https://static.wikia.nocookie.net', url)
    url = re.sub(r'(/revision/latest)(?:/[^?#]*)?', r'\1', url)
    return url

async def api_batch_images(names: list[str]) -> dict[str, str]:
    BASE      = "https://stealabrainrot.fandom.com/api.php"
    hdrs      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"}
    timeout   = aiohttp.ClientTimeout(total=30)
    result:   dict[str, str] = {}
    connector = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        for i in range(0, len(names), 50):
            batch  = names[i:i + 50]
            params = {
                "action": "query", "prop": "pageimages",
                "titles": "|".join(batch),
                "pithumbsize": "500", "format": "json",
            }
            try:
                async with session.get(BASE, params=params, headers=hdrs, timeout=timeout) as r:
                    if r.status != 200:
                        continue
                    jdata = await r.json(content_type=None)
                    for page in jdata.get("query", {}).get("pages", {}).values():
                        title = page.get("title", "")
                        src   = page.get("thumbnail", {}).get("source", "")
                        if title and src:
                            result[title] = to_railway(_clean_wikia_url(src))
                await asyncio.sleep(0.2)
            except Exception:
                continue
    return result

def via_proxy(url: str) -> str:
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
    if is_cdn(url): return url
    if is_railway(url):
        m = re.search(r'[?&]url=(.+)', url)
        if m:
            inner = unquote(m.group(1))
            return via_proxy(inner)
        return url
    wikia  = extract_wikia_url(url)
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
    fresh_sha = await _gh_latest_sha(filename, headers)
    encoded   = base64.b64encode(to_lua(sorted_data).encode()).decode()
    body      = {"message": msg, "content": encoded, "branch": GITHUB_BRANCH}
    if fresh_sha or sha:
        body["sha"] = fresh_sha or sha
    async with aiohttp.ClientSession() as s:
        async with s.put(url, headers=headers, json=body) as r:
            if r.status not in (200, 201):
                raise Exception(f"GitHub Push {r.status}: {(await r.text())[:300]}")

async def fetch_pets() -> tuple[dict, str]:
    url     = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}?ref={GITHUB_BRANCH}"
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

async def _gh_latest_sha(filename: str, headers: dict) -> str:
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers) as r:
            if r.status == 200:
                return (await r.json()).get("sha", "")
            return ""

def _encode_for_file(filename: str, data: dict) -> str:
    if filename == GITHUB_JSON_FILE:
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
        if fresh_sha:
            body["sha"] = fresh_sha
        async with aiohttp.ClientSession() as s:
            async with s.put(url, headers=headers, json=body) as r:
                if r.status not in (200, 201):
                    raise Exception(f"GitHub Push [{filename}] {r.status}: {(await r.text())[:300]}")

    await _push_file(GITHUB_FILE)
    await asyncio.sleep(0.5)
    await _push_file(GITHUB_JSON_FILE)

# ── Notification Helper ───────────────────────────────────────────────────────

async def notify_pet_added(name: str, url: str):
    """Send a notification to the configured channel when a new pet is added."""
    channel_id = getattr(bot, "notify_channel_id", None)
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return
    try:
        payload = {
            "flags": FLAGS_V2,
            "components": [container(
                txt("## New Brainrot Added"),
                sep(),
                section(f"**{title_case(name)}**", url),
                sep(),
                txt(f"**URL:**\n```\n{shorten(url, 200)}\n```"),
            )],
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
                json=payload,
            ) as r:
                await r.read()
    except Exception:
        pass

# ── Emoji Helpers ─────────────────────────────────────────────────────────────

def parse_emoji_input(raw: str) -> dict[str, str]:
    result = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'<:([^:]+):(\d+)>', line)
        if m:
            result[m.group(1)] = f"<:{m.group(1)}:{m.group(2)}>"
            continue
        m = re.match(r'^([^:]+):(\d{10,20})$', line)
        if m:
            name = m.group(1).strip()
            eid  = m.group(2).strip()
            result[name] = f"<:{name}:{eid}>"
    return result

def sanitize_name(name: str) -> str:
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    if not sanitized:
        sanitized = "emoji"
    if len(sanitized) < 2:
        sanitized = sanitized + "_"
    return sanitized[:32]

async def download_and_resize(url: str, session: aiohttp.ClientSession, size: int = 128) -> bytes | None:
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with session.get(url, timeout=timeout) as r:
            if r.status != 200:
                return None
            data = await r.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        result = buf.getvalue()
        if len(result) > 256 * 1024:
            img.thumbnail((64, 64), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            result = buf.getvalue()
        return result
    except Exception:
        return None

async def upload_emoji(
    guild_id: int,
    bot_token: str,
    name: str,
    image_bytes: bytes,
    session: aiohttp.ClientSession,
) -> tuple[dict | None, str]:
    b64     = base64.b64encode(image_bytes).decode()
    payload = {"name": name, "image": f"data:image/png;base64,{b64}"}
    headers = {"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"}
    for attempt in range(3):
        async with session.post(
            f"https://discord.com/api/v10/guilds/{guild_id}/emojis",
            headers=headers,
            json=payload,
        ) as r:
            if r.status == 201:
                return await r.json(), ""
            body = await r.text()
            if r.status == 429:
                try:    retry_after = json.loads(body).get("retry_after", 1.5)
                except: retry_after = 1.5
                await asyncio.sleep(float(retry_after) + 0.3)
                continue
            if r.status == 400:
                err_data = {}
                try: err_data = json.loads(body)
                except: pass
                if err_data.get("code") == 30008 or "maximum" in body.lower():
                    return None, "SERVER_FULL"
                return None, f"HTTP 400: {body[:120]}"
            return None, f"HTTP {r.status}: {body[:120]}"
    return None, "Rate Limited — Max Retries"

# ── Wiki Scrapers ─────────────────────────────────────────────────────────────

async def scrape_pet_image(pet_name: str) -> tuple[str | None, str]:
    slug     = pet_name.replace(" ", "_")
    page_url = f"https://stealabrainrot.fandom.com/wiki/{urllib.parse.quote(slug)}"
    debug    = []

    def _extract_image(html: str) -> str | None:
        m = re.search(r'<meta property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
        if not m:
            m = re.search(r'<meta content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html)
        if m:
            img_url = m.group(1)
            if "wikia.nocookie.net" in img_url:
                return _clean_wikia_url(img_url)
        imgs = re.findall(r'https://static\.wikia\.nocookie\.net/[^"\'.\s<>]+\.(?:png|jpg|webp)', html)
        imgs = [u for u in imgs if not any(x in u.lower() for x in
                ["icon", "logo", "favicon", "placeholder", "wordmark", "fandom-heart"])]
        if imgs:
            return _clean_wikia_url(re.sub(r'/revision/latest.*', '', imgs[0]))
        return None

    loop = asyncio.get_event_loop()
    def _urllib_get(url: str) -> str | None:
        import urllib.request as _ur
        try:
            req = _ur.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
            })
            with _ur.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    try:
        body = await loop.run_in_executor(None, _urllib_get, page_url)
        if body and "<!DOCTYPE" in body[:500]:
            debug.append("Direct OK")
            img = _extract_image(body)
            if img:
                return img, "\n".join(debug)
    except Exception:
        pass
    debug.append("Direct Failed")

    timeout   = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"}
            async with session.get(page_url, headers=hdrs, timeout=timeout) as r:
                body = await r.text()
                if r.status == 200 and "<!DOCTYPE" in body[:500]:
                    debug.append("aiohttp OK")
                    img = _extract_image(body)
                    if img:
                        return img, "\n".join(debug)
        except Exception:
            pass
        debug.append("aiohttp Failed")

        if SCRAPER_API_KEY:
            try:
                async with session.get(
                    "https://api.scraperapi.com",
                    params={"api_key": SCRAPER_API_KEY, "url": page_url, "render": "false"},
                    timeout=timeout,
                ) as r:
                    body = await r.text()
                    if r.status == 200:
                        debug.append("ScraperAPI OK")
                        img = _extract_image(body)
                        if img:
                            return img, "\n".join(debug)
            except Exception:
                pass
            debug.append("ScraperAPI Failed")

    debug.append("No Image Found")
    return None, "\n".join(debug)

def _best_wikia_img(cell_html: str) -> str | None:
    for attr in ('data-src', 'data-image-key', 'src'):
        for m in re.finditer(rf'{attr}=["\'"]([^"\'"]+)["\'"]', cell_html, re.IGNORECASE):
            url = m.group(1)
            if "wikia.nocookie.net" in url and "placeholder" not in url.lower():
                return to_railway(_clean_wikia_url(url))
    return None

async def _scrape_wiki_table(page_url: str) -> list[tuple[str, str | None]]:
    BASE    = "https://stealabrainrot.fandom.com/api.php"
    slug    = urllib.parse.unquote(page_url.split("/wiki/")[-1])
    timeout = aiohttp.ClientTimeout(total=40)
    hdrs    = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
        "Accept-Encoding": "gzip, deflate",
    }
    html: str | None = None

    connector = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get(
                BASE,
                params={"action": "parse", "page": slug, "format": "json", "prop": "text"},
                headers=hdrs,
                timeout=timeout,
            ) as r:
                if r.status == 200:
                    jdata = await r.json(content_type=None)
                    html  = jdata.get("parse", {}).get("text", {}).get("*")
        except Exception:
            pass

        if not html:
            loop = asyncio.get_event_loop()
            def _urllib_get(url: str) -> str | None:
                import urllib.request as _ur
                try:
                    req = _ur.Request(url, headers={"User-Agent": hdrs["User-Agent"]})
                    with _ur.urlopen(req, timeout=30) as r:
                        body = r.read().decode("utf-8", errors="replace")
                        return body if "<!DOCTYPE" in body[:500] or "<!doctype" in body[:500] else None
                except Exception:
                    return None
            try:
                html = await loop.run_in_executor(None, _urllib_get, page_url)
            except Exception:
                pass

        if not html:
            try:
                async with session.get(page_url, headers=hdrs, timeout=timeout) as r:
                    body = await r.text()
                    if r.status == 200 and "<!DOCTYPE" in body[:500]:
                        html = body
            except Exception:
                pass

        if not html and SCRAPER_API_KEY:
            try:
                async with session.get(
                    "https://api.scraperapi.com",
                    params={"api_key": SCRAPER_API_KEY, "url": page_url, "render": "false"},
                    timeout=timeout,
                ) as r:
                    if r.status == 200:
                        html = await r.text()
            except Exception:
                pass

    if not html:
        return []

    def clean(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

    NAME_COL = 1
    ICON_COL = 3
    row_pat  = re.compile(r"<tr[^>]*>(.*?)</tr>",  re.DOTALL | re.IGNORECASE)
    td_pat   = re.compile(r"<td[^>]*>(.*?)</td>",   re.DOTALL | re.IGNORECASE)
    th_pat   = re.compile(r"<th[^>]*>(.*?)</th>",   re.DOTALL | re.IGNORECASE)

    entries:    list[tuple[str, str | None]] = []
    seen_names: set[str] = set()

    for row_m in row_pat.finditer(html):
        row_html = row_m.group(1)
        ths = th_pat.findall(row_html)
        if ths:
            headers = [clean(h).lower() for h in ths]
            for i, h in enumerate(headers):
                if h == "name":                    NAME_COL = i
                if h in ("icon", "image", "img"): ICON_COL = i
            continue
        cells = td_pat.findall(row_html)
        if len(cells) <= max(NAME_COL, ICON_COL):
            continue
        name = clean(cells[NAME_COL])
        skip = {"name", "multi", "icon", "image", "rarity", "effect", "description", ""}
        if not name or name.lower() in skip:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        thumb = _best_wikia_img(cells[ICON_COL])
        if not thumb:
            for cell in cells:
                thumb = _best_wikia_img(cell)
                if thumb:
                    break
        if not thumb:
            all_wikia = re.findall(
                r'https://static\.wikia\.nocookie\.net/[^"\'>\s]+\.(?:png|jpg|webp|gif)',
                row_html, re.IGNORECASE,
            )
            for u in all_wikia:
                if not any(x in u.lower() for x in ["placeholder", "wordmark", "fandom", "favicon"]):
                    thumb = to_railway(re.sub(r"/revision/latest.*", "", u).split("?")[0])
                    break
        entries.append((name, thumb))

    return entries

async def scrape_mutations() -> list[tuple[str, str | None]]:
    return await _scrape_wiki_table("https://stealabrainrot.fandom.com/wiki/Mutations")

async def scrape_traits() -> list[tuple[str, str | None]]:
    return await _scrape_wiki_table("https://stealabrainrot.fandom.com/wiki/Traits")

async def scrape_category_brainrots(
    on_page=None,
) -> list[tuple[str, str | None]]:
    BASE_URL  = "https://stealabrainrot.fandom.com"
    start_url = BASE_URL + "/wiki/Category:Listed_Brainrots"
    timeout   = aiohttp.ClientTimeout(total=40)
    hdrs      = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
        "Accept-Encoding": "gzip, deflate",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    LI_PAT       = re.compile(r'<li class="category-page__member">(.*?)</li>', re.DOTALL)
    NAME_PAT     = re.compile(r'class="category-page__member-link"[^>]*>([^<]+)<')
    DATA_SRC_PAT = re.compile(r'\bdata-src=["\'](' + r'https://static\.wikia\.nocookie\.net/[^"\']+' + r')["\']')
    SRC_PAT      = re.compile(r'\bsrc=["\'](' + r'https://static\.wikia\.nocookie\.net/[^"\']+' + r')["\']')

    all_results:  list[tuple[str, str | None]] = []
    seen_names:   set[str] = set()
    visited_urls: set[str] = set()

    async def _fetch_html(url: str) -> tuple[str | None, str]:
        loop = asyncio.get_event_loop()

        def _urllib_fetch(u: str) -> str | None:
            import urllib.request as _ur
            try:
                req = _ur.Request(u, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                })
                with _ur.urlopen(req, timeout=30) as r:
                    body = r.read().decode("utf-8", errors="replace")
                    return body if "category-page__member" in body else None
            except Exception:
                return None

        try:
            body = await loop.run_in_executor(None, _urllib_fetch, url)
            if body:
                return body, "Direct"
        except Exception:
            pass

        connector = aiohttp.TCPConnector(force_close=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(url, headers=hdrs, timeout=timeout) as r:
                    body = await r.text()
                    if r.status == 200 and "category-page__member" in body:
                        return body, "aiohttp"
            except Exception:
                pass

            if SCRAPER_API_KEY:
                try:
                    async with session.get(
                        "https://api.scraperapi.com",
                        params={"api_key": SCRAPER_API_KEY, "url": url, "render": "false"},
                        timeout=timeout,
                    ) as r:
                        body = await r.text()
                        if r.status == 200 and "category-page__member" in body:
                            return body, "ScraperAPI"
                except Exception:
                    pass

        return None, "Failed"

    async def _api_get_all_names() -> list[str]:
        names: list[str] = []
        cont: str | None = None
        connector = aiohttp.TCPConnector(force_close=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            for _ in range(20):
                params: dict = {
                    "action": "query", "list": "categorymembers",
                    "cmtitle": "Category:Listed_Brainrots",
                    "cmlimit": "500", "cmnamespace": "0", "format": "json",
                }
                if cont:
                    params["cmcontinue"] = cont
                try:
                    async with session.get(
                        BASE_URL + "/api.php", params=params, headers=hdrs, timeout=timeout
                    ) as r:
                        if r.status != 200:
                            break
                        jdata = await r.json(content_type=None)
                        for m in jdata.get("query", {}).get("categorymembers", []):
                            names.append(m["title"])
                        cont = jdata.get("continue", {}).get("cmcontinue")
                        if not cont:
                            break
                        await asyncio.sleep(0.3)
                except Exception:
                    break
        return names

    async def _api_batch_images_local(names: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        connector = aiohttp.TCPConnector(force_close=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            for i in range(0, len(names), 50):
                batch  = names[i:i + 50]
                params = {
                    "action": "query", "prop": "pageimages",
                    "titles": "|".join(batch),
                    "pithumbsize": "500", "format": "json",
                }
                try:
                    async with session.get(
                        BASE_URL + "/api.php", params=params, headers=hdrs, timeout=timeout
                    ) as r:
                        if r.status != 200:
                            continue
                        jdata = await r.json(content_type=None)
                        for page in jdata.get("query", {}).get("pages", {}).values():
                            title = page.get("title", "")
                            src   = page.get("thumbnail", {}).get("source", "")
                            if title and src:
                                result[title] = to_railway(_clean_wikia_url(src))
                    await asyncio.sleep(0.2)
                except Exception:
                    continue
        return result

    def _parse_items(html: str) -> list[tuple[str, str | None]]:
        items = []
        for li in LI_PAT.finditer(html):
            block = li.group(1)
            nm    = NAME_PAT.search(block)
            name  = nm.group(1).strip() if nm else None
            if not name:
                t    = re.search(r'title="([^"]+)"', block)
                name = t.group(1) if t else None
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            ns_idx  = block.find("<noscript>")
            look    = block[:ns_idx] if ns_idx > 0 else block
            im      = DATA_SRC_PAT.search(look) or SRC_PAT.search(look)
            img_url = to_railway(_clean_wikia_url(im.group(1))) if im else None
            items.append((name, img_url))
        return items

    def _find_next(html: str) -> str | None:
        rel = re.search(
            r'<link\s+rel=["\'"]next["\'"]\s+href=["\'"]([^"\']+)["\'\']',
            html,
        )
        if rel:
            return rel.group(1)
        matches = re.findall(
            r'href=["\'](https://stealabrainrot\.fandom\.com/wiki/Category:Listed_Brainrots\?from=[^"\']+)["\']',
            html,
        )
        for c in reversed(matches):
            if c not in visited_urls:
                return c
        return None

    next_url: str | None = start_url
    page      = 0
    got_stuck = False

    while next_url and next_url not in visited_urls:
        visited_urls.add(next_url)
        page += 1
        count_before = len(all_results)

        html, method = await _fetch_html(next_url)
        if html:
            items    = _parse_items(html)
            all_results.extend(items)
            new_pg   = len(all_results) - count_before
            next_url = _find_next(html)

            if page > 1 and new_pg == 0:
                got_stuck = True
                method    = f"{method} — Stuck (Cached, 0 New Items)"
                if on_page:
                    await on_page(page, len(all_results), method, None)
                break
        else:
            next_url = None

        if on_page:
            await on_page(page, len(all_results), method, next_url)

        if next_url:
            await asyncio.sleep(0.8)

    if page <= 1 or got_stuck:
        api_names = await _api_get_all_names()
        new_names = [n for n in api_names if n not in seen_names]
        img_map   = await _api_batch_images_local(new_names) if new_names else {}
        api_added = 0
        for name in new_names:
            seen_names.add(name)
            img_url = img_map.get(name)
            all_results.append((name, img_url))
            api_added += 1
        if on_page and api_added:
            with_img = sum(1 for n in new_names if img_map.get(n))
            await on_page(-1, len(all_results), f"API Fallback (+{api_added} Names, {with_img} With Image)", None)

    return all_results

# ── /Setchannel ───────────────────────────────────────────────────────────────

@tree.command(name="setchannel", description="Set The Channel Where New Brainrot Thumbnail Notifications Will Be Sent.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(channel="Channel To Send New Pet Notifications To")
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(thinking=True, ephemeral=True)
    bot.notify_channel_id = channel.id
    await send_v2(interaction, [container(
        txt("## Notification Channel Set"),
        sep(),
        txt(
            f"**Channel:** {channel.mention}\n\n"
            f"New Pet Thumbnails Added Via `/addbrainrots`, `/fetchbrainrots`, Or `/scrapeallbrainrots` "
            f"Will Now Be Announced Here."
        ),
        sep(),
        txt(f"**Channel ID:** `{channel.id}`"),
    )])

# ── /Ping ─────────────────────────────────────────────────────────────────────

@tree.command(name="ping", description="Check The Bot's Latency And Connection Status.")
@discord.app_commands.default_permissions(administrator=True)
async def ping(interaction: discord.Interaction):
    start = time.monotonic()
    await interaction.response.defer(thinking=True, ephemeral=True)
    latency_ms = round((time.monotonic() - start) * 1000)
    ws_ms      = round(bot.latency * 1000)
    status     = "Excellent" if ws_ms < 80 else "Normal" if ws_ms < 150 else "Slow"
    await send_v2(interaction, [container(
        txt("## Pong"),
        sep(),
        txt(f"**Websocket Latency:** `{ws_ms}ms`"),
        sep(),
        txt(f"**Response Time:** `{latency_ms}ms`"),
        sep(),
        txt(f"**Status:** {status}"),
    )])

# ── /Addbrainrots ─────────────────────────────────────────────────────────────

@tree.command(name="addbrainrots", description="Add A New Brainrot With Its Thumbnail URL To GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def addpet(interaction: discord.Interaction, name: str, url: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    converted = to_railway(url)
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Add Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))])
        return
    if name in data:
        exist = data[name]
        await send_v2(interaction, [container(
            txt("## Brainrot Already Exists"),
            sep(),
            section(f"**{name}**", exist),
            sep(),
            txt(f"**Current URL:**\n```\n{shorten(exist, 240)}\n```"),
            sep(),
            txt(f"**New URL You Tried:**\n```\n{shorten(converted, 240)}\n```"),
            sep(),
            txt("Use `/updatebrainrots` To Change The URL."),
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
        await send_v2(interaction, [container(
            txt("## Brainrot Added Successfully"),
            sep(),
            section(f"**{title_case(name)}**\n\n{label_text}", converted),
            sep(),
            txt(f"**URL:**\n```\n{shorten(converted)}\n```"),
            sep(),
            txt("**GitHub** — Pushed & Sorted A To Z"),
        )])
        await notify_pet_added(name, converted)
    else:
        await send_v2(interaction, [container(txt("## Failed To Add Pet"), sep(), txt(f"**Pet:** `{name}`\n\n**GitHub** Push Failed\n```\n{err[:200]}\n```"))])

# ── /Updatebrainrots ──────────────────────────────────────────────────────────

@tree.command(name="updatebrainrots", description="Update The Thumbnail URL Of An Existing Brainrot.")
@discord.app_commands.default_permissions(administrator=True)
async def updatepet(interaction: discord.Interaction, name: str, url: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
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
        await send_v2(interaction, [container(
            txt("## Pet Updated Successfully"),
            sep(),
            section(f"**{name}**\n\n{label}", converted),
            sep(),
            txt(f"**New URL:**\n```\n{shorten(converted, 240)}\n```"),
            sep(),
            txt(f"**Previous URL:**\n```\n{shorten(old_url, 200)}\n```"),
            sep(),
            txt("**GitHub** — Pushed & Sorted A To Z"),
        )])
    else:
        await send_v2(interaction, [container(txt("## Failed To Update Pet"), sep(), txt(f"**Pet:** `{name}`\n\n**GitHub** Push Failed\n```\n{err[:200]}\n```"))])

# ── /Deletebrainrots ──────────────────────────────────────────────────────────

@tree.command(name="deletebrainrots", description="Delete A Brainrot And Its Thumbnail URL From GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def deletepet(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Delete Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))])
        return
    if name not in data:
        suggestions = [k for k in data if name.lower() in k.lower()]
        items = [txt(f"## Pet Not Found\n**Pet:** `{name}`")]
        if suggestions: items += [sep(), txt("**Similar Pets:**\n" + "\n".join(f" `{s}`" for s in suggestions[:8]))]
        await send_v2(interaction, [container(*items)]); return
    deleted_url = data[name]
    wh_url      = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [container(
            txt("## Confirm Delete Brainrot"),
            sep(),
            section(f"**{title_case(name)}**", deleted_url),
            sep(),
            txt(f"**URL:**\n```\n{shorten(deleted_url, 200)}\n```"),
            sep(),
            txt("⚠️ **Are You Sure You Want To Delete This Pet?**"),
            sep(),
            action_row(btn_yes(f"delbrainrot_yes:{name}"), btn_no("delbrainrot_no")),
        )],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
    bot._delpet_pending = getattr(bot, "_delpet_pending", {})
    bot._delpet_pending[name] = {"data": data, "sha": sha, "url": deleted_url}

# ── /Getbrainrots ─────────────────────────────────────────────────────────────

@tree.command(name="getbrainrots", description="Get The Thumbnail URL Of A Specific Brainrot.")
@discord.app_commands.default_permissions(administrator=True)
async def getpet(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        data, _ = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Get Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))]); return
    if name not in data:
        suggestions = [k for k in data if name.lower() in k.lower()]
        items = [txt(f"## Pet Not Found\n**Pet:** `{name}`")]
        if suggestions: items += [sep(), txt("**Did You Mean:**\n" + "\n".join(f" `{s}`" for s in suggestions[:5]))]
        await send_v2(interaction, [container(*items)]); return
    url_val = data[name]
    await send_v2(interaction, [container(
        txt("## Pet Thumbnail"),
        sep(),
        section(f"**{name}**", url_val),
        sep(),
        txt(f"**URL:**\n```\n{shorten(url_val)}\n```"),
    )])

# ── /Listbrainrots ─────────────────────────────────────────────────────────────

@tree.command(name="listbrainrots", description="List All Brainrots And Their Thumbnails Stored In GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def listbrainrots(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        data, _ = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** List Pets\n\n**Error:**\n```\n{e}\n```"))]); return
    railway_count = sum(1 for v in data.values() if is_railway(v))
    cdn_count     = sum(1 for v in data.values() if is_cdn(v))
    other_count   = len(data) - railway_count - cdn_count
    pet_names     = sorted(data.keys(), key=lambda x: x.lower())
    await followup(interaction, [container(
        txt("## Full Pet List"),
        sep(),
        txt(f"**Total Pets:** {len(data)}  •  **Wiki:** {railway_count}  •  **CDN:** {cdn_count}  •  **Other:** {other_count}"),
        sep(),
        txt("**All Pets (A To Z) — Loading Thumbnails Below...**"),
    )])
    for i in range(0, len(pet_names), 5):
        chunk = pet_names[i:i+5]
        items = []
        for j, pname in enumerate(chunk):
            if j > 0: items.append(sep())
            items.append(section(f"**{pname}**", data[pname]))
        await followup(interaction, [container(*items)])
        await asyncio.sleep(0.8)
    await followup(interaction, [container(txt(f"**Done  {len(pet_names)} Pets Listed.**"))])

# ── /Fetchbrainrots ───────────────────────────────────────────────────────────

@tree.command(name="fetchbrainrots", description="Auto-Fetch A Brainrot's Image From The Fandom Wiki And Save It.")
@discord.app_commands.default_permissions(administrator=True)
async def fetchpet(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True, ephemeral=True)

    img_map     = await api_batch_images([name])
    railway_url = img_map.get(name)

    if not railway_url:
        try:
            wikia_url, debug_info = await scrape_pet_image(name)
            if wikia_url:
                railway_url = to_railway(wikia_url)
        except Exception as e:
            await send_v2(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Pet:** `{name}`\n\n**Exception:**\n```\n{e}\n```"))]); return

    if not railway_url:
        page_url = FANDOM_BASE + quote(name.replace(" ", "_"))
        await send_v2(interaction, [container(
            txt("## Image Not Found On Wiki"),
            sep(),
            txt(f"**Pet:** `{name}`\n\nNo Image Found On The Wiki Page.\n\n**Page Checked:**\n```\n{page_url}\n```"),
        )]); return

    short_url = shorten(railway_url)
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Fetch Pet\n**Pet:** `{name}`\n\n**Error:**\n```\n{e}\n```"))]); return

    if name in data:
        existing_url = data[name]
        wh_url       = webhook_url(interaction)
        payload = {
            "flags": FLAGS_V2,
            "components": [container(
                txt("## Brainrot Already Exists"),
                sep(),
                section(f"**{title_case(name)}**\n\nAlready In GitHub — Overwrite?", existing_url),
                sep(),
                txt(f"**Current URL:**\n```\n{shorten(existing_url)}\n```"),
                sep(),
                txt(f"**Fetched URL:**\n```\n{shorten(short_url)}\n```"),
                sep(),
                action_row(btn_yes(f"overwrite_yes:{name}"), btn_no(f"overwrite_no:{name}")),
            )],
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(wh_url, json=payload) as r:
                if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
        bot._fetchbrainrots_pending       = getattr(bot, "_fetchbrainrots_pending", {})
        bot._fetchbrainrots_pending[name] = {"railway_url": railway_url, "data": data, "sha": sha}
        return

    key     = f"{interaction.id}"
    wh_url2 = webhook_url(interaction)
    payload2 = {
        "flags": FLAGS_V2,
        "components": [container(
            txt("## Brainrot Image Found"),
            sep(),
            section(f"**{title_case(name)}**", railway_url),
            sep(),
            txt(f"**Wiki URL:**\n```\n{short_url}\n```"),
            sep(),
            txt("**Save This Pet To GitHub?**"),
            sep(),
            action_row(
                btn("Save To GitHub", f"fetchbrainrots_save:{key}", style=2),
                btn("Discard",        f"fetchbrainrots_discard:{key}", style=2),
            ),
        )],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url2, json=payload2) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
    bot._fetchbrainrots_pending = getattr(bot, "_fetchbrainrots_pending", {})
    bot._fetchbrainrots_pending[key] = {"railway_url": railway_url, "data": data, "sha": sha, "name": name}

# ── /Syncbrainrots ────────────────────────────────────────────────────────────

@tree.command(name="syncbrainrots", description="Sync All Brainrot URLs To Railway Proxy Format.")
@discord.app_commands.default_permissions(administrator=True)
async def syncpets(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
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
        "components": [container(
            txt("## Sync Pets"),
            sep(),
            txt(f"**Total Pets:** {len(data)}\n**Found {len(needs_sync)} Pet(s) Not Synced:**\n\n{preview_lines}{more_note}"),
            sep(),
            txt("**Convert All To Railway Proxy Format?**"),
            sep(),
            action_row(btn_yes("syncbrainrots_yes"), btn_no("syncbrainrots_no")),
        )],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")
    bot._syncpets_pending = getattr(bot, "_syncpets_pending", {})
    bot._syncpets_pending["latest"] = {"data": data, "sha": sha, "to_convert": to_convert, "to_refetch": to_refetch}

# ── /Scrapeallbrainrots ───────────────────────────────────────────────────────

@tree.command(name="scrapeallbrainrots", description="Auto-Scrape All Brainrots From Category:Listed_Brainrots And Save To GitHub.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(
    skip_existing="Skip Brainrots Already In GitHub (Default: True)",
    dry_run="Preview Only — Do Not Save To GitHub",
)
async def scrapeallbrainrots(
    interaction: discord.Interaction,
    skip_existing: bool = True,
    dry_run:       bool = False,
):
    await interaction.response.defer(thinking=True, ephemeral=True)

    await send_v2(interaction, [container(
        txt("## Scraping Category: Listed Brainrots"),
        sep(),
        txt(f"**Skip Existing:** `{skip_existing}`   **Dry Run:** `{dry_run}`\n\n**Step 1 / 3** — Loading GitHub Data..."),
    )])
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await followup(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    page_log: list[str] = []

    async def on_page(page: int, total: int, method: str, next_url: str | None):
        if page == -1:
            line = f"**API Fallback** — {method}"
        else:
            nxt  = f"→ Next Starts At `{next_url.split('from=')[1]}`" if next_url and "from=" in next_url else "→ Last Page"
            line = f"**Page {page}** `{method}` — {total} Found So Far   {nxt}"
        page_log.append(line)
        await patch_msg(interaction, [container(
            txt("## Scanning Category Pages..."),
            sep(),
            txt(f"**Step 2 / 3** — Fetching Brainrots From Wiki\n\n" + "\n".join(page_log[-6:])),
        )])

    try:
        all_brainrots = await scrape_category_brainrots(on_page=on_page)
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

    if not all_brainrots:
        await followup(interaction, [container(
            txt("## No Brainrots Found"),
            sep(),
            txt("No Brainrots Found On The Category Page.\n\nThe Wiki May Be Blocking Requests."),
        )]); return

    to_add   = [(n, u) for n, u in all_brainrots if n not in data]
    existing = [(n, u) for n, u in all_brainrots if n in data]
    scan_log = "\n".join(page_log)

    await followup(interaction, [container(
        txt("## Category Scan Complete"),
        sep(),
        txt(
            f"**Total Found On Wiki:** {len(all_brainrots)}\n"
            f"**Already In GitHub:** {len(existing)}\n"
            f"**New (Will Add):** {len(to_add)}\n\n"
            f"**Page Log:**\n{scan_log}"
        ),
    )])

    if not to_add:
        await followup(interaction, [container(txt("## Nothing New"), sep(), txt(f"All {len(all_brainrots)} Brainrots Are Already In GitHub."))]); return

    if dry_run:
        preview = "\n".join(f" `{title_case(n)}`{'  — Has Image' if u else '  — No Image'}" for n, u in to_add[:30])
        more    = f"\n*...And {len(to_add) - 30} More*" if len(to_add) > 30 else ""
        await followup(interaction, [container(
            txt("## Dry Run — Preview New Brainrots"),
            sep(),
            txt(f"**{len(to_add)} Brainrots Will Be Added:**\n\n{preview}{more}"),
        )]); return

    added_ok:    list[str] = []
    no_image:    list[str] = []
    recent_done: list[str] = []

    async def _safe_patch(i: int, cur: str):
        bar = progress_bar(i, len(to_add))
        log = "\n".join(f" `{n}`" for n in recent_done[-8:]) or "*(None Yet...)*"
        try:
            await patch_msg(interaction, [container(
                txt("## Adding Brainrots..."),
                sep(),
                txt(f"**Step 3 / 3** — Saving To GitHub\n\n**Progress:** {bar}\n**Processing:** `{title_case(cur)}`\n\n**Recently Added:**\n{log}"),
            )])
        except Exception:
            pass  # Never let UI update crash the loop

    for i, (name, img_url) in enumerate(to_add):
        # Only update UI every 3 items to avoid rate limits
        if i % 3 == 0:
            await _safe_patch(i, name)
        final_url: str | None = img_url or None
        if not final_url:
            try:
                wikia_url, _ = await scrape_pet_image(name)
                if wikia_url:
                    final_url = to_railway(wikia_url)
            except Exception:
                pass
        if final_url:
            data[name] = final_url
            added_ok.append(name)
            recent_done.append(title_case(name))
            try:
                await notify_pet_added(name, final_url)
            except Exception:
                pass
        else:
            no_image.append(name)
        await asyncio.sleep(0.05)

    try:
        await patch_msg(interaction, [container(
            txt("## Pushing To GitHub..."),
            sep(),
            txt(f"**Progress:** {progress_bar(len(to_add), len(to_add))}\n**Processed:** {len(to_add)} Brainrots — Saving..."),
        )])
    except Exception:
        pass

    try:
        await push_pets(data, sha, f"[DK] ScrapeAll: Added {len(added_ok)} Brainrots From Category")
        push_ok = True
    except Exception as pe:
        push_ok = False; push_err = str(pe)

    if push_ok:
        added_log  = "\n".join(f" `{title_case(n)}`" for n in added_ok[:25])
        more_added = f"\n*...And {len(added_ok) - 25} More*" if len(added_ok) > 25 else ""
        no_img_txt = (
            f"\n\n**No Image Found ({len(no_image)}):**\n"
            + "\n".join(f" `{title_case(n)}`" for n in no_image[:10])
            + (f"\n*...And {len(no_image) - 10} More*" if len(no_image) > 10 else "")
        ) if no_image else ""
        await followup(interaction, [container(
            txt("## Scrape All Brainrots — Done!"),
            sep(),
            txt(
                f"**Total On Wiki:** {len(all_brainrots)}\n"
                f"**Added:** {len(added_ok)}\n"
                f"**Skipped (Already Exists):** {len(existing)}\n"
                f"**No Image:** {len(no_image)}\n\n"
                f"**Brainrots Added:**\n{added_log}{more_added}"
                f"{no_img_txt}\n\n"
                f"**GitHub** — Pushed & Sorted A To Z"
            ),
        )])
    else:
        await followup(interaction, [container(txt("## GitHub Push Failed"), sep(), txt(f"**Error:**\n```\n{push_err[:300]}\n```"))])

# ── /Refetchbroken ────────────────────────────────────────────────────────────

@tree.command(name="refetchbroken", description="Auto-Fetch Images For Brainrots With Broken Or Missing URLs.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(dry_run="Preview Only — Do Not Fix Anything")
async def refetchbroken(interaction: discord.Interaction, dry_run: bool = False):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        data, sha = await fetch_pets()
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return

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

    fixed_ok:    list[str] = []
    still_fail:  list[str] = []
    broken_list  = sorted(broken.items())
    broken_names = [n for n, _ in broken_list]

    await patch_msg(interaction, [container(
        txt("## Refetching Broken Images..."),
        sep(),
        txt(f"**Fetching Images Via Wiki API...**\n**Broken Pets:** {len(broken_list)}"),
    )])
    img_map = await api_batch_images(broken_names)

    for i, (name, _) in enumerate(broken_list):
        if i % 3 == 0:
            try:
                await patch_msg(interaction, [container(
                    txt("## Refetching Broken Images..."),
                    sep(),
                    txt(f"**Progress:** {progress_bar(i, len(broken_list))}\n**Processing:** `{title_case(name)}`\n\n**Fixed:** {len(fixed_ok)}   **Still Broken:** {len(still_fail)}"),
                )])
            except Exception:
                pass
        url = img_map.get(name)
        if not url:
            try:
                wikia_url, _ = await scrape_pet_image(name)
                if wikia_url:
                    url = to_railway(wikia_url)
            except Exception:
                pass
        if url:
            data[name] = url
            fixed_ok.append(name)
        else:
            still_fail.append(name)
        await asyncio.sleep(0.05)

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
        fixed_list = "\n".join(f" `{title_case(n)}`" for n in fixed_ok[:20])
        more_fixed = f"\n*...And {len(fixed_ok)-20} More*" if len(fixed_ok) > 20 else ""
        fail_list  = ("\n\n**Still No Image Found:**\n" + "\n".join(f" `{title_case(n)}`" for n in still_fail[:10])) if still_fail else ""
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

@tree.command(name="refetchall", description="Re-Fetch The Latest Images From Wiki For All Brainrots In GitHub.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(dry_run="Preview Only — Do Not Save", overwrite_existing="Overwrite Pets That Already Have Valid Images (Default: Only Fetch Missing)")
async def refetchall(interaction: discord.Interaction, dry_run: bool = False, overwrite_existing: bool = False):
    await interaction.response.defer(thinking=True, ephemeral=True)
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
        await followup(interaction, [container(txt("## Dry Run  Pets That Will Be Fetched"), sep(), txt(f"**{len(to_fetch)} Pet(s):**\n\n{preview}{more}"))])
        return

    fetched_ok:   list[str] = []
    fetch_failed: list[str] = []

    await patch_msg(interaction, [container(
        txt("## Refetching All Pets..."),
        sep(),
        txt(f"**Fetching Images Via Wiki API...**\n**Total:** {len(to_fetch)} Pets"),
    )])
    img_map = await api_batch_images(to_fetch)

    for i, name in enumerate(to_fetch):
        if i % 3 == 0:
            try:
                await patch_msg(interaction, [container(
                    txt("## Refetching All Pets..."),
                    sep(),
                    txt(f"**Progress:** {progress_bar(i, len(to_fetch))}\n**Processing:** `{title_case(name)}`\n\n**Success:** {len(fetched_ok)}    **Failed:** {len(fetch_failed)}"),
                )])
            except Exception:
                pass
        url = img_map.get(name)
        if not url:
            try:
                wikia_url, _ = await scrape_pet_image(name)
                if wikia_url:
                    url = to_railway(wikia_url)
            except Exception:
                pass
        if url:
            data[name] = url
            fetched_ok.append(name)
        else:
            fetch_failed.append(name)
        await asyncio.sleep(0.05)

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
        ok_list  = "\n".join(f" `{title_case(n)}`" for n in fetched_ok[:20])
        more_ok  = f"\n*...And {len(fetched_ok)-20} More*" if len(fetched_ok) > 20 else ""
        fail_txt = ("\n\n**No Image Found:**\n" + "\n".join(f" `{title_case(n)}`" for n in fetch_failed[:10])) if fetch_failed else ""
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

# ── Auto-Init GitHub Files ────────────────────────────────────────────────────

async def ensure_files():
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
    }
    files = [
        (GITHUB_FILE,           "{}",  True),
        (GITHUB_JSON_FILE,      "{}",  True),
        (GITHUB_TRAITS_FILE,    "",    False),
        (GITHUB_MUTATIONS_FILE, "",    False),
    ]
    for filename, empty_content, is_json in files:
        check_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{filename}?ref={GITHUB_BRANCH}"
        async with aiohttp.ClientSession() as s:
            async with s.get(check_url, headers=headers) as r:
                if r.status == 200:
                    continue
                if r.status != 404:
                    print(f"[DK] Could not check {filename}: HTTP {r.status}")
                    continue
            encoded    = base64.b64encode(empty_content.encode()).decode()
            body       = {"message": f"[DK] Init: Create {filename}", "content": encoded, "branch": GITHUB_BRANCH}
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
    await ensure_files()
    print(f"[DK] Logged In As: {bot.user}")
    print(f"[DK] Slash Commands Synced! ({len(tree.get_commands())} Commands)")
    print(f"[DK] GitHub Files:")
    print(f"[DK]    Pets:      {GITHUB_FILE}")
    print(f"[DK]    Traits:    {GITHUB_TRAITS_FILE}")
    print(f"[DK]    Mutations: {GITHUB_MUTATIONS_FILE}")
    print(f"[DK] Max Emoji Slots: Dynamic (Based On Boost Tier)")

# ── /Savetraits ───────────────────────────────────────────────────────────────

@tree.command(name="savetraits", description="Scrape Traits From Wiki & Sync Emoji IDs To GitHub (traits.lua).")
@discord.app_commands.default_permissions(administrator=True)
async def savetraits(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await followup(interaction, [container(txt("## Saving Traits To GitHub..."), sep(), txt(f"Scraping Wiki + Loading Emoji IDs  Pushing To `{GITHUB_TRAITS_FILE}`  Please Wait..."))])
    try:
        traits = await scrape_traits()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not traits:
        await followup(interaction, [container(txt("## No Traits Found"), sep(), txt("Could Not Find Any Traits On The Wiki Page."))]); return
    try:
        m_em, _      = await gh_fetch(GITHUB_MUTATIONS_FILE)
        emoji_map, _ = await gh_fetch(GITHUB_TRAITS_FILE)
        emoji_map    = {**emoji_map, **m_em}
    except Exception:
        emoji_map = {}
    try:
        existing, sha = await gh_fetch(GITHUB_TRAITS_FILE)
    except Exception:
        existing, sha = {}, ""
    data = dict(existing)
    for name, _ in traits:
        if name in emoji_map:   data[name] = emoji_map[name]
        elif name not in data:  data[name] = ""
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
            txt(f"**Total Traits:** {len(data)}  •  **With Emoji:** {mapped}  •  **Missing:** {unmapped}"),
            sep(),
            txt(f"**GitHub File:** `{GITHUB_TRAITS_FILE}`\n**Format:** `[\"Name\"] = \"<:Name:id>\",`"),
            sep(),
            txt(f"**Preview:**\n```lua\n{preview}\n```"),
        )])
    else:
        await followup(interaction, [container(txt("## Failed To Save Traits"), sep(), txt(f"**GitHub** Push Failed\n```\n{err[:200]}\n```"))])

# ── /Savemutations ────────────────────────────────────────────────────────────

@tree.command(name="savemutations", description="Scrape Mutations From Wiki & Sync Emoji IDs To GitHub (mutations.lua).")
@discord.app_commands.default_permissions(administrator=True)
async def savemutations(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await followup(interaction, [container(txt("## Saving Mutations To GitHub..."), sep(), txt(f"Scraping Wiki + Loading Emoji IDs  Pushing To `{GITHUB_MUTATIONS_FILE}`  Please Wait..."))])
    try:
        mutations = await scrape_mutations()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not mutations:
        await followup(interaction, [container(txt("## No Mutations Found"), sep(), txt("Could Not Find Any Mutations On The Wiki Page."))]); return
    try:
        t_em, _      = await gh_fetch(GITHUB_TRAITS_FILE)
        emoji_map, _ = await gh_fetch(GITHUB_MUTATIONS_FILE)
        emoji_map    = {**t_em, **emoji_map}
    except Exception:
        emoji_map = {}
    try:
        existing, sha = await gh_fetch(GITHUB_MUTATIONS_FILE)
    except Exception:
        existing, sha = {}, ""
    data = dict(existing)
    for name, _ in mutations:
        if name in emoji_map:   data[name] = emoji_map[name]
        elif name not in data:  data[name] = ""
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
            txt(f"**Total Mutations:** {len(data)}  •  **With Emoji:** {mapped}  •  **Missing:** {unmapped}"),
            sep(),
            txt(f"**GitHub File:** `{GITHUB_MUTATIONS_FILE}`\n**Format:** `[\"Name\"] = \"<:Name:id>\",`"),
            sep(),
            txt(f"**Preview:**\n```lua\n{preview}\n```"),
        )])
    else:
        await followup(interaction, [container(txt("## Failed To Save Mutations"), sep(), txt(f"**GitHub** Push Failed\n```\n{err[:200]}\n```"))])

# ── /Listtraits ───────────────────────────────────────────────────────────────

@tree.command(name="listtraits", description="Scrape & List All Traits From The Fandom Wiki With Thumbnails.")
@discord.app_commands.default_permissions(administrator=True)
async def listtraits(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await followup(interaction, [container(txt("## Scanning Traits Wiki Page..."), sep(), txt("Scraping `stealabrainrot.fandom.com/wiki/Traits`  Please Wait..."))])
    try:
        traits = await scrape_traits()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not traits:
        await followup(interaction, [container(txt("## No Traits Found"), sep(), txt("Could Not Find Any Traits On The Wiki Page."))]); return
    with_thumb = sum(1 for _, u in traits if u)
    await followup(interaction, [container(txt("## Traits List"), sep(), txt(f"**Total:** {len(traits)}    **With Thumbnail:** {with_thumb}    **No Image:** {len(traits)-with_thumb}\n\n**Loading All Below...**"))])
    for i in range(0, len(traits), 5):
        chunk = traits[i:i+5]
        items = []
        for j, (name, thumb) in enumerate(chunk):
            if j > 0: items.append(sep())
            items.append(section(f"**{name}**", thumb) if thumb else txt(f"**{name}**  *(No Image Found)*"))
        await followup(interaction, [container(*items)])
        await asyncio.sleep(0.8)
    name_lines = "\n".join(f"`{i+1}.` **{name}**" for i, (name, _) in enumerate(traits))
    await followup(interaction, [container(txt("## All Traits  Quick Reference"), sep(), txt(f"**{len(traits)} Traits (Wiki Order):**\n\n{name_lines}"))])

# ── /Listmutations ────────────────────────────────────────────────────────────

@tree.command(name="listmutations", description="Scrape & List All Mutations From The Fandom Wiki With Thumbnails.")
@discord.app_commands.default_permissions(administrator=True)
async def listmutations(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await followup(interaction, [container(txt("## Scanning Mutations Wiki Page..."), sep(), txt("Scraping `stealabrainrot.fandom.com/wiki/Mutations`  Please Wait..."))])
    try:
        mutations = await scrape_mutations()
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    if not mutations:
        await followup(interaction, [container(txt("## No Mutations Found"), sep(), txt("Could Not Find Any Mutations On The Wiki Page."))]); return
    with_thumb = sum(1 for _, u in mutations if u)
    await followup(interaction, [container(txt("## Mutations List"), sep(), txt(f"**Total:** {len(mutations)}    **With Thumbnail:** {with_thumb}    **No Image:** {len(mutations)-with_thumb}\n\n**Loading All Below...**"))])
    for i in range(0, len(mutations), 5):
        chunk = mutations[i:i+5]
        items = []
        for j, (name, thumb) in enumerate(chunk):
            if j > 0: items.append(sep())
            items.append(section(f"**{name}**", thumb) if thumb else txt(f"**{name}**  *(No Image Found)*"))
        await followup(interaction, [container(*items)])
        await asyncio.sleep(0.8)
    name_lines = "\n".join(f"`{i+1}.` **{name}**" for i, (name, _) in enumerate(mutations))
    await followup(interaction, [container(txt("## All Mutations  Quick Reference"), sep(), txt(f"**{len(mutations)} Mutations (Wiki Order):**\n\n{name_lines}"))])

# ── /Addemojis ────────────────────────────────────────────────────────────────

@tree.command(name="addemojis", description="Bulk-Add Trait/Mutation Emoji IDs  Saved To GitHub As Lua Table.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(emoji_data="Paste Lines Of  name:emoji_id  Or  <:name:id>  (One Per Line)")
async def addemojis(interaction: discord.Interaction, emoji_data: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    parsed = parse_emoji_input(emoji_data)
    if not parsed:
        await send_v2(interaction, [container(txt("## No Valid Emojis Parsed"), sep(), txt("**Accepted Formats (One Per Line):**\n```\nDefault:1498945977409863751\n<:Default:1498945977409863751>\n```"))]); return
    try:
        t_data, t_sha = await gh_fetch(GITHUB_TRAITS_FILE)
        m_data, m_sha = await gh_fetch(GITHUB_MUTATIONS_FILE)
        data = {**t_data, **m_data}
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Add Emojis\n\n**Error:**\n```\n{e}\n```"))]); return
    new_entries       = {k: v for k, v in parsed.items() if k not in data}
    overwrite_entries = {k: v for k, v in parsed.items() if k in data}
    for k, v in parsed.items():
        if k in t_data:                     t_data[k] = v
        if k in m_data:                     m_data[k] = v
        if k not in t_data and k not in m_data: t_data[k] = v
    try:
        await gh_push(GITHUB_TRAITS_FILE,    t_data, t_sha, f"[DK] Emojis Added: {', '.join(list(parsed.keys())[:5])}")
        await gh_push(GITHUB_MUTATIONS_FILE, m_data, m_sha, f"[DK] Emojis Added: {', '.join(list(parsed.keys())[:5])}")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if not ok:
        await send_v2(interaction, [container(txt("## Failed To Save Emojis"), sep(), txt(f"**GitHub** Push Failed\n```\n{err[:200]}\n```"))]); return
    max_len   = max((len(k) for k in parsed), default=0)
    lua_lines = []
    for k, v in sorted(parsed.items(), key=lambda x: x[0].lower()):
        ek  = k.replace("\\", "\\\\").replace('"', '\\"')
        ev  = v.replace("\\", "\\\\").replace('"', '\\"')
        pad = " " * (max_len - len(k) + 1)
        lua_lines.append('    ["' + ek + '"]' + pad + '= "' + ev + '",')
    lua_preview = "\n".join(lua_lines[:30])
    if len(lua_lines) > 30: lua_preview += f"\n    ... And {len(lua_lines)-30} More"
    new_list = "\n".join(f" `{k}`  `{v}`" for k in sorted(new_entries)[:15])
    ow_list  = "\n".join(f" `{k}`  `{v}`" for k in sorted(overwrite_entries)[:10])
    summary  = "\n".join(p for p in [
        f"**{len(new_entries)} New** Emoji(s) Added." if new_entries else "",
        f"**{len(overwrite_entries)} Existing** Emoji(s) Overwritten." if overwrite_entries else "",
    ] if p)
    items = [txt("## Emojis Saved Successfully"), sep(), txt(f"{summary}\n\n**GitHub Files:** `{GITHUB_TRAITS_FILE}` + `{GITHUB_MUTATIONS_FILE}`\n**Pushed & Sorted A To Z**")]
    if new_list:  items += [sep(), txt(f"**New Entries:**\n{new_list}")]
    if ow_list:   items += [sep(), txt(f"**Overwritten:**\n{ow_list}")]
    items += [sep(), txt(f"**Lua Preview:**\n```lua\n{lua_preview}\n```")]
    await send_v2(interaction, [container(*items)])

# ── /Listemojis ───────────────────────────────────────────────────────────────

@tree.command(name="listemojis", description="List All Saved Emoji Mappings From GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def listemojis(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        t_data, _ = await gh_fetch(GITHUB_TRAITS_FILE)
        m_data, _ = await gh_fetch(GITHUB_MUTATIONS_FILE)
        data = {**t_data, **m_data}
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** List Emojis\n\n**Error:**\n```\n{e}\n```"))]); return
    if not data:
        await send_v2(interaction, [container(txt("## No Emojis Saved Yet"), sep(), txt(f"**Files:** `{GITHUB_TRAITS_FILE}` + `{GITHUB_MUTATIONS_FILE}` Are Empty.\n\nUse `/addemojis` To Start Adding Emoji IDs."))]); return
    sorted_items = sorted(data.items(), key=lambda x: x[0].lower())
    max_len      = max((len(k) for k in data), default=0)
    lua_lines    = ['    ["' + k + '"]' + " " * (max_len - len(k) + 1) + '= "' + v + '",' for k, v in sorted_items]
    await followup(interaction, [container(txt("## All Saved Emojis"), sep(), txt(f"**Files:** `{GITHUB_TRAITS_FILE}` + `{GITHUB_MUTATIONS_FILE}`  •  **{len(data)} Total Entries**"))])
    for i in range(0, len(lua_lines), 30):
        await followup(interaction, [container(txt(f"```lua\n{chr(10).join(lua_lines[i:i+30])}\n```"))])
        await asyncio.sleep(0.5)
    await followup(interaction, [container(txt(f"**Done  {len(data)} Emoji Mappings Listed.**"))])

# ── /Getemojis ────────────────────────────────────────────────────────────────

@tree.command(name="getemojis", description="Get All Trait & Mutation Names From Wiki With Emoji Mapping Status.")
@discord.app_commands.default_permissions(administrator=True)
async def getemojis(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await followup(interaction, [container(txt("## Scanning Wiki For Names..."), sep(), txt("Scraping Traits & Mutations Pages  Please Wait..."))])
    try:
        traits, mutations = await asyncio.gather(scrape_traits(), scrape_mutations())
    except Exception as e:
        await followup(interaction, [container(txt("## Scrape Failed"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    try:
        t_em, _ = await gh_fetch(GITHUB_TRAITS_FILE)
        m_em, _ = await gh_fetch(GITHUB_MUTATIONS_FILE)
        existing_emojis = {**t_em, **m_em}
    except Exception:
        existing_emojis = {}
    trait_names    = [n for n, _ in traits]
    mutation_names = [n for n, _ in mutations]
    def status_lines(names):
        return "\n".join(
            f"`{'✓' if n in existing_emojis else '✗'}` **{n}**{f'    {existing_emojis[n]}' if n in existing_emojis else ''}"
            for n in names
        )
    mapped_t   = [n for n in trait_names    if n in existing_emojis]
    unmapped_t = [n for n in trait_names    if n not in existing_emojis]
    mapped_m   = [n for n in mutation_names if n in existing_emojis]
    unmapped_m = [n for n in mutation_names if n not in existing_emojis]
    await followup(interaction, [container(txt("## Traits  Emoji Status"), sep(), txt(f"**{len(trait_names)} Traits    Mapped: {len(mapped_t)}    Missing: {len(unmapped_t)}**\n\n{status_lines(trait_names)}"))])
    await asyncio.sleep(0.5)
    await followup(interaction, [container(txt("## Mutations  Emoji Status"), sep(), txt(f"**{len(mutation_names)} Mutations    Mapped: {len(mapped_m)}    Missing: {len(unmapped_m)}**\n\n{status_lines(mutation_names)}"))])
    await asyncio.sleep(0.5)
    if unmapped_t:
        await followup(interaction, [container(txt("## Unmapped Traits"), sep(), txt(f"**{len(unmapped_t)} Traits Still Need Emoji IDs:**\n\n```\n{chr(10).join(unmapped_t)[:1800]}\n```\n\nUse `/addemojis` To Bulk-Add."))])
        await asyncio.sleep(0.5)
    if unmapped_m:
        await followup(interaction, [container(txt("## Unmapped Mutations"), sep(), txt(f"**{len(unmapped_m)} Mutations Still Need Emoji IDs:**\n\n```\n{chr(10).join(unmapped_m)[:1800]}\n```\n\nUse `/addemojis` To Bulk-Add."))])
        await asyncio.sleep(0.5)
    await followup(interaction, [container(txt("## Summary"), sep(), txt(f"**GitHub Files:** `{GITHUB_TRAITS_FILE}` + `{GITHUB_MUTATIONS_FILE}`"))])

# ── /Deleteemoji ──────────────────────────────────────────────────────────────

@tree.command(name="deleteemoji", description="Delete An Emoji Mapping From GitHub.")
@discord.app_commands.default_permissions(administrator=True)
async def deleteemoji(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        t_data, t_sha = await gh_fetch(GITHUB_TRAITS_FILE)
        m_data, m_sha = await gh_fetch(GITHUB_MUTATIONS_FILE)
        data = {**t_data, **m_data}
    except Exception as e:
        await send_v2(interaction, [container(txt("## GitHub Error"), sep(), txt(f"**Operation:** Delete Emoji\n**Name:** `{name}`\n\n**Error:**\n```\n{e}\n```"))]); return
    if name not in data:
        suggestions = [k for k in data if name.lower() in k.lower()]
        items = [txt(f"## Emoji Not Found\n**Name:** `{name}`")]
        if suggestions: items += [sep(), txt("**Similar Names:**\n" + "\n".join(f" `{s}`" for s in suggestions[:8]))]
        await send_v2(interaction, [container(*items)]); return
    deleted_val = data.pop(name)
    if name in t_data: t_data.pop(name)
    if name in m_data: m_data.pop(name)
    try:
        await gh_push(GITHUB_TRAITS_FILE,    t_data, t_sha, f"[DK] Emoji Deleted: {name}")
        await gh_push(GITHUB_MUTATIONS_FILE, m_data, m_sha, f"[DK] Emoji Deleted: {name}")
        ok = True
    except Exception as e:
        ok = False; err = str(e)
    if ok:
        await send_v2(interaction, [container(txt("## Emoji Deleted"), sep(), txt(f"**Name:** `{name}`\n**Deleted Value:** `{deleted_val}`\n\n**GitHub** — Pushed & Sorted A To Z\n**Remaining:** {len(data)} Emojis"))])
    else:
        await send_v2(interaction, [container(txt("## Failed To Delete Emoji"), sep(), txt(f"**Name:** `{name}`\n\n**GitHub** Push Failed\n```\n{err[:200]}\n```"))])

# ── /Clearemojis ──────────────────────────────────────────────────────────────

@tree.command(name="clearemojis", description="Clear All Emoji IDs From GitHub Files.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(target="Which File(s) To Clear")
@discord.app_commands.choices(target=[
    discord.app_commands.Choice(name="traits.lua Only",            value="traits"),
    discord.app_commands.Choice(name="mutations.lua Only",         value="mutations"),
    discord.app_commands.Choice(name="traits.lua + mutations.lua", value="both"),
])
async def clearemojis(interaction: discord.Interaction, target: str = "all"):
    await interaction.response.defer(thinking=True, ephemeral=True)
    files_desc = {
        "traits":    f"`{GITHUB_TRAITS_FILE}`",
        "mutations": f"`{GITHUB_MUTATIONS_FILE}`",
        "both":      f"`{GITHUB_TRAITS_FILE}` + `{GITHUB_MUTATIONS_FILE}`",
    }
    wh_url  = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [container(
            txt("## Confirm Clear Emoji IDs"),
            sep(),
            txt(f"**About To Clear All Emoji IDs In:**\n{files_desc.get(target, target)}"),
            sep(),
            txt("⚠️ **This Action Cannot Be Undone — Are You Sure?**"),
            sep(),
            action_row(btn_yes(f"clearemojis_yes:{target}"), btn_no("clearemojis_no")),
        )],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            if r.status not in (200, 204): raise Exception(f"Discord {r.status}")

# ── /Syncemojis ───────────────────────────────────────────────────────────────

@tree.command(name="syncemojis", description="Scrape Wiki Names & Show Which Ones Are Missing Emoji IDs.")
@discord.app_commands.default_permissions(administrator=True)
async def syncemojis(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await followup(interaction, [container(txt("## Syncing Emoji Map With Wiki..."), sep(), txt("Scraping Traits & Mutations + Loading GitHub  Please Wait..."))])
    try:
        traits_res, mutations_res = await asyncio.gather(scrape_traits(), scrape_mutations())
        t_em, _ = await gh_fetch(GITHUB_TRAITS_FILE)
        m_em, _ = await gh_fetch(GITHUB_MUTATIONS_FILE)
        traits, mutations, existing_emojis = traits_res, mutations_res, {**t_em, **m_em}
    except Exception as e:
        await followup(interaction, [container(txt("## Error"), sep(), txt(f"**Error:**\n```\n{e}\n```"))]); return
    trait_names    = [n for n, _ in traits]
    mutation_names = [n for n, _ in mutations]
    all_names      = trait_names + [n for n in mutation_names if n not in trait_names]
    unmapped       = [n for n in all_names if n not in existing_emojis]
    mapped         = [n for n in all_names if n in existing_emojis]
    if not unmapped:
        await followup(interaction, [container(txt("## All Names Are Fully Mapped"), sep(), txt(f"**{len(all_names)} Names** All Have Emoji IDs. Nothing To Add!"))]); return
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
    await interaction.response.defer(thinking=True, ephemeral=True)

    guild_id  = interaction.guild.id
    bot_token = BOT_TOKEN

    async with aiohttp.ClientSession() as s:
        async with s.get(f"https://discord.com/api/v10/guilds/{guild_id}", headers={"Authorization": f"Bot {bot_token}"}) as rg:
            tier      = (await rg.json()).get("premium_tier", 0) if rg.status == 200 else 0
        max_slots = max_emoji_slots(tier)
        async with s.get(f"https://discord.com/api/v10/guilds/{guild_id}/emojis", headers={"Authorization": f"Bot {bot_token}"}) as r:
            if r.status == 200:
                current_emojis = await r.json()
                slots_used = len(current_emojis)
                slots_free = max_slots - slots_used
            else:
                slots_used = 0
                slots_free = max_slots

    await followup(interaction, [container(
        txt("## Auto Emoji Upload Starting..."), sep(),
        txt(f"**Step 1/4:** Scraping Wiki & Loading GitHub...\n**Mode:** `{mode}`    **Skip Existing:** `{skip_existing}`\n**Server Slots:** {slots_used}/{max_slots} Used    {slots_free} Free"),
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
        t_em, _         = await gh_fetch(GITHUB_TRAITS_FILE)
        m_em, emoji_sha = await gh_fetch(GITHUB_MUTATIONS_FILE)
        existing_emojis = {**t_em, **m_em}
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

    skipped_by_limit = []
    if len(to_upload) > slots_free:
        skipped_by_limit = [n for n, _ in to_upload[slots_free:]]
        to_upload        = to_upload[:slots_free]

    await followup(interaction, [container(txt("## Auto Emoji  Plan"), sep(), txt(
        f"**Traits Scraped:** {len(traits_data)}     **Mutations Scraped:** {len(mutations_data)}\n"
        f"**To Upload:** {len(to_upload)}     **No Image (Skip):** {len(no_image)}\n"
        f"**Already Mapped (Skipped):** {len(seen)-len(candidates) if skip_existing else 0}\n"
        + (f"**Slot Full — Cannot Upload ({len(skipped_by_limit)}):** {', '.join(f'`{n}`' for n in skipped_by_limit[:10])}{'...' if len(skipped_by_limit)>10 else ''}\n" if skipped_by_limit else "")
        + f"\n**Step 2/4:** Downloading, Resizing & Uploading To `{interaction.guild.name}`..."
    ))])

    if not to_upload:
        msg = "All Items Either Have No Image, Or Are Already Mapped."
        if skipped_by_limit:
            msg += f"\n\n**Server Is Full ({slots_used}/{max_slots})!**\nUse `/deleteserveremojis` To Free Up Slots First."
        await followup(interaction, [container(txt("## Nothing To Upload"), sep(), txt(f"{msg}\n\nRun `/getemojis` To See Current Status."))]); return

    uploaded_ok:   list[tuple[str, str]] = []
    failed_upload: list[str]             = []
    failed_dl:     list[str]             = []

    # Send the initial progress message once, then patch it in-place each batch
    await followup(interaction, [container(
        txt(f"**Uploading {len(to_upload)} Emoji(s)...** {progress_bar(0, len(to_upload))}"),
        sep(),
        txt(f"*Batch 1/{(len(to_upload)+2)//3} — Done: 0  Failed: 0*"),
    )])

    connector = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        for i in range(0, len(to_upload), 3):
            batch = to_upload[i:i+3]

            tasks = []
            for name, thumb in batch:
                async def process_one(n=name, t=thumb):
                    img = await download_and_resize(t, session)
                    if img is None: return ("dl_fail", n, f"Download Failed: {t[:80]}")
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
                    failed_dl.append(f"{res[1]}: {res[2]}")
                else:
                    err_detail = res[2] if len(res) > 2 else "Unknown Error"
                    if err_detail == "SERVER_FULL":
                        slot_full = True
                        skipped_by_limit.append(res[1])
                    else:
                        failed_upload.append(f"{res[1]}: {err_detail}")

            # Update progress bar in-place after processing each batch
            done_so_far = i + len(batch)
            bar = progress_bar(done_so_far, len(to_upload))
            await patch_msg(interaction, [container(
                txt(f"**Uploading {len(to_upload)} Emoji(s)...** {bar}"),
                sep(),
                txt(f"*Batch {i//3+1}/{(len(to_upload)+2)//3} — Done: {len(uploaded_ok)}  Failed: {len(failed_upload)+len(failed_dl)}*"),
            )])

            if slot_full:
                remaining = [n for n, _ in to_upload[i+3:]]
                skipped_by_limit.extend(remaining)
                await followup(interaction, [container(
                    txt("## Server Emoji Slots Are Full"), sep(),
                    txt(
                        f"**Server Reached Limit ({max_slots} Slots — Tier {tier}).**\n\n"
                        f"**Uploaded:** {len(uploaded_ok)}\n"
                        f"**Could Not Upload ({len(skipped_by_limit)}):**\n"
                        + "\n".join(f"• `{n}`" for n in skipped_by_limit[:20])
                        + (f"\n*...And {len(skipped_by_limit)-20} More*" if len(skipped_by_limit) > 20 else "")
                        + "\n\nUse `/deleteserveremojis` To Free Up Slots."
                    ),
                )])
                break
            await asyncio.sleep(3.0)

    ok_preview   = "\n".join(f"{es}  `{n}`" for n, es in uploaded_ok[:30])
    if len(uploaded_ok) > 30: ok_preview += f"\n*...And {len(uploaded_ok)-30} More*"
    all_not_done = failed_dl + list(failed_upload)
    fail_txt     = ("\n\n**Failed:**\n" + "\n".join(f"• {e}" for e in all_not_done[:10])) if all_not_done else ""
    no_img_txt   = (f"\n\n**No Image ({len(no_image)}):** " + ", ".join(f"`{n}`" for n, _ in no_image[:15])) if no_image else ""
    skipped_txt  = ""
    if skipped_by_limit:
        skipped_txt  = f"\n\n**Server Full — Not Uploaded ({len(skipped_by_limit)}):**\n"
        skipped_txt += "\n".join(f"• `{n}`" for n in skipped_by_limit[:20])
        if len(skipped_by_limit) > 20: skipped_txt += f"\n*...And {len(skipped_by_limit)-20} More*"

    akey   = str(interaction.id)
    wh_url = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [container(
            txt("## Auto Emoji Upload Complete"),
            sep(),
            txt(
                f"**Uploaded:** {len(uploaded_ok)}  •  **Failed:** {len(all_not_done)}"
                f"{fail_txt}{no_img_txt}{skipped_txt}"
                + (f"\n\n**Preview:**\n{ok_preview}" if ok_preview else "")
            ),
            sep(),
            txt("**Save These Emojis To GitHub?**"),
            sep(),
            txt("`traits.lua` + `mutations.lua` Will Be Updated."),
            sep(),
            action_row(
                btn("Save To GitHub", f"autoemoji_save:{akey}", style=2),
                btn("Discard",        f"autoemoji_discard:{akey}", style=2),
            ),
        )],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(wh_url, json=payload) as r:
            await r.read()

    bot._autoemoji_pending = getattr(bot, "_autoemoji_pending", {})
    bot._autoemoji_pending[akey] = {
        "uploaded_ok":    uploaded_ok,
        "traits_data":    traits_data,
        "mutations_data": mutations_data,
    }

# ── /Deleteserveremojis ───────────────────────────────────────────────────────

@tree.command(name="deleteserveremojis", description="Delete All Or Some Emojis From The Discord Server.")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(mode="Which Emojis To Delete")
@discord.app_commands.choices(mode=[
    discord.app_commands.Choice(name="All Emojis In Server",        value="all"),
    discord.app_commands.Choice(name="Only Emojis Uploaded By Bot", value="bot_only"),
])
async def deleteserveremojis(interaction: discord.Interaction, mode: str = "all"):
    if interaction.guild is None:
        await interaction.response.send_message("Must Be Used Inside A Server!", ephemeral=True); return
    await interaction.response.defer(thinking=True, ephemeral=True)
    wh_url  = webhook_url(interaction)
    payload = {
        "flags": FLAGS_V2,
        "components": [container(
            txt("## Confirm Delete Server Emojis"),
            sep(),
            txt(f"**Mode:** `{'All Emojis In Server' if mode == 'all' else 'Only Bot-Uploaded Emojis'}`"),
            sep(),
            txt(f"⚠️ **This Will Permanently Delete Emojis From `{interaction.guild.name}`!**\nThis Action Cannot Be Undone."),
            sep(),
            txt("**Are You Sure You Want To Continue?**"),
            sep(),
            action_row(btn_yes(f"delserver_yes:{mode}"), btn_no("delserver_no")),
        )],
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
    try:
        await interaction.response.defer()
    except Exception:
        pass

    # ── Delete Pet ────────────────────────────────────────────────────────────

    if custom_id.startswith("delbrainrot_yes:"):
        name = custom_id[len("delbrainrot_yes:"):]
        info = getattr(bot, "_delpet_pending", {}).pop(name, None)
        if not info: await patch_msg(interaction, [container(txt("## Session Expired"), sep(), txt("Please Run The Command Again."))]); return
        data = info["data"]; sha = info["sha"]; deleted_url = info["url"]
        del data[name]
        try:
            await push_pets(data, sha, f"[DK] Deleted: {name}")
            ok = True
        except Exception as e:
            ok = False; err = str(e)
        if ok:
            await patch_msg(interaction, [container(
                txt("## Pet Deleted Successfully"), sep(),
                section(f"**{name}**\n\n**Deleted URL:**\n```\n{shorten(deleted_url, 240)}\n```", deleted_url),
                sep(),
                txt(f"**GitHub** Deleted & Sorted A-Z\n**Remaining Pets:** {len(data)}"),
            )])
        else:
            await patch_msg(interaction, [container(txt("## Failed To Delete Pet"), sep(), txt(f"**GitHub** Push Failed\n```\n{err[:200]}\n```"))])

    elif custom_id == "delbrainrot_no":
        await patch_msg(interaction, [container(txt("## Delete Cancelled"), sep(), txt("No Changes Were Made."))])

    # ── Fetchpet Overwrite ────────────────────────────────────────────────────

    elif custom_id.startswith("overwrite_yes:"):
        pet_name = custom_id[len("overwrite_yes:"):]
        info     = getattr(bot, "_fetchbrainrots_pending", {}).pop(pet_name, None)
        if not info: await patch_msg(interaction, [container(txt("## Session Expired"), sep(), txt("Please Run The Command Again."))]); return
        railway_url = info["railway_url"]; data = info["data"]; sha = info["sha"]; old_url = data.get(pet_name, "")
        try:
            data[pet_name] = railway_url
            await push_pets(data, sha, f"[DK] Auto-Fetch Updated: {pet_name}")
            ok = True
        except Exception as e:
            ok = False; err = str(e)
        extra = f"\n\n**Previous URL:**\n```\n{shorten(old_url, 200)}\n```" if old_url else ""
        if ok:
            await patch_msg(interaction, [container(
                txt("## Brainrot Image Updated Successfully"), sep(),
                section(f"**{pet_name}**\n\n**Railway URL:**\n```\n{shorten(railway_url)}\n```{extra}", railway_url),
                sep(),
                txt("**GitHub** Pushed & Sorted A To Z"),
            )])
            await notify_pet_added(pet_name, railway_url)
        else:
            await patch_msg(interaction, [container(txt("## Failed To Save Pet"), sep(), txt(f"**GitHub** Push Failed\n```\n{err[:200]}\n```"))])

    elif custom_id.startswith("overwrite_no:"):
        pet_name = custom_id[len("overwrite_no:"):]
        info     = getattr(bot, "_fetchbrainrots_pending", {}).pop(pet_name, None)
        exist    = info["data"].get(pet_name, "") if info else ""
        await patch_msg(interaction, [container(
            txt("## Overwrite Cancelled"), sep(),
            section(f"**{pet_name}**\n\n**Kept Existing URL:**\n```\n{shorten(exist)}\n```", exist) if exist else txt(f"**{pet_name}** — Kept Existing Entry."),
        )])

    # ── Sync Pets ─────────────────────────────────────────────────────────────

    elif custom_id == "syncbrainrots_yes":
        pending = getattr(bot, "_syncpets_pending", {}).pop("latest", None)
        if not pending: await patch_msg(interaction, [container(txt("## Session Expired"), sep(), txt("Please Run The Command Again."))]); return
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
        refetch_img_map = await api_batch_images(list(to_refetch)) if to_refetch else {}
        for cname in to_refetch:
            await patch_msg(interaction, [container(txt("## Syncing..."), sep(), txt(f"**Progress:** {progress_bar(done, total)}\n\n**Processing:** `{cname}` *(Re-Fetch)*"))])
            url = refetch_img_map.get(cname)
            if not url:
                try:
                    wikia_url, _ = await scrape_pet_image(cname)
                    if wikia_url: url = to_railway(wikia_url)
                except Exception:
                    pass
            if url: data[cname] = url; converted_list.append(cname)
            else:   failed_list.append(f"{cname}: Image Not Found")
            done += 1
        try:
            await push_pets(data, sha, f"[DK] SyncPets: Converted {len(converted_list)} URLs")
            push_ok = True
        except Exception as pe:
            push_ok = False; push_err = str(pe)
        if push_ok:
            preview  = "\n".join(f" `{n}`" for n in sorted(converted_list)[:20])
            more     = f"\n*...And {len(converted_list)-20} More*" if len(converted_list) > 20 else ""
            fail_txt = ("\n\n**Failed:**\n" + "\n".join(f" {x}" for x in failed_list[:5])) if failed_list else ""
            await patch_msg(interaction, [container(txt("## Sync Complete"), sep(), txt(f"**Converted {len(converted_list)} Pet(s) To Railway:**\n\n{preview}{more}{fail_txt}\n\n**GitHub** Pushed & Sorted A To Z"))])
        else:
            await patch_msg(interaction, [container(txt("## Sync Failed"), sep(), txt(f"**GitHub Push Failed:**\n```\n{push_err[:300]}\n```"))])

    elif custom_id == "syncbrainrots_no":
        getattr(bot, "_syncpets_pending", {}).pop("latest", None)
        await patch_msg(interaction, [container(txt("## Sync Cancelled"), sep(), txt("No Changes Were Made To GitHub."))])

    # ── Clear Emojis ──────────────────────────────────────────────────────────

    elif custom_id.startswith("clearemojis_yes:"):
        target  = custom_id[len("clearemojis_yes:"):]
        results = []
        async def clear_file(filename: str, label: str):
            try:
                _, sha = await gh_fetch(filename)
                await gh_push(filename, {}, sha, f"[DK] Cleared All Emoji IDs: {filename}")
                results.append(f"`{label}` — Cleared Successfully")
            except Exception as e:
                results.append(f"`{label}` — Error: {str(e)[:80]}")
        if target == "traits":      await clear_file(GITHUB_TRAITS_FILE, "traits.lua")
        elif target == "mutations": await clear_file(GITHUB_MUTATIONS_FILE, "mutations.lua")
        elif target == "both":
            await clear_file(GITHUB_TRAITS_FILE, "traits.lua")
            await clear_file(GITHUB_MUTATIONS_FILE, "mutations.lua")
        result_txt = "\n".join(results)
        await patch_msg(interaction, [container(
            txt("## Clear Emojis  Done"), sep(),
            txt(f"{result_txt}\n\nRun `/autoemojis` To Upload New Emojis\nThen `/savetraits` + `/savemutations` To Sync New IDs."),
        )])

    elif custom_id == "clearemojis_no":
        await patch_msg(interaction, [container(txt("## Clear Cancelled"), sep(), txt("No Changes Were Made."))])

    # ── Delete Server Emojis ──────────────────────────────────────────────────

    elif custom_id.startswith("delserver_yes:"):
        mode     = custom_id[len("delserver_yes:"):]
        guild_id = getattr(bot, "_delserver_guild", None) or (interaction.guild.id if interaction.guild else None)
        if not guild_id: await patch_msg(interaction, [container(txt("## Session Expired"), sep(), txt("Please Run The Command Again."))]); return
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
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
                    t_em, _ = await gh_fetch(GITHUB_TRAITS_FILE)
                    m_em, _ = await gh_fetch(GITHUB_MUTATIONS_FILE)
                    bot_emoji_data = {**t_em, **m_em}
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
            await patch_msg(interaction, [container(txt("## Deleting..."), sep(), txt(f"**Total In Server:** {len(server_emojis)}\n**Will Delete:** {len(to_delete)}\n\nDeleting..."))])
            deleted_ok = []; deleted_fail = []
            for i, emoji in enumerate(to_delete):
                eid = emoji["id"]; ename = emoji["name"]
                if i % 10 == 0 and i > 0:
                    bar = progress_bar(i, len(to_delete))
                    await patch_msg(interaction, [container(txt(f"**Deleting...** {bar}\nDone: {len(deleted_ok)}     Failed: {len(deleted_fail)}"))])
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
        fail_txt = ("\n\n**Failed To Delete:**\n" + "\n".join(f" `{x}`" for x in deleted_fail[:10])) if deleted_fail else ""
        await patch_msg(interaction, [container(
            txt("## Server Emojis Deleted"), sep(),
            txt(
                f"**Deleted:** {len(deleted_ok)} Emojis\n"
                f"**Failed:** {len(deleted_fail)} Emojis\n"
                f"**Remaining In Server:** {len(server_emojis)-len(deleted_ok)} Emojis"
                f"{fail_txt}\n\n"
                f"Run `/autoemojis skip_existing:False` To Upload New Emojis."
            ),
        )])

    elif custom_id == "delserver_no":
        await patch_msg(interaction, [container(txt("## Delete Cancelled"), sep(), txt("No Emojis Were Deleted From The Server."))])

    # ── Fetchpet Save / Discard ───────────────────────────────────────────────

    elif custom_id.startswith("fetchbrainrots_save:"):
        key  = custom_id[len("fetchbrainrots_save:"):]
        info = getattr(bot, "_fetchbrainrots_pending", {}).pop(key, None)
        if not info:
            await patch_msg(interaction, [container(txt("## Session Expired"), sep(), txt("Please Run `/fetchbrainrots` Again."))]); return
        railway_url = info["railway_url"]; data = info["data"]; sha = info["sha"]; name = info["name"]
        try:
            data[name] = railway_url
            await push_pets(data, sha, f"[DK] Auto-Fetch Added: {name}")
            await patch_msg(interaction, [container(
                txt("## Brainrot Saved Successfully"),
                sep(),
                section(f"**{title_case(name)}**", railway_url),
                sep(),
                txt(f"**Wiki URL:**\n```\n{shorten(railway_url)}\n```"),
                sep(),
                txt("**GitHub** — Pushed & Sorted A To Z"),
            )])
            await notify_pet_added(name, railway_url)
        except Exception as e:
            await patch_msg(interaction, [container(txt("## Save Failed"), sep(), txt(f"**Error:**\n```\n{str(e)[:200]}\n```"))])

    elif custom_id.startswith("fetchbrainrots_discard:"):
        key  = custom_id[len("fetchbrainrots_discard:"):]
        info = getattr(bot, "_fetchbrainrots_pending", {}).pop(key, None)
        name = info["name"] if info else "Pet"
        await patch_msg(interaction, [container(txt("## Discarded"), sep(), txt(f"**{title_case(name)}** Was Not Saved To GitHub."))])

    # ── Auto Emoji Save / Discard ─────────────────────────────────────────────

    elif custom_id.startswith("autoemoji_save:"):
        key  = custom_id[len("autoemoji_save:"):]
        info = getattr(bot, "_autoemoji_pending", {}).pop(key, None)
        if not info:
            await patch_msg(interaction, [container(txt("## Session Expired"), sep(), txt("Please Run `/autoemojis` Again."))]); return
        uploaded_ok    = info["uploaded_ok"]
        traits_data    = info["traits_data"]
        mutations_data = info["mutations_data"]
        await patch_msg(interaction, [container(txt("## Saving To GitHub..."), sep(), txt(f"Pushing {len(uploaded_ok)} Emojis..."))])
        try:
            trait_names_set    = {n for n, _ in traits_data}
            mutation_names_set = {n for n, _ in mutations_data}
            t_data, t_sha = await gh_fetch(GITHUB_TRAITS_FILE)
            m_data, m_sha = await gh_fetch(GITHUB_MUTATIONS_FILE)
            traits_added = 0; mutations_added = 0
            for name, emoji_str in uploaded_ok:
                if name in trait_names_set:
                    t_data[name] = emoji_str; traits_added += 1
                elif name in mutation_names_set:
                    m_data[name] = emoji_str; mutations_added += 1
            if traits_added:
                await gh_push(GITHUB_TRAITS_FILE, t_data, t_sha, f"[DK] AutoEmojis: +{traits_added} Traits")
            if mutations_added:
                await gh_push(GITHUB_MUTATIONS_FILE, m_data, m_sha, f"[DK] AutoEmojis: +{mutations_added} Mutations")
            await patch_msg(interaction, [container(
                txt("## Emojis Saved To GitHub"),
                sep(),
                txt(f"**Traits Saved:** {traits_added} Emojis\n**Mutations Saved:** {mutations_added} Emojis\n\n**GitHub** — Pushed & Sorted A To Z"),
            )])
        except Exception as e:
            await patch_msg(interaction, [container(txt("## Save Failed"), sep(), txt(f"**Error:**\n```\n{str(e)[:300]}\n```"))])

    elif custom_id.startswith("autoemoji_discard:"):
        key = custom_id[len("autoemoji_discard:"):]
        getattr(bot, "_autoemoji_pending", {}).pop(key, None)
        await patch_msg(interaction, [container(txt("## Discarded"), sep(), txt("Emojis Were Not Saved To GitHub."))])


bot.run(BOT_TOKEN)
