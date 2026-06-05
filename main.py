"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     Discord Multi-System Bot                                ║
║                     Components V2  |  Single File Edition                   ║
║                     discord.py 2.4+  |  aiohttp  |  aiosqlite              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Install  :  pip install discord.py aiohttp aiosqlite                       ║
║  Run      :  python bot.py                                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  /ticket setup    — Configure ticket system                                 ║
║  /ticket panel    — Send ticket panel                                       ║
║  /ticket add      — Add user to ticket                                      ║
║  /ticket remove   — Remove user from ticket                                 ║
║  /ticket list     — List open tickets                                       ║
║  /ticket delete   — Force delete ticket                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  /invites setup   — Configure invite tracking channel                       ║
║  /invites check   — Check how many members a user has invited               ║
║  /invites top     — Show invite leaderboard                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  /welcome setup   — Configure welcome message system                        ║
║  /leave   setup   — Configure leave message system                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  /payment setup        — Configure VietQR + Casso                           ║
║  /payment create       — Generate a QR payment request                      ║
║  /payment check        — Check payment status by ref                        ║
║  /payment confirm      — Manually confirm a payment                         ║
║  /payment cancel       — Cancel a pending payment                           ║
║  /payment list         — List all payments with filter                      ║
║  /payment announce_all — Send daily summary to channel                      ║
║  /payment info         — Show current payment config                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  /ping             — Check bot latency                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import pathlib
import random
import string
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                              CREDENTIALS                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

TOKEN    = os.getenv("TOKEN", "")
OWNER_ID = 1498384419805986886
PREFIX   = "!"


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           TICKET CATEGORIES                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

TICKET_CATEGORIES = {
    "general": {
        "label":       "General Support",
        "description": "Questions And General Help",
    },
    "slot_transfer": {
        "label":       "Slot Transfers",
        "description": "Moving Or Transferring Slots",
    },
    "deposit": {
        "label":       "Deposit Support",
        "description": "Issues With Deposits Or Balances",
    },
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                              STRING TABLE                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

S = {
    # ── Panel ──────────────────────────────────────────────────────────────────
    "panel_title":            "Support Center",
    "panel_categories_title": "### Available Categories",
    "panel_placeholder":      "Choose Ticket Type...",

    # ── Modal ──────────────────────────────────────────────────────────────────
    "modal_title":            "Create A Support Ticket",
    "modal_subject_label":    "Subject",
    "modal_subject_ph":       "Briefly Describe Your Issue...",
    "modal_detail_label":     "Detailed Description",
    "modal_detail_ph":        "Provide As Much Detail As Possible...",

    # ── Ticket Info ────────────────────────────────────────────────────────────
    "ticket_header":          "Your Ticket Has Been Created. Our Support Team Will Respond As Soon As Possible.",
    "ticket_opened_by":       "Opened By",
    "ticket_subject":         "Subject",
    "ticket_created":         "Created",
    "ticket_issue":           "Issue Description",

    # ── Buttons ────────────────────────────────────────────────────────────────
    "btn_close":              "Close Ticket",
    "btn_claim":              "Claim Ticket",

    # ── Close Flow ─────────────────────────────────────────────────────────────
    "close_confirm_q":        "Are You Sure You Want To Close This Ticket?",
    "close_cancelled":        "Close Request Cancelled.",
    "close_header":           "Ticket Closed",
    "close_body":             "If You Need Further Assistance, Please Open A New Ticket.",
    "close_closed_by":        "Closed By",
    "close_countdown":        "This Ticket Will Be Deleted In **10 Seconds**.",

    # ── Claim Flow ─────────────────────────────────────────────────────────────
    "claim_staff_only":       "Only Staff Members Can Claim Tickets.",
    "claim_already":          "This Ticket Is Already Claimed By",
    "claim_success_ch":       "Has Claimed This Ticket",
    "claim_success_note":     "All Further Support Will Be Handled By This Staff Member.",
    "claim_ack":              "You Have Successfully Claimed This Ticket.",

    # ── Misc ───────────────────────────────────────────────────────────────────
    "transcript_ok":          "Transcript Generated Successfully.",
    "err_not_ticket":         "This Channel Is Not A Ticket.",
    "err_no_setup":           "System Not Configured. Run /ticket Setup First.",
    "err_no_category":        "Category Not Found. Please Run /ticket Setup First.",
    "err_open_ticket":        "You Already Have An Open Ticket",
    "err_open_close_first":   "Please Close It Before Opening A New One.",
    "err_panel_sent":         "Panel Sent Successfully.",
    "user_added":             "Has Been Added To This Ticket.",
    "user_removed":           "Has Been Removed From This Ticket.",

    # ── Setup ──────────────────────────────────────────────────────────────────
    "setup_ok":               "Setup Complete",
    "setup_category":         "Category",
    "setup_role":             "Support Role",
    "setup_log":              "Log Channel",
    "setup_not_set":          "Not Set",

    # ── List ───────────────────────────────────────────────────────────────────
    "list_empty":             "No Open Tickets Found.",
    "list_title":             "Open Tickets",
    "list_unclaimed":         "Unclaimed",

    # ── Category Labels ────────────────────────────────────────────────────────
    "cat_general_label":          "General Support",
    "cat_general_desc":           "Questions And General Help",
    "cat_slot_transfer_label":    "Slot Transfers",
    "cat_slot_transfer_desc":     "Moving Or Transferring Slots",
    "cat_deposit_label":          "Deposit Support",
    "cat_deposit_desc":           "Issues With Deposits Or Balances",
}

def t(key: str) -> str:
    return S.get(key, key)

def _cat_label(key: str) -> str:
    return S.get(f"cat_{key}_label", key)

def _cat_desc(key: str) -> str:
    return S.get(f"cat_{key}_desc", key)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                               LOGGING                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("Bot")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                             OWNER CHECK                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "Access Denied. This Command Is Restricted To The Bot Owner.",
                ephemeral=True,
            )
            return False
        return True
    return app_commands.check(predicate)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        COMPONENTS V2 HELPERS                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

V2_FLAG = 1 << 15

def _text(content: str) -> dict:
    return {"type": 10, "content": content}

def _separator(divider: bool = True, spacing: int = 1) -> dict:
    return {"type": 14, "divider": divider, "spacing": spacing}

def _select(custom_id: str, placeholder: str, options: list[dict]) -> dict:
    return {
        "type": 1,
        "components": [{
            "type":        3,
            "custom_id":   custom_id,
            "placeholder": placeholder,
            "min_values":  1,
            "max_values":  1,
            "options":     options,
        }],
    }

def _button(label: str, custom_id: str, style: int = 2) -> dict:
    return {"type": 2, "style": style, "label": label, "custom_id": custom_id}

def _action_row(*buttons) -> dict:
    return {"type": 1, "components": list(buttons)}

def _container(*components, accent_color: int = 0xFFFFFF) -> dict:
    return {"type": 17, "accent_color": accent_color, "components": list(components)}

def _section(text_content: str, thumbnail_url: str) -> dict:
    return {
        "type": 9,
        "components": [{"type": 10, "content": text_content}],
        "accessory":  {"type": 11, "media": {"url": thumbnail_url}},
    }

async def _v2_send(channel: discord.TextChannel, components: list[dict]) -> dict:
    url     = f"https://discord.com/api/v10/channels/{channel.id}/messages"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    payload = {"flags": V2_FLAG, "components": components}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            data = await r.json()
            if r.status not in (200, 201):
                log.error("V2 Send Error %s: %s", r.status, data)
            return data

async def _v2_respond(
    interaction: discord.Interaction,
    components: list[dict],
    *,
    ephemeral: bool = True,
) -> None:
    flags   = V2_FLAG | (64 if ephemeral else 0)
    url     = f"https://discord.com/api/v10/interactions/{interaction.id}/{interaction.token}/callback"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    payload = {"type": 4, "data": {"flags": flags, "components": components}}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            if r.status not in (200, 204):
                log.error("V2 Respond Error %s: %s", r.status, await r.json())

async def _v2_followup(
    interaction: discord.Interaction,
    components: list[dict],
    *,
    ephemeral: bool = True,
) -> None:
    flags   = V2_FLAG | (64 if ephemeral else 0)
    url     = f"https://discord.com/api/v10/webhooks/{interaction.application_id}/{interaction.token}"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    payload = {"flags": flags, "components": components}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload, headers=headers) as r:
            if r.status not in (200, 201):
                log.error("V2 Followup Error %s: %s", r.status, await r.json())

async def _v2_edit_msg(channel_id: int, message_id: int, components: list[dict]) -> None:
    url     = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
    headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
    payload = {"flags": V2_FLAG, "components": components}
    async with aiohttp.ClientSession() as s:
        async with s.patch(url, json=payload, headers=headers) as r:
            if r.status not in (200, 201):
                log.error("V2 Edit Error %s: %s", r.status, await r.json())


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      PERSISTENT STORE  (SQLite via aiosqlite)               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

DB_PATH = pathlib.Path("bot.db")

# In-memory config + runtime data (tickets, payments) — still kept per-guild
_STORE: dict[int, dict] = {}

_DEFAULTS: dict = {
    "ticket_category":  None,
    "log_channel":      None,
    "support_role":     None,
    "panel_channel":    None,
    "counter":          0,
    "tickets":          {},
    "welcome_channel":  None,
    "welcome_purchase": None,
    "welcome_rules":    None,
    "welcome_news":     None,
    "leave_channel":    None,
    "invites_channel":  None,
    "pay_bank_id":      "ICB",
    "pay_account_no":   "0907617630",
    "pay_account_name": "Nguyen Van A",
    "pay_casso_key":    None,
    "pay_log_channel":  None,
    "pay_confirm_role": None,
    "pay_timeout":      600,
    "payments":         {},
    "pay_announce_channel": None,
}

_CONFIG_KEYS = {
    "ticket_category", "log_channel", "support_role", "panel_channel",
    "counter", "welcome_channel", "welcome_purchase", "welcome_rules",
    "welcome_news", "pay_bank_id", "pay_account_no", "pay_account_name",
    "pay_casso_key", "pay_log_channel", "pay_confirm_role", "pay_timeout",
    "pay_announce_channel", "leave_channel", "invites_channel",
}

# ── Database init ──────────────────────────────────────────────────────────────

async def _db_init() -> None:
    """Create all tables if they don't exist yet."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            -- Guild config (one row per guild)
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id    INTEGER PRIMARY KEY,
                data_json   TEXT    NOT NULL DEFAULT '{}'
            );

            -- Ticket log (closed tickets kept for history)
            CREATE TABLE IF NOT EXISTS ticket_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                ticket_id   TEXT    NOT NULL,
                author_id   INTEGER NOT NULL,
                author_name TEXT    NOT NULL,
                category    TEXT,
                subject     TEXT,
                description TEXT,
                opened_at   TEXT,
                closed_by   INTEGER,
                closed_at   TEXT
            );

            -- Payment records
            CREATE TABLE IF NOT EXISTS payments (
                ref             TEXT    NOT NULL,
                guild_id        INTEGER NOT NULL,
                user_id         INTEGER NOT NULL,
                amount          INTEGER NOT NULL,
                description     TEXT,
                channel_id      INTEGER,
                message_id      INTEGER,
                status          TEXT    NOT NULL DEFAULT 'pending',
                created_at      REAL    NOT NULL,
                confirmed_at    REAL,
                confirmed_by_tx TEXT,
                PRIMARY KEY (ref, guild_id)
            );

            -- Invite tracking (cumulative per inviter per guild)
            CREATE TABLE IF NOT EXISTS invite_stats (
                guild_id    INTEGER NOT NULL,
                inviter_id  INTEGER NOT NULL,
                total_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, inviter_id)
            );
        """)
        await db.commit()
    log.info("Database Initialised At %s", DB_PATH)


# ── Load / Save guild config ───────────────────────────────────────────────────

async def _db_load_all() -> None:
    """Load all guild configs from SQLite into _STORE."""
    global _STORE
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT guild_id, data_json FROM guild_config") as cur:
            rows = await cur.fetchall()
    for guild_id, data_json in rows:
        try:
            saved = json.loads(data_json)
        except Exception:
            saved = {}
        d = dict(_DEFAULTS)
        for k in _CONFIG_KEYS:
            if k in saved:
                d[k] = saved[k]
        # Restore runtime dicts
        d["tickets"]  = saved.get("tickets",  {})
        d["payments"] = {}  # payments loaded lazily from DB
        _STORE[int(guild_id)] = d
    log.info("Loaded SQLite — %d Guild(s) Restored.", len(_STORE))


async def _db_save_guild(guild_id: int) -> None:
    """Persist one guild's config to SQLite (async-safe)."""
    d = _STORE.get(guild_id)
    if d is None:
        return
    blob = {k: d[k] for k in _CONFIG_KEYS if k in d}
    blob["tickets"] = d.get("tickets", {})
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO guild_config(guild_id, data_json) VALUES(?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET data_json=excluded.data_json",
            (guild_id, json.dumps(blob, ensure_ascii=False)),
        )
        await db.commit()


def _save_data() -> None:
    """Synchronous shim — schedules async save for each guild."""
    for gid in list(_STORE):
        asyncio.get_event_loop().create_task(_db_save_guild(gid))


def _gdata(guild_id: int) -> dict:
    if guild_id not in _STORE:
        _STORE[guild_id] = dict(_DEFAULTS)
        _STORE[guild_id]["tickets"]  = {}
        _STORE[guild_id]["payments"] = {}
    return _STORE[guild_id]


def _next_id(guild_id: int) -> str:
    d = _gdata(guild_id)
    d["counter"] += 1
    asyncio.get_event_loop().create_task(_db_save_guild(guild_id))
    return f"{d['counter']:04d}"


# ── Invite stats helpers ───────────────────────────────────────────────────────

async def _invite_add(guild_id: int, inviter_id: int) -> int:
    """Increment invite count for inviter and return new total."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO invite_stats(guild_id, inviter_id, total_count) VALUES(?,?,1) "
            "ON CONFLICT(guild_id, inviter_id) DO UPDATE SET total_count = total_count + 1",
            (guild_id, inviter_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT total_count FROM invite_stats WHERE guild_id=? AND inviter_id=?",
            (guild_id, inviter_id),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 1


async def _invite_get(guild_id: int, inviter_id: int) -> int:
    """Return cumulative invite count for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT total_count FROM invite_stats WHERE guild_id=? AND inviter_id=?",
            (guild_id, inviter_id),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def _invite_leaderboard(guild_id: int, limit: int = 10) -> list[tuple[int, int]]:
    """Return top inviters as list of (inviter_id, total_count)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT inviter_id, total_count FROM invite_stats "
            "WHERE guild_id=? ORDER BY total_count DESC LIMIT ?",
            (guild_id, limit),
        ) as cur:
            rows = await cur.fetchall()
    return [(r[0], r[1]) for r in rows]


# ── Payment DB helpers ─────────────────────────────────────────────────────────

async def _db_save_payment(guild_id: int, ref: str, p: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments(ref,guild_id,user_id,amount,description,channel_id,"
            "message_id,status,created_at,confirmed_at,confirmed_by_tx) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(ref,guild_id) DO UPDATE SET "
            "status=excluded.status, confirmed_at=excluded.confirmed_at, "
            "confirmed_by_tx=excluded.confirmed_by_tx",
            (
                ref, guild_id, p["user_id"], p["amount"], p.get("description",""),
                p["channel_id"], p["message_id"], p["status"],
                p["created_at"], p.get("confirmed_at"), p.get("confirmed_by_tx"),
            ),
        )
        await db.commit()


async def _db_log_ticket_close(guild_id: int, td: dict, closed_by_id: int) -> None:
    """Insert a closed-ticket record into ticket_log."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO ticket_log(guild_id,ticket_id,author_id,author_name,"
            "category,subject,description,opened_at,closed_by,closed_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                guild_id,
                td.get("id", "0000"),
                td.get("author_id", 0),
                td.get("author_name", ""),
                td.get("category", ""),
                td.get("subject", ""),
                td.get("description", ""),
                td.get("created_at", ""),
                closed_by_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           VIETQR HELPER                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

VIETQR_BANKS = {
    "ACB":         "ACB",
    "BIDV":        "BIDV",
    "MB":          "MB",
    "MSB":         "MSB",
    "OCB":         "OCB",
    "SCB":         "SCB",
    "SHB":         "SHB",
    "TCB":         "TCB",
    "TPB":         "TPB",
    "VCB":         "VCB",
    "VIB":         "VIB",
    "VPB":         "VPB",
    "VIETINBANK":  "ICB",
    "AGRIBANK":    "VBA",
    "TPBANK":      "TPB",
    "SACOMBANK":   "STB",
    "HDBANK":      "HDB",
    "SEABANK":     "SEAB",
    "ABBANK":      "ABB",
    "BAOVIETBANK": "BVB",
}

def _vietqr_url(
    bank_id: str,
    account_no: str,
    account_name: str,
    amount: int,
    ref: str,
) -> str:
    from urllib.parse import quote
    base  = f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png"
    query = (
        f"?amount={amount}"
        f"&addInfo={quote(ref)}"
        f"&accountName={quote(account_name)}"
    )
    return base + query

def _gen_ref(guild_id: int, user_id: int) -> str:
    chars  = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"PAY{suffix}"


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                         CASSO AUTO-CONFIRM                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

async def _casso_get_transactions(api_key: str, from_id: int = 0) -> list[dict]:
    url     = "https://oauth.casso.vn/v2/transactions"
    headers = {"Authorization": f"Apikey {api_key}"}
    params  = {"page": 1, "pageSize": 20}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                url, headers=headers, params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    log.warning("Casso API Error: %s", r.status)
                    return []
                data = await r.json()
                return data.get("data", {}).get("records", [])
    except Exception as e:
        log.warning("Casso Poll Error: %s", e)
        return []


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                         PAYMENT STORE HELPERS                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def _payment_create(
    guild_id: int,
    user_id: int,
    amount: int,
    description: str,
    channel_id: int,
    message_id: int,
    ref: str = "",
) -> dict:
    d = _gdata(guild_id)
    if not ref:
        ref = _gen_ref(guild_id, user_id)
        while ref in d["payments"]:
            ref = _gen_ref(guild_id, user_id)
    payment = {
        "ref":             ref,
        "guild_id":        guild_id,
        "user_id":         user_id,
        "amount":          amount,
        "description":     description,
        "channel_id":      channel_id,
        "message_id":      message_id,
        "status":          "pending",
        "created_at":      time.time(),
        "confirmed_at":    None,
        "confirmed_by_tx": None,
    }
    d["payments"][ref] = payment
    asyncio.get_event_loop().create_task(_db_save_payment(guild_id, ref, payment))
    return payment

def _payment_get(guild_id: int, ref: str) -> dict | None:
    return _gdata(guild_id)["payments"].get(ref)

def _payment_confirm(guild_id: int, ref: str, tx_id: str) -> bool:
    p = _payment_get(guild_id, ref)
    if not p or p["status"] != "pending":
        return False
    p["status"]          = "confirmed"
    p["confirmed_at"]    = time.time()
    p["confirmed_by_tx"] = tx_id
    asyncio.get_event_loop().create_task(_db_save_payment(guild_id, ref, p))
    return True

def _payment_expire(guild_id: int, ref: str) -> bool:
    p = _payment_get(guild_id, ref)
    if not p or p["status"] != "pending":
        return False
    p["status"] = "expired"
    asyncio.get_event_loop().create_task(_db_save_payment(guild_id, ref, p))
    return True


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      UI — TICKET PANEL & SELECT                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=v["label"], value=k, description=v["description"])
            for k, v in TICKET_CATEGORIES.items()
        ]
        super().__init__(
            placeholder="Choose Ticket Type...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket:category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            CreateModal(self.values[0], interaction.guild_id)
        )


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CategorySelect())


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                      UI — TICKET CREATE MODAL                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class CreateModal(discord.ui.Modal, title="Create A Support Ticket"):
    def __init__(self, category_key: str, guild_id: int = 0):
        super().__init__(title=t("modal_title"))
        self.category_key = category_key
        self.guild_id     = guild_id
        self.subject = discord.ui.TextInput(
            label=t("modal_subject_label"),
            placeholder=t("modal_subject_ph"),
            max_length=100,
            required=True,
        )
        self.detail = discord.ui.TextInput(
            label=t("modal_detail_label"),
            placeholder=t("modal_detail_ph"),
            style=discord.TextStyle.paragraph,
            min_length=20,
            max_length=1000,
            required=True,
        )
        self.add_item(self.subject)
        self.add_item(self.detail)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await _create_ticket(
            interaction=interaction,
            category_key=self.category_key,
            subject=self.subject.value,
            description=self.detail.value,
        )


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    UI — TICKET CONTROL & CONFIRM CLOSE                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class ControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close",
        row=0,
    )
    async def close(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_message(
            t("close_confirm_q"),
            view=ConfirmCloseView(),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.success,
        custom_id="ticket:claim",
        row=0,
    )
    async def claim(self, interaction: discord.Interaction, _: discord.ui.Button):
        await _claim_ticket(interaction)


class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content=t("close_countdown"), view=None)
        await _do_close_ticket(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content=t("close_cancelled"), view=None)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                              BOT SETUP                                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

intents                 = discord.Intents.default()
intents.message_content = True
intents.members         = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    await _db_init()
    await _db_load_all()
    bot.add_view(PanelView())
    bot.add_view(ControlView())
    await bot.tree.sync()
    await bot.change_presence(status=discord.Status.online)
    if not payment_checker.is_running():
        payment_checker.start()
    if not payment_expiry.is_running():
        payment_expiry.start()
    if not daily_summary_task.is_running():
        daily_summary_task.start()
    # Pre-cache invites for all guilds
    for guild in bot.guilds:
        await _refresh_invite_cache(guild)
    log.info(
        "Logged In As %s  |  Guilds: %d  |  Owner ID: %d",
        bot.user, len(bot.guilds), OWNER_ID,
    )


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                       PAYMENT DAILY SUMMARY HELPER                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

async def _send_daily_summary(
    guild_id:   int,
    channel_id: int,
    *,
    note:  str | None = None,
    actor: str        = "Auto",
) -> None:
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return

    d        = _gdata(guild_id)
    now      = time.time()
    today_ts = now - 86400

    confirmed = [
        (ref, p) for ref, p in d["payments"].items()
        if p["status"] == "confirmed"
        and p.get("confirmed_at", 0) >= today_ts
    ]
    confirmed.sort(key=lambda x: x[1].get("confirmed_at", 0))

    date_str  = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    ts_now    = int(now)
    note_line = f"\n\n**Note:** {note}" if note else ""

    if not confirmed:
        await _v2_send(channel, [  # type: ignore
            _container(
                _text(f"## 💰 Daily Payment Summary — {date_str}"),
                _separator(),
                _text(
                    f"**Total Payments:** 0\n"
                    f"**Total Revenue:** `0 VND`\n\n"
                    f"No Confirmed Payments In The Last 24 Hours."
                    f"{note_line}"
                ),
                _separator(),
                _text(f"-# Auto-Generated At 00:00  —  <t:{ts_now}:F>"),
            )
        ])
        return

    total_vnd = sum(p["amount"] for _, p in confirmed)
    rows      = []
    for ref, p in confirmed:
        payer   = guild.get_member(p["user_id"])
        p_str   = payer.mention if payer else f"<@{p['user_id']}>"
        conf_ts = int(p.get("confirmed_at", p["created_at"]))
        rows.append(f"✅ `{ref}` — **{p['amount']:,} VND** — {p_str} — <t:{conf_ts}:t>")

    await _v2_send(channel, [  # type: ignore
        _container(
            _text(f"## 💰 Daily Payment Summary — {date_str}"),
            _separator(),
            _text(
                f"**Total Payments:** {len(confirmed)}\n"
                f"**Total Revenue:** `{total_vnd:,} VND`"
                f"{note_line}"
            ),
            _separator(),
            _text("\n".join(rows)),
            _separator(),
            _text(f"-# Auto-Generated At 00:00  —  <t:{ts_now}:F>"),
        )
    ])
    log.info(
        "Daily Summary Sent To #%s — %d Payments — %s VND — By %s",
        channel, len(confirmed), total_vnd, actor,
    )


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               BACKGROUND TASK — PAYMENT AUTO-CONFIRM (15s)                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@tasks.loop(seconds=15)
async def payment_checker():
    for guild_id, gd in list(_STORE.items()):
        casso_key = gd.get("pay_casso_key")
        if not casso_key:
            continue
        pending = {ref: p for ref, p in gd["payments"].items() if p["status"] == "pending"}
        if not pending:
            continue
        txs = await _casso_get_transactions(casso_key)
        for tx in txs:
            desc   = str(tx.get("description", "") or tx.get("memo", "")).upper()
            amount = int(tx.get("amount", 0))
            tx_id  = str(tx.get("id", ""))
            for ref, p in list(pending.items()):
                if p["status"] != "pending":
                    continue
                if ref.upper() in desc and amount >= p["amount"]:
                    if _payment_confirm(guild_id, ref, tx_id):
                        await _notify_payment_confirmed(guild_id, ref)
                        pending.pop(ref, None)
                        break

@payment_checker.before_loop
async def before_checker():
    await bot.wait_until_ready()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               BACKGROUND TASK — PAYMENT EXPIRY CHECK (60s)                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@tasks.loop(seconds=60)
async def payment_expiry():
    now = time.time()
    for guild_id, gd in list(_STORE.items()):
        timeout = gd.get("pay_timeout", 600)
        for ref, p in list(gd["payments"].items()):
            if p["status"] != "pending":
                continue
            if now - p["created_at"] > timeout:
                if _payment_expire(guild_id, ref):
                    await _notify_payment_expired(guild_id, ref)

@payment_expiry.before_loop
async def before_expiry():
    await bot.wait_until_ready()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               BACKGROUND TASK — DAILY SUMMARY (00:00 UTC+7)                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@tasks.loop(minutes=1)
async def daily_summary_task():
    now_utc7 = datetime.now(timezone.utc).astimezone(
        __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo("Asia/Ho_Chi_Minh")
    )
    if now_utc7.hour != 0 or now_utc7.minute != 0:
        return
    for guild_id, gd in list(_STORE.items()):
        ch_id = gd.get("pay_announce_channel")
        if not ch_id:
            continue
        await _send_daily_summary(guild_id, ch_id, actor="Daily Auto-Task")

@daily_summary_task.before_loop
async def before_daily():
    await bot.wait_until_ready()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        PAYMENT NOTIFICATIONS                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

async def _notify_payment_confirmed(guild_id: int, ref: str):
    d = _gdata(guild_id)
    p = d["payments"].get(ref)
    if not p:
        return
    guild  = bot.get_guild(guild_id)
    if not guild:
        return
    member = guild.get_member(p["user_id"])
    ts     = int(time.time())

    try:
        await _v2_edit_msg(p["channel_id"], p["message_id"], [
            _container(
                _text("## ✅ Payment Confirmed"),
                _separator(),
                _text(
                    f"**Reference:** `{ref}`\n"
                    f"**Amount:** `{p['amount']:,} VND`\n"
                    f"**Status:** ✅ Confirmed\n"
                    f"**Payer:** {member.mention if member else '<@' + str(p['user_id']) + '>'}\n"
                    f"-# Confirmed <t:{ts}:R>"
                ),
            )
        ])
    except Exception as e:
        log.warning("Could Not Edit Payment Message: %s", e)

    log_ch_id = d.get("pay_log_channel")
    if log_ch_id:
        log_ch = guild.get_channel(log_ch_id)
        if log_ch:
            ping_role = d.get("pay_confirm_role")
            ping_txt  = f"<@&{ping_role}> " if ping_role else ""
            await _v2_send(log_ch, [  # type: ignore
                _container(
                    _text("## ✅ Payment Received"),
                    _separator(),
                    _section(
                        f"**Reference:** `{ref}`\n"
                        f"**Amount:** `{p['amount']:,} VND`\n"
                        f"**Payer:** {member.mention if member else 'ID: ' + str(p['user_id'])}\n"
                        f"**TX ID:** `{p.get('confirmed_by_tx', 'N/A')}`",
                        member.display_avatar.with_size(256).url if member
                        else "https://cdn.discordapp.com/embed/avatars/0.png",
                    ),
                    _separator(),
                    _text(f"{ping_txt}-# <t:{ts}:F>"),
                )
            ])

    log.info("Payment %s Confirmed For User %s — %s VND", ref, p["user_id"], p["amount"])


async def _notify_payment_expired(guild_id: int, ref: str):
    d = _gdata(guild_id)
    p = d["payments"].get(ref)
    if not p:
        return

    try:
        await _v2_edit_msg(p["channel_id"], p["message_id"], [
            _container(
                _text("## ⏰ Payment Expired"),
                _separator(),
                _text(
                    f"**Reference:** `{ref}`\n"
                    f"**Amount:** `{p['amount']:,} VND`\n"
                    f"**Status:** ⏰ Expired — No Payment Received\n"
                    f"-# This Message Will Be Deleted In 5 Seconds."
                ),
            )
        ])
    except Exception as e:
        log.warning("Could Not Edit Expired Payment Message: %s", e)

    await asyncio.sleep(5)
    try:
        url     = f"https://discord.com/api/v10/channels/{p['channel_id']}/messages/{p['message_id']}"
        headers = {"Authorization": f"Bot {TOKEN}"}
        async with aiohttp.ClientSession() as s:
            async with s.delete(url, headers=headers) as r:
                if r.status not in (200, 204):
                    log.warning("Could Not Delete Expired Payment Message: %s", r.status)
    except Exception as e:
        log.warning("Could Not Delete Expired Payment Message: %s", e)

    log.info("Payment %s Expired And Message Deleted", ref)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                    INVITE CACHE  (snapshot before each join)                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# guild_id -> {code: uses}
_invite_cache: dict[int, dict[str, int]] = {}

async def _refresh_invite_cache(guild: discord.Guild) -> None:
    try:
        invites = await guild.invites()
        _invite_cache[guild.id] = {inv.code: (inv.uses or 0) for inv in invites}
    except Exception:
        pass

@bot.event
async def on_invite_create(invite: discord.Invite):
    if invite.guild:
        await _refresh_invite_cache(invite.guild)  # type: ignore

@bot.event
async def on_invite_delete(invite: discord.Invite):
    if invite.guild:
        await _refresh_invite_cache(invite.guild)  # type: ignore


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                          EVENT — MEMBER JOIN                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    d     = _gdata(guild.id)

    ts         = int(datetime.now(timezone.utc).timestamp())
    avatar_url = member.display_avatar.with_size(256).url

    # ── Welcome message ───────────────────────────────────────────────────────
    wch = guild.get_channel(d.get("welcome_channel") or 0)
    if wch:
        def _ref(ch_id) -> str:
            return f"<#{ch_id}>" if ch_id else "`Not Set`"

        await _v2_send(wch, [  # type: ignore
            _container(
                _text(f"## Welcome To {guild.name} <:kawaiifu:1512397384540356703>"),
                _separator(),
                _section(
                    f"**Welcome {member.mention}!**\n"
                    f"> Purchase At {_ref(d.get('welcome_purchase'))}\n"
                    f"> Rules In {_ref(d.get('welcome_rules'))}\n"
                    f"> News In {_ref(d.get('welcome_news'))}",
                    avatar_url,
                ),
                _separator(),
                _text(f"-# Member #{guild.member_count}  ·  <t:{ts}:F>"),
            )
        ])
        log.info("Welcome Sent For %s In '%s' (Member #%d)", member, guild.name, guild.member_count)

    # ── Invite tracking ───────────────────────────────────────────────────────
    inv_ch = guild.get_channel(d.get("invites_channel") or 0)
    if not inv_ch:
        await _refresh_invite_cache(guild)
        return

    # Compare cached uses vs current uses to find which invite was used
    old_cache = _invite_cache.get(guild.id, {})
    inviter: discord.Member | None = None
    used_code: str = "Unknown"

    try:
        new_invites = await guild.invites()
        for inv in new_invites:
            old_uses = old_cache.get(inv.code, 0)
            if (inv.uses or 0) > old_uses:
                inviter   = guild.get_member(inv.inviter.id) if inv.inviter else None
                used_code = inv.code
                break
        # Refresh cache after detection
        _invite_cache[guild.id] = {inv.code: (inv.uses or 0) for inv in new_invites}
    except Exception as e:
        log.warning("Invite Track Error: %s", e)
        await _refresh_invite_cache(guild)
        return

    # Update cumulative count in DB
    if inviter:
        total_invited = await _invite_add(guild.id, inviter.id)
    else:
        total_invited = 0

    inviter_text   = inviter.mention if inviter else "`Unknown`"
    inviter_name   = str(inviter) if inviter else "Unknown"
    inviter_avatar = (
        inviter.display_avatar.with_size(256).url if inviter
        else "https://cdn.discordapp.com/embed/avatars/0.png"
    )

    await _v2_send(inv_ch, [  # type: ignore
        _container(
            _text("## 🔗 New Member Invited"),
            _separator(),
            _section(
                f"**{member.mention}** Was Invited By {inviter_text}\n"
                f"> Invite Code: `{used_code}`\n"
                f"> {inviter_text} Has Now Invited **{total_invited}** Member(s) Total",
                inviter_avatar,
            ),
            _separator(),
            _text(f"-# <t:{ts}:F>"),
        )
    ])
    log.info("Invite Track: %s Joined Via %s (Invited By %s — Total: %d)", member, used_code, inviter_name, total_invited)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                            TICKET LOGIC                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

async def _create_ticket(
    interaction: discord.Interaction,
    category_key: str,
    subject: str,
    description: str,
):
    guild: discord.Guild = interaction.guild  # type: ignore
    d = _gdata(guild.id)

    stale = [
        cid for cid, td in d["tickets"].items()
        if td.get("open") and guild.get_channel(cid) is None
    ]
    for cid in stale:
        d["tickets"].pop(cid, None)

    for ch_id, td in d["tickets"].items():
        if td.get("author_id") == interaction.user.id and td.get("open"):
            ch     = guild.get_channel(ch_id)
            ch_ref = ch.mention if ch else f"<#{ch_id}>"
            return await interaction.followup.send(
                f"{t('err_open_ticket')}: {ch_ref}\n{t('err_open_close_first')}",
                ephemeral=True,
            )

    cat_ch = guild.get_channel(d["ticket_category"])
    if cat_ch is None:
        return await interaction.followup.send(t("err_no_category"), ephemeral=True)

    support_role = guild.get_role(d["support_role"]) if d["support_role"] else None
    cat_info     = TICKET_CATEGORIES[category_key]
    ticket_id    = _next_id(guild.id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user:   discord.PermissionOverwrite(
            read_messages=True, send_messages=True,
            attach_files=True, embed_links=True,
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True, send_messages=True,
            manage_channels=True, manage_messages=True,
        ),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, attach_files=True,
        )

    channel: discord.TextChannel = await guild.create_text_channel(
        name=f"ticket-{ticket_id}-{interaction.user.name[:10]}",
        category=cat_ch,  # type: ignore
        overwrites=overwrites,
        topic=f"[{cat_info['label']}] {subject} | {interaction.user}",
    )

    ts = int(datetime.now(timezone.utc).timestamp())
    d["tickets"][channel.id] = {
        "id":           ticket_id,
        "author_id":    interaction.user.id,
        "author_name":  str(interaction.user),
        "category":     cat_info["label"],
        "category_key": category_key,
        "subject":      subject,
        "description":  description,
        "open":         True,
        "claimed_by":   None,
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }

    ping = interaction.user.mention + (f" {support_role.mention}" if support_role else "")
    await channel.send(content=ping)

    await _v2_send(channel, [
        _container(
            _text(f"## Ticket #{ticket_id}  —  {_cat_label(category_key)}"),
            _separator(),
            _text(t("ticket_header")),
            _separator(),
            _section(
                f"**{t('ticket_opened_by')}:** {interaction.user.mention} (`{interaction.user}`)\n"
                f"**{t('ticket_subject')}:** {subject}\n"
                f"**{t('ticket_created')}:** <t:{ts}:F>",
                interaction.user.display_avatar.with_size(256).url,
            ),
            _separator(),
            _text(f"**{t('ticket_issue')}:**\n>>> {description}"),
            _separator(),
            _action_row(
                _button(t("btn_close"), "ticket:close", style=4),
                _button(t("btn_claim"), "ticket:claim", style=3),
            ),
        )
    ])

    await interaction.followup.send(
        f"Ticket Created Successfully: {channel.mention}", ephemeral=True
    )
    await _log_event(guild, "CREATE", channel.id, interaction.user, subject)
    log.info("Ticket #%s Created By %s", ticket_id, interaction.user)


async def _do_close_ticket(interaction: discord.Interaction):
    guild: discord.Guild = interaction.guild  # type: ignore
    d  = _gdata(guild.id)
    td = d["tickets"].get(interaction.channel_id)
    if not td:
        return

    td["open"] = False
    channel: discord.TextChannel = interaction.channel  # type: ignore

    author = guild.get_member(td["author_id"])
    if author:
        await channel.set_permissions(author, send_messages=False)

    ts = int(datetime.now(timezone.utc).timestamp())
    await _v2_send(channel, [
        _container(
            _text(f"## {t('close_header')}"),
            _separator(),
            _text(t("close_body")),
            _separator(),
            _text(f"-# {t('close_closed_by')} {interaction.user.mention}  —  <t:{ts}:F>"),
        )
    ])

    # ── Build transcript ───────────────────────────────────────────────────────
    author = guild.get_member(td["author_id"])
    try:
        buf, fname = await _build_transcript(channel, td, str(interaction.user))

        # ── DM the ticket author — styled like the reference image ───────────
        ticket_num = td.get('id', '????')
        category   = td.get('category', 'N/A')
        subject    = td.get('subject', 'N/A')
        if author:
            try:
                embed = discord.Embed(
                    title=f"🎫 Ticket #{ticket_num} — {category}",
                    description=(
                        f"Your Ticket In **{guild.name}** Has Been Closed.\n"
                        f"Closed By **{interaction.user}**\n\n"
                        f"A Transcript Of The Conversation Is Attached Below."
                    ),
                    color=0x2b2d31,
                )
                embed.add_field(name="Subject", value=subject, inline=False)
                embed.set_footer(text=f"{guild.name}", icon_url=guild.icon.url if guild.icon else None)
                await author.send(embed=embed, file=discord.File(buf, filename=fname))
            except discord.Forbidden:
                log.warning("Could Not DM Transcript To %s (DMs Disabled)", author)

        # ── Send transcript to log channel with a clean embed ────────────────
        log_ch_id = d.get("log_channel")
        if log_ch_id:
            lch = guild.get_channel(log_ch_id)
            if lch:
                buf.seek(0)
                author_mention = author.mention if author else f"<@{td['author_id']}>"
                claimed_by_id  = td.get("claimed_by")
                claimed_txt    = f"<@{claimed_by_id}>" if claimed_by_id else "`Unclaimed`"

                await _v2_send(lch, [  # type: ignore
                    _container(
                        _text(f"## 🎫 Ticket #{ticket_num} Closed"),
                        _separator(),
                        _section(
                            f"**Category:** {category}\n"
                            f"**Subject:** {subject}\n"
                            f"**Opened By:** {author_mention}\n"
                            f"**Claimed By:** {claimed_txt}\n"
                            f"**Closed By:** {interaction.user.mention}",
                            interaction.user.display_avatar.with_size(256).url,
                        ),
                        _separator(),
                        _text(
                            f"📄 Transcript: `{fname}`\n"
                            f"-# Closed <t:{ts}:F>"
                        ),
                    )
                ])
                # Send the actual .txt file separately (V2 containers don't support file attachments)
                buf.seek(0)
                await lch.send(
                    content=f"📄 `transcript-{ticket_num}.txt`",
                    file=discord.File(buf, filename=fname),
                )

    except Exception as e:
        log.error("Transcript Error: %s", e)

    # ── Log to DB ──────────────────────────────────────────────────────────────
    await _db_log_ticket_close(guild.id, td, interaction.user.id)

    await asyncio.sleep(10)
    subject = td.get("subject", "")
    await channel.delete(reason=f"Ticket Closed By {interaction.user}")
    d["tickets"].pop(interaction.channel_id, None)
    asyncio.get_event_loop().create_task(_db_save_guild(guild.id))
    await _log_event(guild, "CLOSE", interaction.channel_id, interaction.user, subject)


async def _claim_ticket(interaction: discord.Interaction):
    d  = _gdata(interaction.guild_id)
    td = d["tickets"].get(interaction.channel_id)

    if not td:
        return await interaction.response.send_message("Ticket Data Not Found.", ephemeral=True)

    support_role_id = d.get("support_role")
    support_role    = interaction.guild.get_role(support_role_id) if support_role_id else None
    if support_role and support_role not in interaction.user.roles:  # type: ignore
        return await interaction.response.send_message(t("claim_staff_only"), ephemeral=True)

    if td.get("claimed_by"):
        claimer = interaction.guild.get_member(td["claimed_by"])
        return await interaction.response.send_message(
            f"{t('claim_already')} {claimer.mention if claimer else 'A Staff Member'}.",
            ephemeral=True,
        )

    td["claimed_by"] = interaction.user.id
    ts = int(datetime.now(timezone.utc).timestamp())

    await _v2_send(interaction.channel, [  # type: ignore
        _container(
            _text("## Ticket Claimed"),
            _separator(),
            _text(
                f"**{interaction.user.mention}** {t('claim_success_ch')}  —  <t:{ts}:R>\n"
                f"{t('claim_success_note')}"
            ),
        )
    ])
    await interaction.response.send_message(t("claim_ack"), ephemeral=True)


async def _build_transcript(
    channel: discord.TextChannel, td: dict, exported_by: str
) -> tuple[io.BytesIO, str]:
    lines = [
        "=" * 56,
        f"  Ticket Transcript  —  #{td.get('id', '????')}",
        "=" * 56,
        f"  Category   : {td.get('category',    'N/A')}",
        f"  Subject    : {td.get('subject',     'N/A')}",
        f"  Opened By  : {td.get('author_name', 'N/A')}",
        f"  Exported By: {exported_by}",
        f"  Timestamp  : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 56 + "\n",
    ]
    async for msg in channel.history(limit=500, oldest_first=True):
        ts_str = msg.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts_str}] {msg.author}: {msg.content or '[No Text Content]'}")
        for att in msg.attachments:
            lines.append(f"[{ts_str}] {msg.author}: [Attachment] {att.url}")
    buf   = io.BytesIO("\n".join(lines).encode("utf-8"))
    fname = f"ticket-{td.get('id', '0000')}-transcript.txt"
    return buf, fname


async def _log_event(
    guild: discord.Guild,
    event: str,
    channel_id: int,
    actor: discord.Member,
    subject: str,
):
    d   = _gdata(guild.id)
    lch = guild.get_channel(d["log_channel"]) if d.get("log_channel") else None
    if not lch:
        return

    ts    = int(datetime.now(timezone.utc).timestamp())
    tags  = {"CREATE": "Ticket Created", "CLOSE": "Ticket Closed", "CLAIM": "Ticket Claimed"}
    label = tags.get(event, event.title())

    await _v2_send(lch, [  # type: ignore
        _container(
            _text(f"## {label}"),
            _separator(),
            _section(
                f"**Channel:** <#{channel_id}>\n"
                f"**Actor:** {actor.mention}  (`{actor}` — ID: `{actor.id}`)\n"
                f"**Subject:** {subject[:100]}",
                actor.display_avatar.with_size(256).url,
            ),
            _separator(),
            _text(f"-# <t:{ts}:F>"),
        )
    ])


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                           /ticket COMMANDS                                  ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  /ticket setup    — Configure ticket system                                 ║
# ║  /ticket panel    — Send ticket panel to channel                            ║
# ║  /ticket add      — Add user to ticket                                      ║
# ║  /ticket remove   — Remove user from ticket                                 ║
# ║  /ticket list     — List all open tickets                                   ║
# ║  /ticket delete   — Force delete a ticket channel                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

ticket_grp = app_commands.Group(
    name="ticket",
    description="Ticket Support System",
    default_permissions=discord.Permissions(0),
)


@ticket_grp.command(name="setup", description="Configure The Ticket System")
@app_commands.describe(
    category="Category Channel To Contain Ticket Channels",
    support_role="Role That Can View And Respond To Tickets",
    log_channel="Channel For Ticket Event Logs (Optional)",
)
@is_owner()
async def ticket_setup(
    interaction:  discord.Interaction,
    category:     discord.CategoryChannel,
    support_role: discord.Role,
    log_channel:  Optional[discord.TextChannel] = None,
):
    d = _gdata(interaction.guild_id)
    d["ticket_category"] = category.id
    d["support_role"]    = support_role.id
    d["log_channel"]     = log_channel.id if log_channel else None
    asyncio.get_event_loop().create_task(_db_save_guild(interaction.guild_id))

    lc = log_channel.mention if log_channel else t("setup_not_set")
    await _v2_respond(interaction, [
        _container(
            _text(f"## {t('setup_ok')}"),
            _separator(),
            _text(
                f"**{t('setup_category')}:** {category.mention}\n"
                f"**{t('setup_role')}:** {support_role.mention}\n"
                f"**{t('setup_log')}:** {lc}"
            ),
        )
    ])


@ticket_grp.command(name="panel", description="Send The Ticket Panel To This Channel")
@is_owner()
async def ticket_panel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    d = _gdata(interaction.guild_id)

    if not d.get("ticket_category"):
        return await interaction.followup.send(t("err_no_setup"), ephemeral=True)

    channel: discord.TextChannel = interaction.channel  # type: ignore

    # Build select options from TICKET_CATEGORIES
    select_options = [
        {
            "label":       v["label"],
            "value":       k,
            "description": v["description"],
        }
        for k, v in TICKET_CATEGORIES.items()
    ]

    await _v2_send(channel, [
        _container(
            _text(
                "## Support\n\n"
                "Choose a ticket type, then fill out the form "
                "(**Enter your issue** — at least **20** characters)."
            ),
            _select(
                custom_id="ticket:category_select",
                placeholder="Choose Ticket Type...",
                options=select_options,
            ),
            _text("-# Limit **1** open ticket per member."),
        )
    ])

    d["panel_channel"] = channel.id
    await interaction.followup.send(t("err_panel_sent"), ephemeral=True)


@ticket_grp.command(name="add", description="Add A User To This Ticket")
@app_commands.describe(user="Member To Add To This Ticket Channel")
@is_owner()
async def ticket_add(interaction: discord.Interaction, user: discord.Member):
    d = _gdata(interaction.guild_id)
    if interaction.channel_id not in d["tickets"]:
        return await interaction.response.send_message(t("err_not_ticket"), ephemeral=True)
    await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)  # type: ignore
    await _v2_respond(interaction, [
        _container(
            _text("## User Added"),
            _separator(),
            _text(f"{user.mention} {t('user_added')}"),
        )
    ])


@ticket_grp.command(name="remove", description="Remove A User From This Ticket")
@app_commands.describe(user="Member To Remove From This Ticket Channel")
@is_owner()
async def ticket_remove(interaction: discord.Interaction, user: discord.Member):
    d = _gdata(interaction.guild_id)
    if interaction.channel_id not in d["tickets"]:
        return await interaction.response.send_message(t("err_not_ticket"), ephemeral=True)
    await interaction.channel.set_permissions(user, overwrite=None)  # type: ignore
    await _v2_respond(interaction, [
        _container(
            _text("## User Removed"),
            _separator(),
            _text(f"{user.mention} {t('user_removed')}"),
        )
    ])


@ticket_grp.command(name="list", description="View All Currently Open Tickets")
@is_owner()
async def ticket_list(interaction: discord.Interaction):
    d      = _gdata(interaction.guild_id)
    open_t = {cid: td for cid, td in d["tickets"].items() if td.get("open")}

    if not open_t:
        return await interaction.response.send_message(t("list_empty"), ephemeral=True)

    rows = []
    for ch_id, td in list(open_t.items())[:20]:
        claimed = f"<@{td['claimed_by']}>" if td.get("claimed_by") else t("list_unclaimed")
        rows.append(f"**#{td['id']}** <#{ch_id}>  —  {td['category']}  —  {claimed}")

    await _v2_respond(interaction, [
        _container(
            _text(f"## {t('list_title')}  ({len(open_t)})"),
            _separator(),
            _text("\n".join(rows)),
        )
    ])


@ticket_grp.command(name="delete", description="Force Delete A Ticket Channel")
@app_commands.describe(channel="The Ticket Channel To Delete")
@is_owner()
async def ticket_delete(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True, thinking=True)
    d  = _gdata(interaction.guild_id)
    td = d["tickets"].get(channel.id)

    if not td:
        return await interaction.followup.send(
            f"{channel.mention} Is Not A Tracked Ticket Channel.", ephemeral=True
        )

    guild: discord.Guild = interaction.guild  # type: ignore
    author = guild.get_member(td["author_id"])
    try:
        buf, fname = await _build_transcript(channel, td, str(interaction.user))
        dm_body = (
            f"**Ticket #{td.get('id', '????')} — {td.get('category', '')}**\n"
            f"Your Ticket In **{guild.name}** Was Deleted By {interaction.user}.\n"
            f"Transcript Attached Below."
        )
        if author:
            await author.send(content=dm_body, file=discord.File(buf, filename=fname))
        log_ch_id = d.get("log_channel")
        if log_ch_id:
            lch = guild.get_channel(log_ch_id)
            if lch:
                buf.seek(0)
                await lch.send(
                    content=(
                        f"Transcript — Ticket `#{td.get('id', '????')}` "
                        f"Deleted By {interaction.user.mention}"
                    ),
                    file=discord.File(buf, filename=fname),
                )
    except discord.Forbidden:
        log.warning("Could Not DM Transcript To %s", author)
    except Exception as e:
        log.error("Transcript DM Error On Delete: %s", e)

    ts = int(datetime.now(timezone.utc).timestamp())
    await _v2_send(channel, [
        _container(
            _text("## Ticket Deleted"),
            _separator(),
            _text("Transcript Has Been Sent To The Ticket Author Via DM."),
            _separator(),
            _text(f"-# Deleted By {interaction.user.mention}  —  <t:{ts}:F>"),
        )
    ])
    await asyncio.sleep(3)
    await channel.delete(reason=f"Ticket Deleted By {interaction.user}")
    d["tickets"].pop(channel.id, None)
    await _log_event(guild, "CLOSE", channel.id, interaction.user, td.get("subject", ""))
    await interaction.followup.send(
        f"Ticket `#{td.get('id', '????')}` Has Been Deleted.", ephemeral=True
    )
    log.info("Ticket #%s Deleted By %s", td.get("id"), interaction.user)


bot.tree.add_command(ticket_grp)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                          /welcome COMMANDS                                  ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  /welcome setup   — Configure welcome message system                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

welcome_grp = app_commands.Group(
    name="welcome",
    description="Welcome Message System",
    default_permissions=discord.Permissions(0),
)


@welcome_grp.command(name="setup", description="Configure The Welcome Message System")
@app_commands.describe(
    channel="Channel To Send Welcome Messages In",
    purchase="Purchase / Shop Channel To Link",
    rules="Rules Channel To Link",
    news="Announcements / News Channel To Link",
)
@is_owner()
async def welcome_setup(
    interaction: discord.Interaction,
    channel:     discord.TextChannel,
    purchase:    Optional[discord.TextChannel] = None,
    rules:       Optional[discord.TextChannel] = None,
    news:        Optional[discord.TextChannel] = None,
):
    d = _gdata(interaction.guild_id)
    d["welcome_channel"]  = channel.id
    d["welcome_purchase"] = purchase.id if purchase else None
    d["welcome_rules"]    = rules.id    if rules    else None
    d["welcome_news"]     = news.id     if news     else None
    asyncio.get_event_loop().create_task(_db_save_guild(interaction.guild_id))

    def _ref(ch: Optional[discord.TextChannel]) -> str:
        return ch.mention if ch else "`Not Set`"

    await _v2_respond(interaction, [
        _container(
            _text("## Welcome System Configured"),
            _separator(),
            _text(
                f"**Welcome Channel:** {channel.mention}\n"
                f"**Purchase Channel:** {_ref(purchase)}\n"
                f"**Rules Channel:** {_ref(rules)}\n"
                f"**News Channel:** {_ref(news)}"
            ),
            _separator(),
            _text("Members Will Now Receive A Welcome Message When They Join."),
        )
    ])
    log.info("Welcome Setup By %s In '%s'", interaction.user, interaction.guild.name)


bot.tree.add_command(welcome_grp)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                          /payment COMMANDS                                  ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  /payment setup        — Configure VietQR + Casso                           ║
# ║  /payment create       — Generate a QR payment request                      ║
# ║  /payment check        — Check payment status by ref                        ║
# ║  /payment confirm      — Manually confirm a payment (owner)                 ║
# ║  /payment cancel       — Cancel a pending payment (owner)                   ║
# ║  /payment list         — List all payments with filter                      ║
# ║  /payment announce_all — Send daily summary to channel                      ║
# ║  /payment info         — Show current payment config                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

payment_grp = app_commands.Group(
    name="payment",
    description="VietQR Payment System",
    default_permissions=discord.Permissions(0),
)


@payment_grp.command(name="setup", description="Configure The VietQR AutoBank Payment System")
@app_commands.describe(
    bank_id="VietQR Bank Code (E.g. MB, VCB, TCB, VPB, TPB, ACB)",
    account_no="Bank Account Number",
    account_name="Account Holder Name (Shown On QR)",
    casso_key="Casso API Key For Auto-Confirm (Get From casso.vn)",
    log_channel="Channel To Log Confirmed Payments",
    confirm_role="Role To Ping On Payment Confirmed (Optional)",
    timeout="Payment Expiry In Minutes (Default: 10)",
)
@is_owner()
async def payment_setup(
    interaction:   discord.Interaction,
    bank_id:       str,
    account_no:    str,
    account_name:  str,
    casso_key:     str,
    log_channel:   discord.TextChannel,
    confirm_role:  Optional[discord.Role] = None,
    timeout:       int = 10,
):
    d             = _gdata(interaction.guild_id)
    bank_id_upper = bank_id.strip().upper()

    d["pay_bank_id"]      = bank_id_upper
    d["pay_account_no"]   = account_no.strip()
    d["pay_account_name"] = account_name.strip()
    d["pay_casso_key"]    = casso_key.strip()
    d["pay_log_channel"]  = log_channel.id
    d["pay_confirm_role"] = confirm_role.id if confirm_role else None
    d["pay_timeout"]      = max(1, timeout) * 60
    asyncio.get_event_loop().create_task(_db_save_guild(interaction.guild_id))

    await _v2_respond(interaction, [
        _container(
            _text("## ✅ Payment System Configured"),
            _separator(),
            _text(
                f"**Bank:** `{bank_id_upper}`\n"
                f"**Account No:** `{account_no}`\n"
                f"**Account Name:** `{account_name}`\n"
                f"**Log Channel:** {log_channel.mention}\n"
                f"**Ping Role:** {confirm_role.mention if confirm_role else '`None`'}\n"
                f"**Casso API Key:** `{'*' * min(len(casso_key), 8)}...` *(Hidden)*\n"
                f"**Payment Timeout:** `{timeout} Minutes`\n\n"
                "Auto-Confirm: Bot Will Poll Casso Every 15s And Confirm Matching Payments.\n"
                "Run `/payment create` To Generate A QR Code."
            ),
        )
    ])
    log.info(
        "Payment Setup By %s In '%s' — Bank: %s  Account: %s",
        interaction.user, interaction.guild.name, bank_id_upper, account_no,
    )


@payment_grp.command(name="create", description="Generate A VietQR Payment QR Code")
@app_commands.describe(
    amount="Amount In VND (E.g. 50000)",
    user="Who Is Paying (Optional, Defaults To You)",
)
async def payment_create(
    interaction: discord.Interaction,
    amount:      int,
    user:        Optional[discord.Member] = None,
):
    await interaction.response.defer(ephemeral=False, thinking=True)
    d = _gdata(interaction.guild_id)

    if not d.get("pay_bank_id") or not d.get("pay_account_no"):
        return await interaction.followup.send(
            "Payment System Not Configured. Ask An Admin To Run `/payment setup` First.",
            ephemeral=True,
        )

    if amount < 1000:
        return await interaction.followup.send(
            "Minimum Amount Is `1,000 VND`.", ephemeral=True
        )

    payer      = user or interaction.user
    bank_id    = d["pay_bank_id"]
    account_no = d["pay_account_no"]
    acc_name   = d["pay_account_name"]
    ref        = _gen_ref(interaction.guild_id, payer.id)
    while ref in d["payments"]:
        ref = _gen_ref(interaction.guild_id, payer.id)

    qr_url = _vietqr_url(bank_id, account_no, acc_name, amount, ref)
    ts     = int(time.time())
    expire = ts + d.get("pay_timeout", 600)

    channel: discord.TextChannel = interaction.channel  # type: ignore
    msg_data = await _v2_send(channel, [
        _container(
            _text("## 🏦 Payment Request"),
            _separator(),
            _section(
                f"**Payer:** {payer.mention}\n"
                f"**Amount:** `{amount:,} VND`\n"
                f"**Bank:** `{bank_id}` — `{account_no}`\n"
                f"**Account Name:** `{acc_name}`\n"
                f"**Transfer Description:** `{ref}`\n"
                f"⏰ Expires <t:{expire}:R>",
                qr_url,
            ),
            _separator(),
            _text(
                "**Instructions:**\n"
                "> 1️⃣  Open Your Banking App\n"
                "> 2️⃣  Scan The QR Code On The Right\n"
                f"> 3️⃣  Enter Exactly This Transfer Description: **`{ref}`** — Required!\n"
                "> 4️⃣  Bot Will Auto-Confirm Within A Few Seconds\n\n"
                "-# Do Not Change The Transfer Description Or Payment Will Not Be Detected."
            ),
            _separator(),
            _action_row(_button("❌ Cancel Payment", f"payment:cancel:{ref}", style=4)),
        )
    ])

    msg_id = int(msg_data.get("id", 0))
    _payment_create(interaction.guild_id, payer.id, amount, "", channel.id, msg_id, ref=ref)

    try:
        await interaction.delete_original_response()
    except Exception:
        pass

    log.info(
        "Payment %s Created — %s VND — Payer: %s — Bank: %s %s",
        ref, amount, payer, bank_id, account_no,
    )


@payment_grp.command(name="check", description="Manually Check A Payment Status By Reference Code")
@app_commands.describe(ref="Payment Reference Code (E.g. PAYAB1234)")
async def payment_check(interaction: discord.Interaction, ref: str):
    d = _gdata(interaction.guild_id)
    p = d["payments"].get(ref.upper())
    if not p:
        return await interaction.response.send_message(
            f"Payment `{ref}` Not Found.", ephemeral=True
        )

    status_icon = {
        "pending":   "⏳",
        "confirmed": "✅",
        "expired":   "⏰",
        "cancelled": "❌",
    }.get(p["status"], "❓")
    payer = interaction.guild.get_member(p["user_id"])
    ts    = int(p["created_at"])

    await _v2_respond(interaction, [
        _container(
            _text(f"## {status_icon} Payment Status"),
            _separator(),
            _text(
                f"**Reference:** `{ref}`\n"
                f"**Status:** {status_icon} {p['status'].upper()}\n"
                f"**Amount:** `{p['amount']:,} VND`\n"
                f"**Payer:** {payer.mention if payer else 'ID: ' + str(p['user_id'])}\n"
                f"**Created:** <t:{ts}:F>\n"
                + (f"**TX ID:** `{p['confirmed_by_tx']}`" if p.get("confirmed_by_tx") else "")
            ),
        )
    ])


@payment_grp.command(name="confirm", description="Manually Confirm A Payment (Owner Only)")
@app_commands.describe(ref="Payment Reference Code To Confirm")
@is_owner()
async def payment_confirm(interaction: discord.Interaction, ref: str):
    d          = _gdata(interaction.guild_id)
    ref_up     = ref.strip().upper()
    payments   = d["payments"]

    matched_key = next((k for k in payments if k.upper() == ref_up), None)
    if not matched_key:
        pending_refs = [k for k, v in payments.items() if v["status"] == "pending"]
        hint = (
            "\n\n**Active Payments:** " + ", ".join(f"`{r}`" for r in pending_refs[:10])
            if pending_refs else ""
        )
        return await interaction.response.send_message(
            f"Payment `{ref_up}` Not Found.{hint}", ephemeral=True
        )

    p = payments[matched_key]
    if p["status"] != "pending":
        return await interaction.response.send_message(
            f"Payment `{matched_key}` Is Already **{p['status'].upper()}**.", ephemeral=True
        )

    _payment_confirm(interaction.guild_id, matched_key, "MANUAL")
    await _notify_payment_confirmed(interaction.guild_id, matched_key)
    await interaction.response.send_message(
        f"Payment `{matched_key}` Confirmed Manually. ✅", ephemeral=True
    )


@payment_grp.command(name="cancel", description="Cancel A Pending Payment (Owner Only)")
@app_commands.describe(ref="Payment Reference Code To Cancel")
@is_owner()
async def payment_cancel(interaction: discord.Interaction, ref: str):
    d = _gdata(interaction.guild_id)
    p = d["payments"].get(ref.upper())
    if not p:
        return await interaction.response.send_message(
            f"Payment `{ref}` Not Found.", ephemeral=True
        )
    if p["status"] != "pending":
        return await interaction.response.send_message(
            f"Payment Is Already **{p['status'].upper()}**.", ephemeral=True
        )
    _payment_expire(interaction.guild_id, ref.upper())
    await _notify_payment_expired(interaction.guild_id, ref.upper())
    await interaction.response.send_message(f"Payment `{ref}` Cancelled.", ephemeral=True)


@payment_grp.command(name="list", description="List All Payments (Owner Only)")
@app_commands.describe(status="Filter By Status")
@app_commands.choices(status=[
    app_commands.Choice(name="All",       value="all"),
    app_commands.Choice(name="Pending",   value="pending"),
    app_commands.Choice(name="Confirmed", value="confirmed"),
    app_commands.Choice(name="Expired",   value="expired"),
    app_commands.Choice(name="Cancelled", value="cancelled"),
])
@is_owner()
async def payment_list(interaction: discord.Interaction, status: str = "all"):
    d        = _gdata(interaction.guild_id)
    payments = d["payments"]

    filtered = {
        ref: p for ref, p in payments.items()
        if status == "all" or p["status"] == status
    }

    if not filtered:
        return await interaction.response.send_message(
            f"No Payments Found With Status: `{status}`.", ephemeral=True
        )

    icon_map = {"pending": "⏳", "confirmed": "✅", "expired": "⏰", "cancelled": "❌"}
    rows     = []
    for ref, p in list(filtered.items())[-20:]:
        icon   = icon_map.get(p["status"], "❓")
        payer  = interaction.guild.get_member(p["user_id"])
        p_name = payer.display_name if payer else f"ID:{p['user_id']}"
        rows.append(f"{icon} `{ref}` — `{p['amount']:,}₫` — {p_name} — **{p['status']}**")

    total     = len(filtered)
    confirmed = sum(1 for p in filtered.values() if p["status"] == "confirmed")
    total_vnd = sum(p["amount"] for p in filtered.values() if p["status"] == "confirmed")

    await _v2_respond(interaction, [
        _container(
            _text(f"## 💳 Payment List — `{status.upper()}`"),
            _separator(),
            _text(
                f"**Total:** {total}  •  **Confirmed:** {confirmed}  •  **Revenue:** `{total_vnd:,} VND`\n\n"
                + "\n".join(rows)
            ),
        )
    ])


@payment_grp.command(
    name="announce_all",
    description="Manually Send Daily Payment Summary To A Channel",
)
@app_commands.describe(
    channel="Channel To Send The Summary (Also Saves As Auto-Announce Channel)",
    note="Extra Note To Include (Optional)",
)
@is_owner()
async def payment_announce_all(
    interaction: discord.Interaction,
    channel:     discord.TextChannel,
    note:        Optional[str] = None,
):
    await interaction.response.defer(ephemeral=True, thinking=True)
    d = _gdata(interaction.guild_id)
    d["pay_announce_channel"] = channel.id
    asyncio.get_event_loop().create_task(_db_save_guild(interaction.guild_id))

    await _send_daily_summary(
        interaction.guild_id, channel.id, note=note, actor=str(interaction.user)
    )
    await interaction.followup.send(
        f"Summary Sent To {channel.mention}.\n"
        "-# This Channel Is Now Set As The Daily 00:00 Auto-Announce Channel.",
        ephemeral=True,
    )


@payment_grp.command(name="info", description="Show Current Payment System Configuration")
@is_owner()
async def payment_info(interaction: discord.Interaction):
    d = _gdata(interaction.guild_id)
    if not d.get("pay_bank_id"):
        return await interaction.response.send_message(
            "Payment System Not Configured. Run `/payment setup` First.", ephemeral=True
        )

    log_ch    = interaction.guild.get_channel(d.get("pay_log_channel") or 0)
    conf_role = interaction.guild.get_role(d.get("pay_confirm_role") or 0)
    timeout_m = d.get("pay_timeout", 600) // 60
    pending   = sum(1 for p in d["payments"].values() if p["status"] == "pending")
    confirmed = sum(1 for p in d["payments"].values() if p["status"] == "confirmed")
    revenue   = sum(p["amount"] for p in d["payments"].values() if p["status"] == "confirmed")

    await _v2_respond(interaction, [
        _container(
            _text("## 🏦 Payment System Info"),
            _separator(),
            _text(
                f"**Bank:** `{d['pay_bank_id']}`\n"
                f"**Account No:** `{d['pay_account_no']}`\n"
                f"**Account Name:** `{d['pay_account_name']}`\n"
                f"**Log Channel:** {log_ch.mention if log_ch else '`Not Set`'}\n"
                f"**Ping Role:** {conf_role.mention if conf_role else '`None`'}\n"
                f"**Timeout:** `{timeout_m} Minutes`\n"
                f"**Casso Key:** `{'Configured ✅' if d.get('pay_casso_key') else 'Not Set ❌'}`"
            ),
            _separator(),
            _text(
                f"**Stats:**\n"
                f"> Pending: `{pending}`\n"
                f"> Confirmed: `{confirmed}`\n"
                f"> Total Revenue: `{revenue:,} VND`"
            ),
        )
    ])


bot.tree.add_command(payment_grp)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               COMPONENT INTERACTION — PAYMENT CANCEL BUTTON                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = (interaction.data or {}).get("custom_id", "")
    if not custom_id.startswith("payment:cancel:"):
        return

    ref      = custom_id[len("payment:cancel:"):].upper()
    guild_id = interaction.guild_id
    if not guild_id:
        return await interaction.response.send_message("Guild Not Found.", ephemeral=True)

    p = _payment_get(guild_id, ref)
    if not p:
        return await interaction.response.send_message(
            f"Payment `{ref}` Not Found.", ephemeral=True
        )
    if p["status"] != "pending":
        return await interaction.response.send_message(
            f"Payment Is Already **{p['status'].upper()}**.", ephemeral=True
        )
    if p["user_id"] != interaction.user.id and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(
            "Only The Payment Owner Can Cancel This.", ephemeral=True
        )

    _payment_expire(guild_id, ref)
    await interaction.response.defer()

    await _v2_edit_msg(p["channel_id"], p["message_id"], [
        _container(
            _text("## ❌ Payment Cancelled"),
            _separator(),
            _text(
                f"**Reference:** `{ref}`\n"
                f"**Amount:** `{p['amount']:,} VND`\n"
                f"**Status:** ❌ Cancelled\n"
                f"-# Cancelled By {interaction.user.mention}  —  This Message Will Be Deleted In 5 Seconds."
            ),
        )
    ])
    await asyncio.sleep(5)
    try:
        url     = f"https://discord.com/api/v10/channels/{p['channel_id']}/messages/{p['message_id']}"
        headers = {"Authorization": f"Bot {TOKEN}"}
        async with aiohttp.ClientSession() as s:
            async with s.delete(url, headers=headers) as r:
                if r.status not in (200, 204):
                    log.warning("Could Not Delete Cancelled Payment Message: %s", r.status)
    except Exception as e:
        log.warning("Could Not Delete Cancelled Payment Message: %s", e)

    log.info("Payment %s Cancelled By %s", ref, interaction.user)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                            ERROR HANDLER                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "You Do Not Have Permission To Use This Command."
    elif isinstance(error, app_commands.CheckFailure):
        msg = "Access Denied. You Are Not Authorized To Use This Command."
    else:
        msg = "An Error Occurred. Please Try Again."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                          PREFIX COMMANDS                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.command(name="sync")
async def cmd_sync(ctx: commands.Context):
    if ctx.author.id != OWNER_ID:
        return await ctx.reply("Access Denied. Only The Bot Owner Can Use This Command.")
    msg    = await ctx.reply("Syncing Commands...")
    synced = await bot.tree.sync()
    await msg.edit(content=f"Synced **{len(synced)}** Slash Commands Successfully.")
    log.info("!sync Called By %s — %d Commands Synced", ctx.author, len(synced))


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                            SLASH COMMANDS                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.tree.command(name="ping", description="Check Bot Latency")
async def slash_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    ts = int(datetime.now(timezone.utc).timestamp())
    await _v2_respond(interaction, [
        _container(
            _text("## 🏓 Pong!"),
            _separator(),
            _text(
                f"**Latency:** `{latency_ms}ms`\n"
                f"-# <t:{ts}:F>"
            ),
        )
    ], ephemeral=False)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        EVENT — MEMBER LEAVE (on_member_remove)              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    d     = _gdata(guild.id)

    lch = guild.get_channel(d.get("leave_channel") or 0)
    if not lch:
        return

    ts         = int(datetime.now(timezone.utc).timestamp())
    avatar_url = member.display_avatar.with_size(256).url
    joined_ts  = int(member.joined_at.timestamp()) if member.joined_at else ts

    await _v2_send(lch, [  # type: ignore
        _container(
            _text(f"## 🚪 Goodbye From **{guild.name}**!"),
            _separator(),
            _section(
                f"**{member.mention} Has Left The Server.**\n"
                f"> Joined: <t:{joined_ts}:R>\n"
                f"> We Now Have `{guild.member_count}` Members.",
                avatar_url,
            ),
            _separator(),
            _text(f"-# <t:{ts}:F>"),
        )
    ])
    log.info("Leave Message Sent For %s In '%s'", member, guild.name)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                       /leave setup COMMAND                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

leave_grp = app_commands.Group(
    name="leave",
    description="Leave Message System",
    default_permissions=discord.Permissions(0),
)


@leave_grp.command(name="setup", description="Configure The Leave Message System")
@app_commands.describe(channel="Channel To Send Leave Messages In")
@is_owner()
async def leave_setup(
    interaction: discord.Interaction,
    channel:     discord.TextChannel,
):
    d = _gdata(interaction.guild_id)
    d["leave_channel"] = channel.id
    asyncio.get_event_loop().create_task(_db_save_guild(interaction.guild_id))

    await _v2_respond(interaction, [
        _container(
            _text("## Leave System Configured"),
            _separator(),
            _text(
                f"**Leave Channel:** {channel.mention}\n\n"
                "Members Will Now Receive A Goodbye Message When They Leave."
            ),
        )
    ])
    log.info("Leave Setup By %s In '%s'", interaction.user, interaction.guild.name)


bot.tree.add_command(leave_grp)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                       /invites COMMANDS                                     ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  /invites setup   — Configure invite tracking channel                       ║
# ║  /invites check   — Check how many people a user has invited                ║
# ║  /invites top     — Show invite leaderboard                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

invites_grp = app_commands.Group(
    name="invites",
    description="Invite Tracking System",
    default_permissions=discord.Permissions(0),
)


@invites_grp.command(name="setup", description="Configure The Invite Tracking Channel")
@app_commands.describe(channel="Channel To Send Invite Notifications In")
@is_owner()
async def invites_setup(
    interaction: discord.Interaction,
    channel:     discord.TextChannel,
):
    d = _gdata(interaction.guild_id)
    d["invites_channel"] = channel.id
    asyncio.get_event_loop().create_task(_db_save_guild(interaction.guild_id))

    # Pre-cache current invites
    await _refresh_invite_cache(interaction.guild)

    await _v2_respond(interaction, [
        _container(
            _text("## 🔗 Invite Tracking Configured"),
            _separator(),
            _text(
                f"**Invites Channel:** {channel.mention}\n\n"
                "When A Member Joins, The Bot Will Detect Who Invited Them\n"
                "And Track Their Cumulative Invite Count In The Database."
            ),
        )
    ])
    log.info("Invites Setup By %s In '%s'", interaction.user, interaction.guild.name)


@invites_grp.command(name="check", description="Check How Many People A User Has Invited")
@app_commands.describe(user="Member To Check (Defaults To Yourself)")
async def invites_check(
    interaction: discord.Interaction,
    user:        Optional[discord.Member] = None,
):
    target = user or interaction.user
    count  = await _invite_get(interaction.guild_id, target.id)
    ts     = int(datetime.now(timezone.utc).timestamp())

    await _v2_respond(interaction, [
        _container(
            _text("## 🔗 Invite Stats"),
            _separator(),
            _section(
                f"**{target.mention}** Has Invited **{count}** Member(s)\n"
                f"-# Tracked Since Bot Joined / Invite Tracking Was Enabled",
                target.display_avatar.with_size(256).url,
            ),
            _separator(),
            _text(f"-# <t:{ts}:F>"),
        )
    ], ephemeral=False)


@invites_grp.command(name="top", description="Show The Invite Leaderboard")
async def invites_top(interaction: discord.Interaction):
    board = await _invite_leaderboard(interaction.guild_id, limit=10)
    ts    = int(datetime.now(timezone.utc).timestamp())

    if not board:
        return await _v2_respond(interaction, [
            _container(
                _text("## 🔗 Invite Leaderboard"),
                _separator(),
                _text("No Invite Data Found Yet. Data Is Collected When Members Join."),
            )
        ])

    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    rows   = []
    for i, (uid, cnt) in enumerate(board):
        m      = interaction.guild.get_member(uid)
        name   = m.display_name if m else f"<@{uid}>"
        mention= m.mention       if m else f"<@{uid}>"
        rows.append(f"{medals[i]} **#{i+1}** {mention} — **{cnt}** Invite(s)")

    await _v2_respond(interaction, [
        _container(
            _text("## 🔗 Invite Leaderboard"),
            _separator(),
            _text("\n".join(rows)),
            _separator(),
            _text(f"-# <t:{ts}:F>"),
        )
    ], ephemeral=False)


bot.tree.add_command(invites_grp)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                             ENTRY POINT                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    log.info("Starting Bot  |  Owner ID: %d", OWNER_ID)
    bot.run(TOKEN, log_handler=None)
