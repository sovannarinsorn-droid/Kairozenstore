"""
╔══════════════════════════════════════════════════════════════╗
║     Kairozen SMM Bot — カイロゼン SMM  [v5]                 ║
║     SMM Panel · ដាក់លុយ CamRapidPay KHQR                   ║
║     Panel Admin · បន្ថែម/កាត់ Balance                       ║
║     Compatible: Python 3.10+ · Termux / Render / VPS       ║
║     v5: Order+Deposit notify → Channel · User ID only      ║
╚══════════════════════════════════════════════════════════════╝
ដំឡើង:
  pip install pyTelegramBotAPI requests flask qrcode pillow --break-system-packages
"""

import json, logging, time, re, threading, io, os, sys, subprocess, datetime
import requests as http_req
from dotenv import load_dotenv
load_dotenv()
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from flask import Flask, request as flask_request, jsonify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── Auto-install deps ───
def _ensure_deps():
    pkgs = {"PIL": "pillow", "qrcode": "qrcode"}
    for mod, pkg in pkgs.items():
        try: __import__(mod)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg,
                            "--break-system-packages", "-q"], check=False)
_ensure_deps()

import qrcode
from PIL import Image

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  CONFIG  — ដូរតម្លៃទាំងនេះ
# ═══════════════════════════════════════════════════════════
BOT_TOKEN          = os.getenv("BOT_TOKEN", "8792366989:AAEjk24yuW1_I5XAiqrl42X4fflzA0R4Zu0")           # Telegram Bot Token
ADMIN_ID           = int(os.getenv("ADMIN_ID", "8266854899"))       # Telegram ID របស់ Admin

# ── CamRapidPay — Create KHQR + Check transaction ──
CAMRAPID_API_KEY   = os.getenv("CAMRAPID_API_KEY", "6cc5b3ab09f7940752924a877fdba323de6a08a83b01eb3a3b353e4f8a505659")     # CamRapidPay API Key
CAMRAPID_CREATE    = "https://pay.camrapidpay.com/api/v1/khqr/create-payments"
CAMRAPID_CHECK     = "https://pay.camrapidpay.com/check-transaction-api"
WEBHOOK_URL        = os.getenv("WEBHOOK_URL", "")          # ដាក់ URL webhook (optional)

DEPOSIT_EXPIRE_SEC = 300   # 5 minutes (CamRapidPay expire 5 min)
POLL_INTERVAL      = 8

# Flask Control Server
CONTROL_KEY        = os.getenv("CONTROL_KEY", "change_this_secret")

# ═══════════════════════════════════════════════════════════
#  FILES
# ═══════════════════════════════════════════════════════════
WALLETS_FILE    = "smm_wallets.json"
USERS_FILE      = "smm_users.json"
LANG_FILE       = "smm_lang.json"
PROMO_FILE      = "smm_promos.json"
SETTINGS_FILE   = "smm_settings.json"
NOTIFY_FILE     = "smm_notify.json"

SMM_API_FILE    = "smm_api.json"
SMM_SVC_FILE    = "smm_services.json"
SMM_ORD_FILE    = "smm_orders.json"
SMM_PROFIT_FILE = "smm_profit.json"
SMM_POLL_FILE   = "smm_poll.json"
SMM_DEP_FILE    = "smm_deposits.json"

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def _save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: logger.error(f"Save {path}: {e}")

# ─── Load all state ───
wallets      = _load(WALLETS_FILE,   {})
users_db     = _load(USERS_FILE,     {})
user_lang    = _load(LANG_FILE,      {})
promos       = _load(PROMO_FILE,     {})
settings     = _load(SETTINGS_FILE,  {})
notify_cfg   = _load(NOTIFY_FILE,    {"channel_id": "", "enabled": False})

smm_api      = _load(SMM_API_FILE,   {"url": "", "key": ""})
smm_services = _load(SMM_SVC_FILE,   {})
smm_orders   = _load(SMM_ORD_FILE,   {})
smm_profit   = _load(SMM_PROFIT_FILE,{"pct": 20})
smm_poll     = _load(SMM_POLL_FILE,  {"interval": POLL_INTERVAL})
smm_deps     = _load(SMM_DEP_FILE,   {})

# ── Auto-seed TikTok Promote Khmer packages ──
_TIKTOK_PACKAGES = [
    {
        "slug":        "manual_tiktok_promote_p1",
        "label":       "🇰🇭 500-1k ❤️ · 1.8k 👁 View",
        "description": "500-1K Likes ❤️ + 1.8K Views 👁\n⏱ 5-15 នាទី",
        "flat_price":  0.99,
    },
    {
        "slug":        "manual_tiktok_promote_p2",
        "label":       "🇰🇭 1k-2k ❤️ · 3.5k 👁 View",
        "description": "1K-2K Likes ❤️ + 3.5K Views 👁\n⏱ 5-15 នាទី",
        "flat_price":  1.99,
    },
    {
        "slug":        "manual_tiktok_promote_p3",
        "label":       "🇰🇭 2k-3k ❤️ · 10k 👁 View",
        "description": "2K-3K Likes ❤️ + 10K Views 👁\n⏱ 10-20 នាទី",
        "flat_price":  3.25,
    },
    {
        "slug":        "manual_tiktok_promote_p4",
        "label":       "🇰🇭 3k-5k ❤️ · 20k 👁 View",
        "description": "3K-5K Likes ❤️ + 20K Views 👁\n⏱ 15-30 នាទី",
        "flat_price":  5.49,
    },
    {
        "slug":        "manual_tiktok_promote_p5",
        "label":       "🇰🇭 500 ❤️ · 1k 👁 · 100 👤 Follow",
        "description": "500 Likes ❤️ + 1K Views 👁 + 100 Followers 👤\n⏱ 5-15 នាទី",
        "flat_price":  1.99,
    },
]
_changed = False
for _pkg in _TIKTOK_PACKAGES:
    _slug = _pkg["slug"]
    if _slug not in smm_services:
        smm_services[_slug] = {
            "api_id":      None,
            "manual":      True,
            "cost_rate":   0,
            "min":         1,
            "max":         1,
            "label":       _pkg["label"],
            "category":    "🇰🇭 TikTok Khmer",
            "flat_price":  _pkg["flat_price"],
            "preset_qtys": [1],
            "description": _pkg["description"],
        }
        _changed = True
if _changed:
    _save(SMM_SVC_FILE, smm_services)

# Remove old single-package slug if exists
if "manual_tiktok_promote_khmer" in smm_services:
    smm_services.pop("manual_tiktok_promote_khmer")
    _save(SMM_SVC_FILE, smm_services)




waiting      = {}
lang_cooldown= {}

# ═══════════════════════════════════════════════════════════
#  BOT + HTTP
# ═══════════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

def _make_session():
    s = http_req.Session()
    r = Retry(total=3, backoff_factor=2, status_forcelist=[500,502,503,504])
    a = HTTPAdapter(max_retries=r)
    s.mount("http://", a); s.mount("https://", a)
    return s
http = _make_session()

# ═══════════════════════════════════════════════════════════
#  LANGUAGE
# ═══════════════════════════════════════════════════════════
STRINGS = {
    "kh": {
        "welcome": (
            "សួស្តី បង/ប្អូន! 👋\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "ស្វាគមន៍មក <b>Kairozen SMM</b> 🇰🇭\n"
            "ខ្ញុំជួយបង្កើន Views · Likes · Followers\n"
            "សម្រាប់ TikTok និង Social Media ផ្សេងៗ!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💳 លុយបច្ចុប្បន្ន: <b>${:.2f}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 ចុចជ្រើសពី Menu ខាងក្រោមបាន!"
        ),
        "select_lang":   "🌐 ជ្រើសភាសាដែលអ្នកចូលចិត្ត:",
        "lang_set":      "✅ ផ្លាស់ប្តូរភាសារួចហើយ!",
        "menu":          "🏠 ត្រឡប់ Menu",
        "banned":        "🚫 គណនីរបស់អ្នកត្រូវបាន ban! សូមទំនាក់ Admin ប្រសិនបើមានបញ្ហា។",
        "cancel_ok":     "🏠 ត្រឡប់ Menu ហើយ!",
        "no_service":    "❌ មិនទាន់មាន Service ទេ នឹងដាក់ឆាប់ៗ!",
        "choose_platform": "ជ្រើស Platform ដែលចង់ boost:",
        "choose_qty":    "ជ្រើស Package:",
        "send_link":     "ផ្ញើ Link វីដេអូរបស់អ្នកមក:",
        "low_balance":   "❌ លុយមិនគ្រប់! សូម Top Up ជាមុន 💸",
        "order_done":    "✅ Order បានទទួលហើយ! នឹងដំណើរការឆាប់ៗ 🙏",
        "deposit_ok":    "✅ ដាក់លុយបានជោគជ័យ! អរគុណ 🙏",
        "qr_expired":    "⏰ QR ផុតហើយ! សូម Top Up ម្តងទៀតនៅ",
        "qr_error":      "⚠️ មានបញ្ហា Generate QR! សូមទំនាក់ Admin 🙏",
        "track_prompt":  "🔍 វាយ Order ID របស់អ្នក (ឧ: KZ12345):",
        "order_notfound":"❌ រកមិនឃើញ Order នេះទេ! ត្រូវប្រាកដ ID ត្រឹមត្រូវ",
        "no_orders":     "❌ មិនទាន់មាន Order ណាមួយទេ!",
        "how_to_use": (
            "💡 <b>របៀបប្រើ Kairozen SMM</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ ដាក់លុយ → ចុច <b>💸 បញ្ចូលលុយ</b> → Scan QR\n"
            "2️⃣ Order → ចុច <b>🛒 បញ្ជាទិញ</b> → ជ្រើស Package → ផ្ញើ Link\n"
            "3️⃣ តាមដាន → ចុច <b>📋 ប្រវត្តិ</b> → មើលស្ថានភាព Order\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "❓ មានសំណួរ ទំនាក់ Admin បានគ្រប់ពេល! 😊"
        ),
        "support_msg": (
            "💬 <b>ទំនាក់ Admin Kairozen SMM</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📞 Admin: @smos_sne1\n"
            "⏱ ទំនាក់បានគ្រប់ពេល!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 មានបញ្ហា Order ឬ Payment\n"
            "ផ្ញើ Order ID មកផ្ទាល់ Admin 🙏"
        ),
        "fallback": "😊 ប្រើប៊ូតុង Menu ខាងក្រោមបាន!",
    },
    "en": {
        "welcome": (
            "Hey! 👋 Welcome to <b>Kairozen SMM</b> 🇰🇭\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "We help grow your TikTok & Social Media\n"
            "Views · Likes · Followers — fast & real!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💳 Your Balance: <b>${:.2f}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 Pick from the menu below!"
        ),
        "select_lang":   "🌐 Choose your language:",
        "lang_set":      "✅ Language updated!",
        "menu":          "🏠 Back to Menu",
        "banned":        "🚫 Your account has been banned. Contact Admin if you think this is a mistake.",
        "cancel_ok":     "🏠 Back to Menu!",
        "no_service":    "❌ No services yet — check back soon!",
        "choose_platform": "Pick a platform to boost:",
        "choose_qty":    "Choose a package:",
        "send_link":     "Send your video link:",
        "low_balance":   "❌ Not enough balance! Please Top Up first 💸",
        "order_done":    "✅ Order received! We'll process it shortly 🙏",
        "deposit_ok":    "✅ Deposit successful! Thank you 🙏",
        "qr_expired":    "⏰ QR expired! Please Top Up again",
        "qr_error":      "⚠️ QR error! Please contact Admin 🙏",
        "track_prompt":  "🔍 Send your Order ID (e.g. KZ12345):",
        "order_notfound":"❌ Order not found! Make sure the ID is correct.",
        "no_orders":     "❌ No orders yet!",
        "how_to_use": (
            "💡 <b>How to use Kairozen SMM</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ Top Up → Tap <b>💸 Top Up</b> → Scan QR\n"
            "2️⃣ Order → Tap <b>🛒 Order</b> → Pick package → Send link\n"
            "3️⃣ Track → Tap <b>📋 History</b> → Check status\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "❓ Questions? Contact Admin anytime! 😊"
        ),
        "support_msg": (
            "💬 <b>Contact Kairozen SMM Admin</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📞 Admin: @smos_sne1\n"
            "⏱ Available anytime!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 For order or payment issues,\n"
            "send your Order ID directly to Admin 🙏"
        ),
        "fallback": "😊 Use the menu buttons below!",
    },
}

def get_lang(uid): return user_lang.get(str(uid), "kh")

def t(uid, key, *args):
    lang = get_lang(uid)
    s = STRINGS.get(lang, STRINGS["kh"]).get(key) or STRINGS["kh"].get(key, key)
    if args:
        try: return s.format(*args)
        except: return s
    return s

def lang_select_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇰🇭 ខ្មែរ", callback_data="setlang:kh"),
         InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en")]
    ])

# ═══════════════════════════════════════════════════════════
#  WALLET HELPERS
# ═══════════════════════════════════════════════════════════
def bal(uid): return float(wallets.get(str(uid), 0))
def add_bal(uid, amt):
    wallets[str(uid)] = round(bal(uid) + amt, 2)
    _save(WALLETS_FILE, wallets)
def ded_bal(uid, amt):
    wallets[str(uid)] = max(0, round(bal(uid) - amt, 2))
    _save(WALLETS_FILE, wallets)
def set_bal(uid, amt):
    wallets[str(uid)] = round(float(amt), 2)
    _save(WALLETS_FILE, wallets)

# ═══════════════════════════════════════════════════════════
#  PROMO CODE
# ═══════════════════════════════════════════════════════════
def apply_promo(uid, code, amount):
    code = code.strip().upper()
    p = promos.get(code)
    if not p: return amount, 0, "❌ Promo Code ខុស!"
    if p.get("uses", 0) > 0 and p.get("used", 0) >= p["uses"]:
        return amount, 0, "❌ Promo Code ផុតសិទ្ធហើយ!"
    user_used = p.get("user_used", {})
    if str(uid) in user_used:
        return amount, 0, "❌ អ្នកបានប្រើ Promo Code នេះហើយ!"
    if p.get("pct", False):
        discount = round(amount * float(p["discount"]) / 100, 2)
    else:
        discount = min(float(p["discount"]), amount)
    final = max(0, round(amount - discount, 2))
    return final, discount, None

def confirm_promo(code, uid):
    code = code.strip().upper()
    p = promos.get(code)
    if not p: return
    p["used"] = p.get("used", 0) + 1
    uu = p.get("user_used", {})
    uu[str(uid)] = 1
    p["user_used"] = uu
    _save(PROMO_FILE, promos)

# ═══════════════════════════════════════════════════════════
#  SMM HELPERS
# ═══════════════════════════════════════════════════════════
def _smm_get_categories():
    cats = []
    for s in smm_services.values():
        c = s.get("category", "Other")
        if c not in cats: cats.append(c)
    return cats

def _smm_get_svcs_in_cat(cat):
    return [(slug, s) for slug, s in smm_services.items() if s.get("category") == cat]

def _smm_profit_pct(): return float(smm_profit.get("pct", 20))

def _smm_sell_rate(cost, slug=None):
    s = smm_services.get(slug, {})
    if s.get("flat_price"): return float(s["flat_price"]) * 1000  # convert to per-1K for display
    if s.get("custom_price"): return float(s["custom_price"])
    return round(float(cost) * (1 + _smm_profit_pct() / 100), 4)

def _smm_price_for_order(slug, qty):
    """Get actual price for an order (handles flat_price services)"""
    s = smm_services.get(slug, {})
    if s.get("flat_price"):
        return float(s["flat_price"])  # flat: always $0.99 regardless of qty
    sr = _smm_sell_rate(s.get("cost_rate", 0), slug)
    return round(sr * qty / 1000, 4)

def _smm_api_post(params, timeout=25):
    url = smm_api.get("url", "")
    if not url: return None
    try:
        r = http.post(url, data=params, timeout=timeout)
        return r.json()
    except Exception as e:
        logger.error(f"SMM API: {e}"); return None

def _smm_fetch_service(api_id):
    key = smm_api.get("key", "")
    url = smm_api.get("url", "")
    if not key or not url:
        logger.error("SMM API: url or key not set")
        return None
    try:
        r = http.post(url, data={"key": key, "action": "services"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            logger.error(f"SMM API error: {data['error']}")
            return None
        for s in data:
            if str(s.get("service")) == str(api_id):
                # API panels use "rate" as cost per 1000, some use "min" fallback
                rate = s.get("rate") or s.get("price") or s.get("cost") or "0"
                return {
                    "cost_rate": str(rate),
                    "min":       max(1, int(float(s.get("min") or 10))),
                    "max":       int(float(s.get("max") or 100000)),
                    "raw_name":  s.get("name") or s.get("Name") or str(api_id),
                }
        logger.error(f"SMM API: service {api_id} not found in list")
    except Exception as e:
        logger.error(f"Fetch service {api_id}: {e}")
    return None

def _smm_clean_name(raw):
    raw = re.sub(r'\s*\[.*?\]\s*', ' ', raw)
    raw = re.sub(r'\s*\(.*?\)\s*', ' ', raw)
    return re.sub(r'\s+', ' ', raw).strip()[:60]

def _smm_service_list_text():
    if not smm_services: return "❌ គ្មាន Service ទេ"
    lines = ["<b>📋 SMM Services</b>\n━━━━━━━━━━━━━━━━━━"]
    for cat in _smm_get_categories():
        lines.append(f"\n📂 <b>{cat}</b>")
        for slug, s in _smm_get_svcs_in_cat(cat):
            sr = _smm_sell_rate(s["cost_rate"], slug)
            lines.append(f"  • {s.get('label',slug)} — ${sr:.2f}/1K")
    return "\n".join(lines)

def _send_order_notify(uid, oid, label, qty, link, price):
    """Send purchase notification to admin channel/group"""
    cid = notify_cfg.get("channel_id", "")
    if not cid or not notify_cfg.get("enabled", False):
        return
    try:
        msg = (
            f"🛒 <b>Order ថ្មី!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 User ID: <code>{uid}</code>\n"
            f"📦 សេវា: {label}\n"
            f"🔢 ចំនួន: {qty:,}\n"
            f"💵 តម្លៃ: <b>${price:.2f}</b>\n"
            f"🆔 Order ID: <code>{oid}</code>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        bot.send_message(cid, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Notify channel error: {e}")

def _send_deposit_notify(uid, amount, bonus, new_bal):
    """Send deposit notification to admin channel/group"""
    cid = notify_cfg.get("channel_id", "")
    if not cid or not notify_cfg.get("enabled", False):
        return
    try:
        msg = (
            f"💰 <b>ដាក់លុយ ថ្មី!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 User ID: <code>{uid}</code>\n"
            f"💵 បានទទួល: <b>${amount:.2f}</b>\n"
        )
        if bonus > 0:
            msg += f"🎟️ Bonus: <b>+${bonus:.2f}</b>\n"
        msg += (
            f"💳 Balance ថ្មី: <b>${new_bal:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        bot.send_message(cid, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Notify deposit channel error: {e}")

def _make_order_id():
    return f"KZ{int(time.time())%100000:05d}"

def _place_smm_order(uid, slug, qty, link):
    uid_str = str(uid)
    s = smm_services.get(slug)
    if not s: return None, "❌ Service រកមិនឃើញ"
    sr    = _smm_sell_rate(s["cost_rate"], slug)
    price = sr * qty / 1000
    if bal(uid) < price: return None, f"❌ Balance មិនគ្រប់! (Balance: ${bal(uid):.2f})"
    ded_bal(uid, price)
    key = smm_api.get("key",""); url = smm_api.get("url","")
    res = None
    if key and url:
        res = _smm_api_post({"key": key, "action": "add",
                             "service": s["api_id"], "link": link, "quantity": qty})
    api_order_id = str(res.get("order","")) if res else ""
    oid = _make_order_id()
    smm_orders[oid] = {
        "uid": uid_str, "slug": slug, "label": s.get("label",slug),
        "qty": qty, "price": price, "link": link, "api_order_id": api_order_id,
        "status": "pending", "ts": int(time.time()),
    }
    _save(SMM_ORD_FILE, smm_orders)
    _send_order_notify(uid, oid, s.get("label", slug), qty, link, price)
    return oid, None

# ═══════════════════════════════════════════════════════════
#  CAMRAPIDPAY — Create KHQR + Check payment
#  (v9: replace manual EMV TLV with CamRapidPay API)
# ═══════════════════════════════════════════════════════════

def _camrapid_create(uid, amount, reference):
    """Create KHQR payment via CamRapidPay API — returns response dict or None"""
    payload = {
        "api_key":   CAMRAPID_API_KEY,
        "amount":    round(float(amount), 2),
        "reference": reference,
    }
    if WEBHOOK_URL:
        payload["webhook_url"] = WEBHOOK_URL
    else:
        payload["webhook_url"] = f"https://placeholder.kairozen.store/wh/{reference}"

    logger.info(f"[camrapid_create] uid={uid} ref={reference} amount={payload['amount']}")
    try:
        r = http.post(CAMRAPID_CREATE,
                      json=payload,
                      headers={"Content-Type": "application/json",
                               "Accept": "application/json"},
                      timeout=15)
        logger.info(f"[camrapid_create] HTTP {r.status_code}")
        data = r.json()
        logger.info(f"[camrapid_create] resp={data}")
        if data.get("success"):
            return data   # keys: qr_code, payment_url, bill_number, amount, expires_in
        logger.error(f"[camrapid_create] failed: {data}")
        return None
    except Exception as e:
        logger.error(f"[camrapid_create] exception: {e}")
        return None

def _camrapid_check(reference) -> bool:
    """Check payment status via CamRapidPay API — returns True if paid"""
    try:
        r = http.get(
            CAMRAPID_CHECK,
            params={"api_key": CAMRAPID_API_KEY, "reference": reference},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        data = r.json()
        logger.info(f"[camrapid_check] ref={reference} resp={data}")
        return data.get("success") and data.get("status") in ("Success", "success", "PAID", "paid")
    except Exception as e:
        logger.error(f"[camrapid_check] {e}")
        return False

def _watch_deposit(uid, uid_str, dep_id, amount, reference):
    """Poll CamRapidPay until paid or expired (5 min)"""
    deadline = time.time() + DEPOSIT_EXPIRE_SEC + 30
    while time.time() < deadline:
        dep = smm_deps.get(dep_id)
        if not dep or dep.get("status") != "pending": return
        if _camrapid_check(reference):
            bonus = float(dep.get("bonus") or 0)
            total = round(amount + bonus, 2)
            add_bal(uid, total)
            smm_deps[dep_id]["status"] = "confirmed"
            _save(SMM_DEP_FILE, smm_deps)
            new_b = bal(uid)
            msg = (f"✅ <b>ដាក់លុយបានជោគជ័យហើយ!</b> 🙏\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"💰 បានទទួល: <b>${amount:.2f}</b>")
            if bonus > 0:
                msg += f"\n🎟️ Promo Bonus: <b>+${bonus:.2f}</b>"
            msg += f"\n💳 Balance: <b>${new_b:.2f}</b>"
            try: bot.send_message(uid, msg, parse_mode="HTML", reply_markup=main_kb(uid))
            except: pass
            try:
                bot.send_message(ADMIN_ID,
                    f"💰 <b>ដាក់លុយ ✅</b>\n👤 <code>{uid_str}</code>\n"
                    f"📌 Ref: <code>{reference}</code>\n"
                    f"💰 ${amount:.2f}" + (f" + Bonus ${bonus:.2f}" if bonus > 0 else ""),
                    parse_mode="HTML")
            except: pass
            _send_deposit_notify(uid, amount, bonus, new_b)
            return
        time.sleep(POLL_INTERVAL)
    dep = smm_deps.get(dep_id)
    if dep and dep.get("status") == "pending":
        dep["status"] = "expired"; _save(SMM_DEP_FILE, smm_deps)
        try: bot.send_message(uid, "⏰ <b>QR ផុតកំណត់!</b> សូម top up ម្តងទៀត", parse_mode="HTML")
        except: pass

def _send_deposit_qr(uid, amount, promo_code=None, label="💸 ដាក់លុយ", bonus=0.0, promo_code_name=None):
    """Create KHQR via CamRapidPay API → send QR image to user"""
    uid_str       = str(uid)
    promo_applied = promo_code_name
    reference     = f"KZ{uid}_{int(time.time())}"[:50]

    # Call CamRapidPay API to create KHQR
    resp = _camrapid_create(uid, amount, reference)
    if not resp:
        bot.send_message(uid, "⚠️ <b>មានបញ្ហា Generate QR!</b>\nសូមព្យាយាមម្តងទៀត ឬ ទំនាក់ Admin",
                         parse_mode="HTML")
        return

    qr_str      = resp.get("qr_code", "")
    payment_url = resp.get("payment_url", "")

    dep_id = f"dep_{uid}_{int(time.time())}"
    smm_deps[dep_id] = {
        "uid":         uid_str,
        "amount":      amount,
        "status":      "pending",
        "bonus":       bonus,
        "promo":       promo_applied or "",
        "reference":   reference,
        "payment_url": payment_url,
    }
    _save(SMM_DEP_FILE, smm_deps)

    if promo_applied and bonus > 0:
        confirm_promo(promo_applied, uid)

    cap = (f"{label}\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"💰 Amount: <b>${amount:.2f}</b>\n"
           f"⏱ Expires in: <b>5 minutes</b>\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"📱 Scan with ABA · Bakong · Wing · ACLEDA\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"✅ <i>System auto-detects payment — balance updates instantly after scan!</i>")

    # Generate QR image from qr_code string
    img_buf = None
    if qr_str:
        try:
            import qrcode as _qrc
            qr = _qrc.QRCode(box_size=8, border=2,
                             error_correction=_qrc.constants.ERROR_CORRECT_M)
            qr.add_data(qr_str); qr.make(fit=True)
            img = qr.make_image(fill_color="#0a2240", back_color="white").convert("RGB")
            img_buf = io.BytesIO(); img.save(img_buf, format="PNG"); img_buf.seek(0)
            img_buf.name = "khqr.png"
        except Exception as ie:
            logger.warning(f"[deposit_qr] qrcode gen failed: {ie}")

    if img_buf:
        try: bot.send_photo(uid, img_buf, caption=cap, parse_mode="HTML")
        except: bot.send_message(uid, cap, parse_mode="HTML")
    else:
        bot.send_message(uid, cap, parse_mode="HTML")

    threading.Thread(target=_watch_deposit,
                     args=(uid, uid_str, dep_id, amount, reference), daemon=True).start()

def _get_dep_promo(uid):
    step = waiting.get(uid)
    if isinstance(step, dict):
        return step.get("promo")
    return None

def _process_deposit(uid, uid_str, amount, promo_code=None):
    lang  = get_lang(uid)
    bonus = 0.0
    promo_applied = None
    if promo_code:
        p = promos.get(promo_code.upper())
        if p and (p.get("uses", 0) == 0 or p.get("used", 0) < p.get("uses", 0)):
            if str(uid) not in p.get("user_used", {}):
                if p.get("pct", False):
                    bonus = round(amount * float(p["discount"]) / 100, 2)
                else:
                    bonus = round(float(p["discount"]), 2)
                promo_applied = promo_code.upper()
    _send_deposit_qr(uid, amount,
                     label=f"💸 <b>{'ដាក់លុយ' if lang=='kh' else 'Top Up'}</b>",
                     bonus=bonus, promo_code_name=promo_applied)

# ═══════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════
def main_kb(uid=None):
    lang = get_lang(uid) if uid else "kh"
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "en":
        kb.row("👤 My Account",      "💸 Top Up")
        kb.row("🛒 Order Service")
        kb.row("📋 Order History",   "🔍 Track Order")
        kb.row("💬 Support")
    else:
        kb.row("👤 គណនី",            "💸 បញ្ចូលលុយ")
        kb.row("🛒 បញ្ជាទិញសេវា")
        kb.row("📋 ប្រវត្តិការបញ្ជាទិញ", "🔍 តាមដានការបញ្ជាទិញ")
        kb.row("💬 ជំនួយ")
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 ការបញ្ជា SMM",  "⚙️ កំណត់ SMM API")
    kb.row("➕ បន្ថែម SMM",    "✍️ Manual SMM")
    kb.row("🗑️ លុប SMM",    "✏️ កែ SMM")
    kb.row("💹 ប្រាក់ចំណេញ SMM","📋 SMM Services")
    kb.row("━━━ 💰 ហិរញ្ញវត្ថុ ━━━")
    kb.row("💰 កាបូបលុយ",      "💳 ប្រាក់បញ្ញើ")
    kb.row("💸 បន្ថែមប្រាក់",   "💔 កាត់ប្រាក់")
    kb.row("━━━ 👥 អ្នកប្រើ ━━━")
    kb.row("👥 អ្នកប្រើប្រាស់",  "📊 ស្ថិតិ")
    kb.row("📢 ផ្សព្វផ្សាយ")
    kb.row("⏱ ល្បឿន Poll",     "💰 ឆែកលុយ API")
    kb.row("🖼️ Welcome Photo",  "🔄 ធ្វើឱ្យទាន់សម័យ")
    kb.row("🔔 Notify Channel")
    return kb

def cancel_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✕ Cancel")
    return kb

def deposit_amt_kb(uid=None, promo_code=None):
    lang = get_lang(uid) if uid else "kh"
    # Preset amounts
    amounts = [1, 2, 5, 10, 20, 50]
    btns = []
    row = []
    for i, amt in enumerate(amounts):
        row.append(InlineKeyboardButton(f"💵 ${amt}", callback_data=f"dep:amt:{amt}"))
        if len(row) == 3:
            btns.append(row); row = []
    if row: btns.append(row)
    # Custom amount
    btns.append([InlineKeyboardButton(
        "✏️ ចំនួនផ្សេង" if lang=="kh" else "✏️ Custom Amount",
        callback_data="dep:custom")])
    return InlineKeyboardMarkup(btns)

def smm_cat_kb():
    PLATFORM_ICONS = {
        "tiktok khmer": "🇰🇭",
        "tiktok": "🎵", "telegram": "📱", "facebook": "📘",
        "instagram": "📸", "youtube": "▶️", "twitter": "🐦",
        "x": "🐦", "threads": "🧵"
    }
    cats = _smm_get_categories()
    btns = []
    for cat in cats:
        icon = "📱"
        for key, ico in PLATFORM_ICONS.items():
            if key in cat.lower(): icon = ico; break
        btns.append([InlineKeyboardButton(f"{icon}  {cat}", callback_data=f"smmcat:{cat}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:main")])
    return InlineKeyboardMarkup(btns)

def smm_svc_kb(cat):
    SVC_ICONS = {
        "follower":"👤","like":"❤️","view":"👁","comment":"💬",
        "share":"🔗","save":"🔖","member":"👥","subscriber":"🔔",
        "watch":"👀","reaction":"😍",
    }
    svcs = _smm_get_svcs_in_cat(cat)
    btns = []
    for slug, s in svcs:
        label = s.get("label", slug)
        icon = "⚡"
        for key, ico in SVC_ICONS.items():
            if key in label.lower(): icon = ico; break
        btns.append([InlineKeyboardButton(f"{icon}  {label}", callback_data=f"smmsvc:{slug}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats")])
    return InlineKeyboardMarkup(btns)

def smm_qty_kb(slug, s):
    sr    = _smm_sell_rate(s["cost_rate"], slug)
    mn    = s.get("min", 10)
    mx    = s.get("max", 100000)
    label = s.get("label", slug)
    first = label.split()[0] if label else slug
    # Flat price service — only 1 option
    if s.get("flat_price"):
        flat = float(s["flat_price"])
        btns = [[InlineKeyboardButton(
            f"✅ Order — ${flat:.2f}", callback_data=f"smmqty:{slug}:1")]]
        btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats")])
        return InlineKeyboardMarkup(btns)
    preset = s.get("preset_qtys")
    if preset and isinstance(preset, list):
        qtys = [q for q in preset if mn <= q <= mx]
    else:
        suggestions = [100, 500, 1000, 5000, 10000, 50000]
        qtys = []
        for q in [mn] + suggestions:
            if mn <= q <= mx and q not in qtys: qtys.append(q)
            if len(qtys) >= 6: break
    btns = []
    for q in qtys:
        price = sr * q / 1000
        btns.append([InlineKeyboardButton(
            f"{q:,} {first} — ${price:.2f}", callback_data=f"smmqty:{slug}:{q}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats")])
    return InlineKeyboardMarkup(btns)

# ═══════════════════════════════════════════════════════════
#  USER TRACKING
# ═══════════════════════════════════════════════════════════
def _track_user(message):
    uid = message.chat.id
    uid_str = str(uid)
    u = message.from_user
    users_db[uid_str] = {
        "name":     u.first_name or "",
        "username": u.username or "",
        "last":     int(time.time()),
        "banned":   users_db.get(uid_str, {}).get("banned", False),
    }
    _save(USERS_FILE, users_db)
    wallets.setdefault(uid_str, 0.0)

def is_banned(uid):
    return bool(users_db.get(str(uid), {}).get("banned", False))

# ═══════════════════════════════════════════════════════════
#  ADMIN PROMO HELPERS
# ═══════════════════════════════════════════════════════════
def _show_promos(uid):
    if not promos:
        bot.send_message(uid, "🎟️ <b>គ្មាន Promo Code ទេ</b>", parse_mode="HTML",
                         reply_markup=admin_kb()); return
    lines = ["🎟️ <b>Promo Codes</b>\n━━━━━━━━━━━━━━━━━━"]
    for code, p in promos.items():
        dtype = f"{p['discount']:.0f}%" if p.get("pct") else f"${float(p.get('discount',0)):.2f}"
        lines.append(f"• <code>{code}</code> — {dtype} | {p.get('used',0)}/{p.get('uses',0)} used")
    bot.send_message(uid, "\n".join(lines), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.chat.id
    waiting.pop(uid, None)
    _track_user(message)
    if is_banned(uid):
        bot.send_message(uid, t(uid, "banned")); return
    if uid == ADMIN_ID:
        bot.send_message(uid,
            f"🤖 <b>Panel Admin — Kairozen SMM</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{ADMIN_ID}</code>\n"
            f"💹 ចំណេញ SMM: <b>{_smm_profit_pct():.0f}%</b>\n"
            f"⏱ Poll: <b>{smm_poll.get('interval',5)}s</b>\n"
            f"📊 Services: <b>{len(smm_services)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML", reply_markup=admin_kb())
        return
    if str(uid) not in user_lang:
        bot.send_message(uid,
            "សួស្តី! 👋 ជ្រើសភាសាដែលអ្នកចូលចិត្តសិន\n"
            "<i>Hi! Pick your language first 😊</i>",
            parse_mode="HTML", reply_markup=lang_select_kb())
        return
    _show_welcome(uid)

WELCOME_SETTINGS_FILE = "smm_welcome.json"
welcome_cfg = _load(WELCOME_SETTINGS_FILE, {"photo_id": ""})

def _save_welcome_photo(file_id):
    welcome_cfg["photo_id"] = file_id
    _save(WELCOME_SETTINGS_FILE, welcome_cfg)

def _show_welcome(uid):
    b       = bal(uid)
    caption = t(uid, "welcome", b)
    photo_id = welcome_cfg.get("photo_id", "")
    if photo_id:
        try:
            bot.send_photo(
                uid,
                photo=photo_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=main_kb(uid)
            )
            return
        except Exception:
            pass
    # Fallback: text only
    bot.send_message(uid, caption, parse_mode="HTML", reply_markup=main_kb(uid))

# ═══════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("setlang:"))
def cb_setlang(call):
    uid  = call.message.chat.id
    lang = call.data.split(":")[1]
    user_lang[str(uid)] = lang
    _save(LANG_FILE, user_lang)
    bot.answer_callback_query(call.id, t(uid, "lang_set"))
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    _show_welcome(uid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("poll:"))
def cb_poll(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    sec = int(call.data.split(":")[1])
    smm_poll["interval"] = sec; _save(SMM_POLL_FILE, smm_poll)
    bot.answer_callback_query(call.id, f"✅ Poll = {sec}s")
    try: bot.edit_message_text(f"✅ Poll Speed = <b>{sec} វិ</b>",
                               chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("dep:"))
def cb_dep(call):
    uid     = call.message.chat.id
    uid_str = str(uid)
    lang    = get_lang(uid)
    val     = call.data[4:]
    bot.answer_callback_query(call.id)

    # ── ជ្រើស amount preset ──
    if val.startswith("amt:"):
        amount = float(val.split(":")[1])
        waiting.pop(uid, None)
        _process_deposit(uid, uid_str, amount, None)
        return

    # ── custom amount ──
    if val == "custom":
        waiting[uid] = {"step": "dep_custom_amt"}
        bot.send_message(uid,
            "✏️ <b>វាយចំនួន (USD):</b>\nឧ: <code>3</code> ឬ <code>7.50</code>" if lang=="kh" else
            "✏️ <b>Enter amount (USD):</b>\ne.g. <code>3</code> or <code>7.50</code>",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

@bot.callback_query_handler(func=lambda c: c.data.startswith("back:"))
def cb_back(call):
    uid  = call.message.chat.id
    dest = call.data[5:]
    bot.answer_callback_query(call.id)
    waiting.pop(uid, None)
    if dest == "main":
        try: bot.delete_message(uid, call.message.message_id)
        except: pass
        _show_welcome(uid)
    elif dest == "smmcats":
        try:
            bot.edit_message_text("📊 <b>SMM Services</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Platform:",
                                  chat_id=uid, message_id=call.message.message_id,
                                  parse_mode="HTML", reply_markup=smm_cat_kb())
        except:
            bot.send_message(uid, "📊 <b>SMM Services</b>",
                             parse_mode="HTML", reply_markup=smm_cat_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmcat:"))
def cb_smmcat(call):
    uid = call.message.chat.id
    cat = call.data[7:]
    bot.answer_callback_query(call.id)
    svcs = _smm_get_svcs_in_cat(cat)
    if not svcs:
        try: bot.answer_callback_query(call.id, "❌ គ្មាន Service", show_alert=True)
        except: pass
        return
    is_tiktok_khmer = "tiktok khmer" in cat.lower()
    if is_tiktok_khmer:
        header = (
            f"🇰🇭 <b>TikTok Khmer Services!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• ធានាបានអ្នកមើលខ្មែរ 100%\n"
            f"• អាចបានលើសទៅតាមវីដេអូ\n\n"
            f"ជ្រើសសេវាកម្ម:"
        )
    else:
        header = f"📂 <b>{cat}</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Service:"
    try:
        bot.edit_message_text(header,
                              chat_id=uid, message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=smm_svc_kb(cat))
    except:
        bot.send_message(uid, header, parse_mode="HTML", reply_markup=smm_svc_kb(cat))

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmsvc:"))
def cb_smmsvc(call):
    uid  = call.message.chat.id
    slug = call.data[7:]
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
    sr   = _smm_sell_rate(s["cost_rate"], slug)
    lang = get_lang(uid)
    # Price display
    if s.get("flat_price"):
        price_line = f"💰 តម្លៃ: <b>${float(s['flat_price']):.2f} / order</b>"
    else:
        price_line = f"💰 {'តម្លៃ' if lang=='kh' else 'Price'}: <b>${sr:.2f}/1K</b>\n📏 Min: {s.get('min',10):,}  ·  Max: {s.get('max',100000):,}"
    desc_line = f"\n📋 {s['description']}" if s.get("description") else ""
    txt  = (f"⚡ <b>{s.get('label',slug)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{price_line}"
            f"{desc_line}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{'ជ្រើស Quantity:' if lang=='kh' else 'Choose Quantity:'}")
    try:
        bot.edit_message_text(txt, chat_id=uid, message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=smm_qty_kb(slug, s))
    except:
        bot.send_message(uid, txt, parse_mode="HTML", reply_markup=smm_qty_kb(slug, s))

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmqty:"))
def cb_smmqty(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    slug  = parts[1]; qty = int(parts[2])
    s     = smm_services.get(slug)
    if not s: return
    price = _smm_price_for_order(slug, qty)
    lang  = get_lang(uid)
    is_tiktok_promote = s.get("flat_price") and "tiktok" in slug.lower()
    if is_tiktok_promote:
        link_prompt = (
            f"🔗 <b>ផ្ញើ Link វីដេអូ TikTok:</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 {s.get('label',slug)}\n"
            f"💰 តម្លៃ: <b>${price:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>សំខាន់!</b> បន្ទាប់ពី order:\n"
            f"1️⃣ ចូល TikTok Inbox\n"
            f"2️⃣ System notifications → Promote Assistant\n"
            f"3️⃣ ចុច <b>Respond</b> → <b>Authorize</b> → <b>Confirm</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📎 ឧ: <code>https://www.tiktok.com/@user/video/123</code>"
        )
    else:
        link_prompt = (
            f"🔗 <b>{'ផ្ញើ Link:' if lang=='kh' else 'Send Link:'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 {s.get('label',slug)}\n"
            f"💰 {qty:,} — <b>${price:.4f}</b>"
        )
    waiting[uid] = {"step": "smm_link", "slug": slug, "qty": qty, "price": price}
    try:
        bot.edit_message_text(
            link_prompt,
            chat_id=uid, message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="back:main")]]))
    except:
        bot.send_message(uid, link_prompt, parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmapi:"))
def cb_smmapi(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    action = call.data[7:]
    bot.answer_callback_query(call.id)

    if action == "setup":
        waiting[uid] = "smm_api_url"
        bot.send_message(uid,
            "🌐 <b>ផ្ញើ SMM API URL</b>\nឧ: <code>https://smmking.net/api/v2</code>",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "test":
        url = smm_api.get("url",""); key = smm_api.get("key","")
        if not url or not key:
            bot.send_message(uid, "❌ API មិនទាន់ set!", reply_markup=admin_kb()); return
        try:
            r = http.post(url, data={"key": key, "action": "balance"}, timeout=10)
            d = r.json()
            balance  = d.get("balance", d.get("Balance", "?"))
            currency = d.get("currency", d.get("Currency", "USD"))
            bot.send_message(uid,
                f"✅ <b>Connection OK!</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"💰 Balance: <b>{balance} {currency}</b>",
                parse_mode="HTML", reply_markup=admin_kb())
        except Exception as e:
            bot.send_message(uid, f"❌ Connection failed: <code>{e}</code>",
                             parse_mode="HTML", reply_markup=admin_kb())

    elif action == "clear":
        smm_api.clear(); smm_api.update({"url":"","key":""})
        _save(SMM_API_FILE, smm_api)
        bot.send_message(uid, "🗑️ SMM API cleared!", reply_markup=admin_kb())

# ── Admin: Confirm / Reject deposit ──
@bot.callback_query_handler(func=lambda c: c.data.startswith("admconf:"))
def cb_admconf(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    dep_id = call.data[8:]
    dep    = smm_deps.get(dep_id)
    if not dep or dep.get("status") != "pending":
        bot.answer_callback_query(call.id, "⚠️ Deposit មិន pending ទេ", show_alert=True); return
    bot.answer_callback_query(call.id)
    # Ask admin for amount
    waiting[uid] = {"step": "adm_confirm_dep", "dep_id": dep_id}
    bot.send_message(uid,
        f"💰 <b>Enter amount received (USD):</b>\n"
        f"📌 Ref: <code>{dep.get('reference','')}</code>\n"
        f"👤 User: <code>{dep.get('uid','')}</code>",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("admrej:"))
def cb_admrej(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    dep_id = call.data[7:]
    dep    = smm_deps.get(dep_id)
    if not dep:
        bot.answer_callback_query(call.id, "❌ Deposit រកមិនឃើញ", show_alert=True); return
    bot.answer_callback_query(call.id)
    dep["status"] = "rejected"; _save(SMM_DEP_FILE, smm_deps)
    try:
        bot.edit_message_text(
            f"❌ <b>Deposit Rejected</b>\n📌 Ref: <code>{dep.get('reference','')}</code>",
            chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
    except: pass
    try:
        bot.send_message(int(dep["uid"]),
            "❌ <b>ការ Deposit ត្រូវបាន Reject!</b>\nទំនាក់ Admin: @KhmerSmm099",
            parse_mode="HTML")
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("mansvc_cat:"))
def cb_mansvc_cat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    cat = call.data[len("mansvc_cat:"):]
    bot.answer_callback_query(call.id)
    step = waiting.get(uid, {})
    label = step.get("label", "") if isinstance(step, dict) else ""
    if cat == "__custom__":
        waiting[uid] = {"step": "manual_svc_cat_custom", "label": label}
        bot.send_message(uid,
            "✏️ <b>វាយ Category ផ្ទាល់ខ្លួន:</b>\nឧ: <code>TikTok Khmer</code>",
            parse_mode="HTML", reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "manual_svc_price", "label": label, "cat": cat}
        bot.send_message(uid,
            f"💰 <b>ដាក់តម្លៃ (USD per 1000)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📂 Category: <b>{cat}</b>\n"
            f"📝 ឈ្មោះ: <b>{label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ឧ: <code>0.50</code> = $0.50 per 1K\n"
            f"ឧ: <code>1.20</code> = $1.20 per 1K",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("manord:"))
def cb_manord(call):
    """Admin: mark manual order as completed"""
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    parts = call.data.split(":")
    action = parts[1]
    oid    = parts[2] if len(parts) > 2 else ""
    bot.answer_callback_query(call.id)
    o = smm_orders.get(oid)
    if not o:
        bot.send_message(uid, f"❌ Order <code>{oid}</code> រកមិនឃើញ",
                         parse_mode="HTML"); return
    if action == "done":
        waiting[uid] = {"step": "manual_order_done", "oid": oid, "user_uid": o["uid"]}
        bot.send_message(uid,
            f"✅ <b>Complete Order</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{oid}</code>\n"
            f"👤 User: <code>{o['uid']}</code>\n"
            f"📊 {o.get('label','?')} × {o.get('qty',0):,}\n"
            f"🔗 <code>{o.get('link','?')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>វាយ Note ឲ្យ User</b> (ឬ <code>-</code> ដើម្បីរំលង):",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "reject":
        smm_orders[oid]["status"] = "rejected"
        _save(SMM_ORD_FILE, smm_orders)
        try:
            bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
        except: pass
        try:
            bot.send_message(int(o["uid"]),
                f"❌ <b>Order ត្រូវបាន Reject!</b>\n"
                f"🆔 <code>{oid}</code>\n"
                f"💳  លុយបានដក (${ o.get('price',0):.4f}) ត្រូវបានសងវិញ\n"
                f"ទំនាក់ Admin ប្រសិនបើចង់ដឹង: @smos_sne1",
                parse_mode="HTML")
            # Refund
            add_bal(int(o["uid"]), float(o.get("price") or 0))
        except: pass
        bot.send_message(uid,
            f"❌ <b>Rejected & Refunded</b>\n🆔 <code>{oid}</code>",
            parse_mode="HTML", reply_markup=admin_kb())


@bot.callback_query_handler(func=lambda c: c.data.startswith("editsvc:"))
def cb_editsvc(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    slug = call.data[len("editsvc:"):]
    s = smm_services.get(slug)
    if not s:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    old_label = s.get("label", slug)
    api_id    = s.get("api_id", "?")
    waiting[uid] = {"step": "edit_svc_name", "slug": slug}
    bot.send_message(uid,
        f"✏️ <b>កែឈ្មោះ Service</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 API ID: <code>{api_id}</code>\n"
        f"📝 ឈ្មោះ​បច្ចុប្បន្ន:\n<b>{old_label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"វាយ <b>ឈ្មោះថ្មី</b>:",
        parse_mode="HTML", reply_markup=cancel_kb())


@bot.callback_query_handler(func=lambda c: c.data.startswith("smmaddcat:"))
def cb_smmaddcat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    cat = call.data[len("smmaddcat:"):]
    bot.answer_callback_query(call.id)
    if cat == "custom":
        waiting[uid] = "smm_add_cat"
        bot.send_message(uid, "✏️ វាយ Category name (ឧ: TikTok Live, Spotify):",
                         reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "smm_add_ids", "cat": cat}
        bot.send_message(uid,
            f"📂 Category: <b>{cat}</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"ផ្ញើ Service IDs (comma separated):\n"
            f"ឧ: <code>5441,5448,5502</code>\n\n"
            f"💡 IDs រក នៅ SMM Panel → Services",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("delsvc:"))
def cb_delsvc(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    parts = call.data.split(":", 2)

    if len(parts) == 3 and parts[1] == "cat":
        cat = parts[2]
        to_del = [slug for slug, s in smm_services.items() if s.get("category") == cat]
        for slug in to_del:
            smm_services.pop(slug, None)
        _save(SMM_SVC_FILE, smm_services)
        try: bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
        except: pass
        bot.send_message(uid,
            f"✅ Deleted <b>{len(to_del)}</b> services in <b>{cat}</b>",
            parse_mode="HTML", reply_markup=admin_kb())
        return

    slug = parts[1]
    s    = smm_services.get(slug)
    if not s:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    label  = s.get("label", slug)
    api_id = s.get("api_id", "?")
    smm_services.pop(slug, None)
    _save(SMM_SVC_FILE, smm_services)
    try: bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except: pass
    bot.send_message(uid,
        f"✅ Deleted: <b>[{api_id}] {label}</b>\n"
        f"📊 Remaining: <b>{len(smm_services)}</b>",
        parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("useraction:"))
def cb_useraction(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    parts  = call.data.split(":")
    action = parts[1]
    target = parts[2] if len(parts) > 2 else ""

    if action == "addbal":
        waiting[uid] = {"step": "add_balance_amt", "target": target}
        bot.send_message(uid,
            f"💸 <b>បន្ថែមប្រាក់</b>\n👤 UID: <code>{target}</code>\n"
            f"💳 Balance: <b>${bal(int(target)):.2f}</b>\nផ្ញើ Amount $:",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "dedbal":
        waiting[uid] = {"step": "deduct_balance_amt", "target": target}
        bot.send_message(uid,
            f"💔 <b>កាត់ប្រាក់</b>\n👤 UID: <code>{target}</code>\n"
            f"💳 Balance: <b>${bal(int(target)):.2f}</b>\nផ្ញើ Amount $ ដក:",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "ban":
        users_db[target]["banned"] = True; _save(USERS_FILE, users_db)
        bot.send_message(uid, f"🚫 Banned <code>{target}</code>",
                         parse_mode="HTML", reply_markup=admin_kb())

    elif action == "unban":
        users_db[target]["banned"] = False; _save(USERS_FILE, users_db)
        bot.send_message(uid, f"🔓 Unbanned <code>{target}</code>",
                         parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adminpromo:"))
def cb_adminpromo(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    action = call.data[len("adminpromo:"):]
    if action == "add":
        waiting[uid] = "promo_add_code"
        bot.send_message(uid,
            "🎟️ <b>បន្ថែម Promo Code</b>\n━━━━━━━━━━━━━━━━━━\n"
            "Format: <code>CODE DISCOUNT TYPE USES</b></code>\n\n"
            "TYPE: <code>pct</code> (%) ឬ <code>fix</code> ($)\n\n"
            "ឧទាហរណ៍:\n"
            "<code>SAVE50 50 pct 100</code>  → 50% off, 100 uses\n"
            "<code>GIFT1 1.00 fix 50</code>  → $1 bonus, 50 uses",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "list":
        _show_promos(uid)

# ═══════════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════════
def _do_broadcast(admin_uid, message):
    waiting.pop(admin_uid, None)
    sent = failed = 0
    for u_id in list(users_db.keys()):
        try:
            if message.photo:
                bot.send_photo(int(u_id), message.photo[-1].file_id, caption=message.caption or "")
            elif message.video:
                bot.send_video(int(u_id), message.video.file_id, caption=message.caption or "")
            else:
                bot.send_message(int(u_id), message.text or "", parse_mode="HTML")
            sent += 1
        except: failed += 1
        time.sleep(0.05)
    bot.send_message(admin_uid,
        f"📢 <b>ផ្សព្វផ្សាយរួចរាល់!</b>\n✅ បានផ្ញើ: {sent} | ❌ បរាជ័យ: {failed}",
        parse_mode="HTML", reply_markup=admin_kb())

# ═══════════════════════════════════════════════════════════
#  PHOTO HANDLER
# ═══════════════════════════════════════════════════════════
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    uid = message.chat.id
    step = waiting.get(uid)
    if uid == ADMIN_ID:
        if step == "broadcast_msg":
            _do_broadcast(uid, message)
        elif step == "set_welcome_photo":
            file_id = message.photo[-1].file_id
            _save_welcome_photo(file_id)
            waiting.pop(uid, None)
            bot.send_message(uid,
                "✅ <b>Welcome Photo បានរក្សា!</b>\n"
                "រូបនេះនឹងបង្ហាញពេល User ចុច /start",
                parse_mode="HTML", reply_markup=admin_kb())

        elif step == "set_notify_channel":
            waiting.pop(uid, None)
            val = text.strip()
            if val.lower() == "off":
                notify_cfg["enabled"] = False
                _save(NOTIFY_FILE, notify_cfg)
                bot.send_message(uid, "🔕 <b>Notify Channel បានបិទ!</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            else:
                notify_cfg["channel_id"] = val
                notify_cfg["enabled"] = True
                _save(NOTIFY_FILE, notify_cfg)
                bot.send_message(uid,
                    f"✅ <b>Notify Channel បានកំណត់!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📢 Channel/Group: <code>{val}</code>\n"
                    f"ស្ថានភាព: ✅ បើក\n\n"
                    f"<i>💡 ត្រូវប្រាកដថា Bot ជា Admin នៅក្នុង Channel/Group នោះ!</i>",
                    parse_mode="HTML", reply_markup=admin_kb())

# ═══════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    uid     = message.chat.id
    uid_str = str(uid)
    text    = message.text or ""
    lang    = get_lang(uid)
    step    = waiting.get(uid)

    _track_user(message)

    if is_banned(uid) and uid != ADMIN_ID:
        bot.send_message(uid, t(uid, "banned")); return

    # ── Cancel ──
    if text == "✕ Cancel":
        waiting.pop(uid, None)
        bot.send_message(uid, t(uid, "cancel_ok"), reply_markup=main_kb(uid) if uid != ADMIN_ID else admin_kb())
        return

    # ════════════════════════════════════════
    #  ADMIN SECTION
    # ════════════════════════════════════════
    if uid == ADMIN_ID:

        # Admin commands
        if text.startswith("/addbal"):
            parts = text.split()
            if len(parts) < 3:
                bot.send_message(uid, "ប្រើ: /addbal UID AMOUNT"); return
            try:
                target = parts[1]; amt = float(parts[2])
                add_bal(int(target), amt)
                bot.send_message(uid,
                    f"✅ +${amt:.2f} → <code>{target}</code>\n💳 Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"✅ Admin បន្ថែមលុយ! +${amt:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except: pass
            except: bot.send_message(uid, "❌ Format ខុស")
            return

        if text.startswith("/deductbal"):
            parts = text.split()
            if len(parts) < 3:
                bot.send_message(uid, "ប្រើ: /deductbal UID AMOUNT"); return
            try:
                target = parts[1]; amt = float(parts[2])
                cur = bal(int(target))
                ded = min(amt, cur)
                ded_bal(int(target), ded)
                bot.send_message(uid,
                    f"✅ -${ded:.2f} → <code>{target}</code>\n💳 Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except: bot.send_message(uid, "❌ Format ខុស")
            return

        # ── Waiting steps ──
        if isinstance(step, dict) and step.get("step") == "add_balance_amt":
            target = step["target"]
            try:
                amt = float(text.replace("$",""))
                add_bal(int(target), amt)
                _save(WALLETS_FILE, wallets)
                waiting.pop(uid, None)
                bot.send_message(uid,
                    f"✅ <b>បន្ថែម Balance</b>\n👤 <code>{target}</code>\n"
                    f"💰 +${amt:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"✅ <b>Admin បន្ថែមលុយ!</b>\n💰 +${amt:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except: pass
            except: bot.send_message(uid, "❌ Amount ខុស! ឧ: <code>5.00</code>", parse_mode="HTML")
            return

        if isinstance(step, dict) and step.get("step") == "deduct_balance_amt":
            target = step["target"]
            try:
                amt  = float(text.replace("$",""))
                cur  = bal(int(target))
                ded  = min(amt, cur)
                ded_bal(int(target), ded)
                waiting.pop(uid, None)
                bot.send_message(uid,
                    f"✅ <b>កាត់ Balance</b>\n👤 <code>{target}</code>\n"
                    f"💔 -${ded:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"⚠️ <b>Admin កាត់លុយ!</b>\n💔 -${ded:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except: pass
            except: bot.send_message(uid, "❌ Amount ខុស!")
            return

        if isinstance(step, dict) and step.get("step") == "edit_svc_name":
            slug = step.get("slug")
            s    = smm_services.get(slug)
            if not s:
                bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb())
                waiting.pop(uid, None); return
            old_label = s.get("label", slug)
            new_label = text.strip()
            if not new_label:
                bot.send_message(uid, "❌ ឈ្មោះទទេ! សូមវាយម្តងទៀត"); return
            smm_services[slug]["label"] = new_label
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>ឈ្មោះ Service បានផ្លាស់ប្តូរ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 API ID: <code>{s.get('api_id','?')}</code>\n"
                f"📝 ចាស់: <s>{old_label}</s>\n"
                f"✨ ថ្មី: <b>{new_label}</b>",
                parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "promo_add_code":
            parts = text.strip().split()
            if len(parts) < 4:
                bot.send_message(uid,
                    "❌ Format ខុស!\nឧ: <code>SAVE50 50 pct 100</code>\n"
                    "ឬ: <code>GIFT1 1.00 fix 50</code>", parse_mode="HTML"); return
            code = parts[0].upper()
            try:
                discount = float(parts[1])
                pct  = (parts[2].lower() == "pct")
                uses = int(parts[3])
            except:
                bot.send_message(uid, "❌ Format ខុស!", parse_mode="HTML"); return
            promos[code] = {"discount": discount, "pct": pct, "uses": uses, "used": 0}
            _save(PROMO_FILE, promos)
            waiting.pop(uid, None)
            dtype = f"{discount:.0f}%" if pct else f"${discount:.2f}"
            bot.send_message(uid,
                f"✅ <b>Promo Code Created!</b>\n"
                f"🎟️ <code>{code}</code> — <b>{dtype}</b> | {uses} uses",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "broadcast_msg":
            _do_broadcast(uid, message); return

        if step == "smm_add_cat":
            waiting[uid] = {"step": "smm_add_ids", "cat": text}
            bot.send_message(uid,
                f"📂 Category: <b>{text}</b>\n"
                f"ផ្ញើ API Service IDs (comma):\n"
                f"ឧ: <code>5441,5448,5502</code>\n\n"
                f"💡 រក IDs នៅ SMM API Panel ➡️ Services",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "smm_add_ids":
            cat = step["cat"]
            # Check API configured first
            if not smm_api.get("url") or not smm_api.get("key"):
                waiting.pop(uid, None)
                bot.send_message(uid,
                    "❌ <b>SMM API មិនទាន់ Set!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "ចុច <b>🔗 Set SMM API</b> ជាមុន រួចទើបបន្ថែម Service",
                    parse_mode="HTML", reply_markup=admin_kb()); return
            ids = [i.strip() for i in text.replace(" ", "").split(",") if i.strip().isdigit()]
            if not ids:
                bot.send_message(uid, "❌ ផ្ញើ IDs ជាលេខ ឧ: <code>5441,5448</code>",
                                 parse_mode="HTML"); return
            bot.send_message(uid, f"⏳ Fetching {len(ids)} service(s) from API...")
            ok, fail = [], []
            for api_id in ids:
                info = _smm_fetch_service(api_id)
                if info:
                    slug = f"{cat.lower().replace(' ', '_')}_{api_id}"
                    smm_services[slug] = {
                        "api_id":    api_id,
                        "cost_rate": info["cost_rate"],
                        "min":       info["min"],
                        "max":       info["max"],
                        "label":     _smm_clean_name(info["raw_name"]),
                        "category":  cat,
                    }
                    ok.append(f"✅ <code>{api_id}</code> — {smm_services[slug]['label']}")
                else:
                    fail.append(f"❌ <code>{api_id}</code> — not found / API error")
            if ok:
                _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            msg = f"<b>📊 SMM Import — {cat}</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(ok)
            if fail: msg += "\n\n<b>Failed:</b>\n" + "\n".join(fail)
            msg += f"\n\n✅ Total services: <b>{len(smm_services)}</b>"
            bot.send_message(uid, msg, parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "smm_api_url":
            smm_api["url"] = text.strip().rstrip("/")
            waiting[uid] = "smm_api_key"
            bot.send_message(uid,
                f"✅ URL: <code>{smm_api['url']}</code>\n\n🔑 ឥឡូវ ផ្ញើ API Key:",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if step == "smm_api_key":
            smm_api["key"] = text.strip()
            _save(SMM_API_FILE, smm_api)
            waiting.pop(uid, None)
            bot.send_message(uid, "⏳ Testing connection...", reply_markup=admin_kb())
            try:
                r = http.post(smm_api["url"],
                              data={"key": smm_api["key"], "action": "balance"}, timeout=10)
                d = r.json()
                balance  = d.get("balance", d.get("Balance", "?"))
                currency = d.get("currency", d.get("Currency", "USD"))
                bot.send_message(uid,
                    f"✅ <b>SMM API ភ្ជាប់ហើយ!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"🌐 URL: <code>{smm_api['url']}</code>\n"
                    f"💰 Balance: <b>{balance} {currency}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except Exception as e:
                bot.send_message(uid,
                    f"⚠️ API Saved ប៉ុន្តែ test failed: <code>{e}</code>",
                    parse_mode="HTML", reply_markup=admin_kb())
            return

        if isinstance(step, dict) and step.get("step") == "smm_set_profit":
            try:
                pct = float(text)
                smm_profit["pct"] = pct; _save(SMM_PROFIT_FILE, smm_profit)
                waiting.pop(uid, None)
                bot.send_message(uid, f"✅ SMM Profit <b>{pct:.0f}%</b>",
                                 parse_mode="HTML", reply_markup=admin_kb())
            except: bot.send_message(uid, "❌ ត្រូវជាលេខ")
            return

        # ── Manual service: step 1 label ──
        if isinstance(step, dict) and step.get("step") == "manual_svc_label":
            label = text.strip()
            if not label:
                bot.send_message(uid, "❌ ឈ្មោះទទេ! វាយម្តងទៀត:", reply_markup=cancel_kb()); return
            waiting[uid] = {"step": "manual_svc_cat", "label": label}
            cats_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 TikTok",    callback_data="mansvc_cat:TikTok"),
                 InlineKeyboardButton("📘 Facebook",  callback_data="mansvc_cat:Facebook")],
                [InlineKeyboardButton("📸 Instagram", callback_data="mansvc_cat:Instagram"),
                 InlineKeyboardButton("▶️ YouTube",   callback_data="mansvc_cat:YouTube")],
                [InlineKeyboardButton("📱 Telegram",  callback_data="mansvc_cat:Telegram"),
                 InlineKeyboardButton("🐦 Twitter",   callback_data="mansvc_cat:Twitter")],
                [InlineKeyboardButton("✏️ ផ្សេង (Custom)", callback_data="mansvc_cat:__custom__")],
            ])
            bot.send_message(uid,
                f"📂 <b>ជ្រើស Category</b>\n"
                f"📝 ឈ្មោះ: <b>{label}</b>",
                parse_mode="HTML", reply_markup=cats_kb); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_cat_custom":
            cat = text.strip()
            if not cat:
                bot.send_message(uid, "❌ Category ទទេ!", reply_markup=cancel_kb()); return
            waiting[uid] = {"step": "manual_svc_price", "label": step["label"], "cat": cat}
            bot.send_message(uid,
                f"💰 <b>ដាក់តម្លៃ (USD per 1000)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ឧ: <code>0.50</code> = $0.50 per 1K\n"
                f"ឧ: <code>1.20</code> = $1.20 per 1K",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_price":
            try:
                price = float(text.replace("$","").strip())
                if price <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ តម្លៃខុស! ឧ: <code>0.50</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            waiting[uid] = {**step, "step": "manual_svc_min", "price": price}
            bot.send_message(uid,
                f"🔢 <b>Min Order</b> (ចំនួនអប្បបរមា)\n"
                f"ឧ: <code>100</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_min":
            try:
                mn = int(text.strip())
                if mn <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ ត្រូវជាលេខ! ឧ: <code>100</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            waiting[uid] = {**step, "step": "manual_svc_max", "min": mn}
            bot.send_message(uid,
                f"🔢 <b>Max Order</b> (ចំនួនអតិបរមា)\n"
                f"ឧ: <code>50000</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_max":
            try:
                mx = int(text.strip())
                if mx <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ ត្រូវជាលេខ! ឧ: <code>50000</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            # Save manual service
            label = step["label"]; cat = step["cat"]; price = step["price"]; mn = step["min"]
            slug  = f"manual_{cat.lower().replace(' ','_')}_{int(time.time())}"
            smm_services[slug] = {
                "api_id":       None,          # No API — manual
                "manual":       True,
                "cost_rate":    price,
                "min":          mn,
                "max":          mx,
                "label":        label,
                "category":     cat,
            }
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>Manual Service បានបន្ថែម!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 ឈ្មោះ: <b>{label}</b>\n"
                f"📂 Category: <b>{cat}</b>\n"
                f"💰 តម្លៃ: <b>${price:.2f}/1K</b>\n"
                f"🔢 Min: <b>{mn:,}</b> · Max: <b>{mx:,}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✍️ <i>Service នេះ Admin ត្រូវ process ដោយដៃ</i>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        # ── Admin: Update manual order status ──
        if isinstance(step, dict) and step.get("step") == "manual_order_done" and uid == ADMIN_ID:
            oid      = step.get("oid")
            user_uid = step.get("user_uid")
            o        = smm_orders.get(oid)
            if not o:
                bot.send_message(uid, "❌ Order រកមិនឃើញ", reply_markup=admin_kb())
                waiting.pop(uid, None); return
            note = text.strip()
            smm_orders[oid]["status"]   = "completed"
            smm_orders[oid]["note"]     = note
            _save(SMM_ORD_FILE, smm_orders)
            waiting.pop(uid, None)
            try:
                bot.send_message(int(user_uid),
                    f"✅ <b>Order បានដំណើរការហើយ!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 <code>{oid}</code>\n"
                    f"📊 {o.get('label','?')}\n"
                    f"🔢 ចំនួន: <b>{o.get('qty',0):,}</b>\n"
                    + (f"📝 Note: {note}\n" if note and note != "-" else "") +
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🙏 អរគុណ!",
                    parse_mode="HTML")
            except: pass
            bot.send_message(uid,
                f"✅ <b>Order Completed!</b>\n🆔 <code>{oid}</code>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "✍️ Manual SMM":
            waiting[uid] = {"step": "manual_svc_label"}
            bot.send_message(uid,
                "✍️ <b>បន្ថែម Manual Service</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>Service ប្រភេទនេះ Admin process ដោយដៃ\n"
                "ប្រើសម្រាប់: TikTok Khmer, Reseller, ល.ល</i>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "📝 <b>វាយ ឈ្មោះ Service:</b>\n"
                "ឧ: <code>TikTok Likes Khmer</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "📊 ការបញ្ជា SMM":
            if not smm_orders:
                bot.send_message(uid, "❌ គ្មានការបញ្ជា SMM", reply_markup=admin_kb()); return
            lines = ["<b>📊 ការបញ្ជា SMM (20 ចុងក្រោយ)</b>\n━━━━━━━━━━━━━━━━━━"]
            for oid, o in list(smm_orders.items())[-20:]:
                lines.append(f"🆔 <code>{oid}</code> | 👤 <code>{o['uid']}</code>\n  {o.get('label','?')} | Qty:{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')}")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "⚙️ កំណត់ SMM API":
            cur_url = smm_api.get("url","❌ មិនទាន់ set")
            cur_key = smm_api.get("key","❌ មិនទាន់ set")
            masked = cur_key[:6] + "****" + cur_key[-4:] if len(cur_key) > 10 else cur_key
            kb_api = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ កំណត់ URL + Key", callback_data="smmapi:setup")],
                [InlineKeyboardButton("🔌 សាកល្បងភ្ជាប់",  callback_data="smmapi:test")],
                [InlineKeyboardButton("🗑️ លុប API",         callback_data="smmapi:clear")],
            ])
            bot.send_message(uid,
                f"⚙️ <b>SMM API Config</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"🌐 URL: <code>{cur_url}</code>\n"
                f"🔑 Key: <code>{masked}</code>",
                parse_mode="HTML", reply_markup=kb_api); return

        if text == "➕ បន្ថែម SMM":
            cats_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 TikTok",    callback_data="smmaddcat:TikTok"),
                 InlineKeyboardButton("📘 Facebook",  callback_data="smmaddcat:Facebook")],
                [InlineKeyboardButton("📸 Instagram", callback_data="smmaddcat:Instagram"),
                 InlineKeyboardButton("▶️ YouTube",   callback_data="smmaddcat:YouTube")],
                [InlineKeyboardButton("📱 Telegram",  callback_data="smmaddcat:Telegram"),
                 InlineKeyboardButton("🐦 Twitter",   callback_data="smmaddcat:Twitter")],
                [InlineKeyboardButton("✏️ Custom Category", callback_data="smmaddcat:custom")],
            ])
            bot.send_message(uid,
                "➕ <b>បន្ថែម SMM Service</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Category:",
                parse_mode="HTML", reply_markup=cats_kb); return

        if text == "🗑️ លុប SMM":
            if not smm_services:
                bot.send_message(uid, "❌ គ្មាន SMM Service ទេ", reply_markup=admin_kb()); return
            cats = {}
            for slug, s in smm_services.items():
                cat = s.get("category", "Other")
                cats.setdefault(cat, []).append((slug, s))
            for cat, svcs in cats.items():
                btns = []
                for slug, s in svcs:
                    label = s.get("label", slug)[:30]
                    api_id = s.get("api_id", "?")
                    btns.append([InlineKeyboardButton(
                        f"🗑️ [{api_id}] {label}", callback_data=f"delsvc:{slug}")])
                btns.append([InlineKeyboardButton(
                    f"🗑️ លុបទាំងអស់ {cat}", callback_data=f"delsvc:cat:{cat}")])
                bot.send_message(uid,
                    f"📂 <b>{cat}</b> — {len(svcs)} services\n━━━━━━━━━━━━━━━━━━",
                    parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
            return

        if text == "✏️ កែ SMM":
            if not smm_services:
                bot.send_message(uid, "❌ គ្មាន SMM Service ទេ", reply_markup=admin_kb()); return
            cats = {}
            for slug, s in smm_services.items():
                cat = s.get("category", "Other")
                cats.setdefault(cat, []).append((slug, s))
            for cat, svcs in cats.items():
                btns = []
                for slug, s in svcs:
                    label  = s.get("label", slug)[:35]
                    api_id = s.get("api_id", "?")
                    btns.append([InlineKeyboardButton(
                        f"✏️ [{api_id}] {label}", callback_data=f"editsvc:{slug}")])
                bot.send_message(uid,
                    f"✏️ <b>កែឈ្មោះ — {cat}</b>\n━━━━━━━━━━━━━━━━━━\nចុចដើម្បីកែ:",
                    parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
            return

        if text == "📋 SMM Services":
            bot.send_message(uid, _smm_service_list_text(), parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "💹 ប្រាក់ចំណេញ SMM":
            waiting[uid] = {"step": "smm_set_profit"}
            bot.send_message(uid,
                f"💹 <b>ប្រាក់ចំណេញ SMM: {_smm_profit_pct():.0f}%</b>\nផ្ញើ % ថ្មី:",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "💰 ឆែកលុយ API":
            url = smm_api.get("url",""); key = smm_api.get("key","")
            if not url or not key:
                bot.send_message(uid, "❌ SMM API មិនទាន់ set!", reply_markup=admin_kb()); return
            try:
                r = http.post(url, data={"key": key, "action": "balance"}, timeout=10)
                d = r.json()
                balance  = d.get("balance", d.get("Balance", "?"))
                currency = d.get("currency", d.get("Currency", "USD"))
                bot.send_message(uid,
                    f"💰 <b>SMM API Balance</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"💵 Balance: <b>{balance} {currency}</b>\n"
                    f"🌐 API: <code>{url}</code>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except Exception as e:
                bot.send_message(uid, f"❌ API Error: {e}", reply_markup=admin_kb())
            return

        if text == "💰 កាបូបលុយ":
            lines = ["<b>💰 កាបូបលុយអ្នកប្រើ</b>\n━━━━━━━━━━━━━━━━━━"]
            for u_id, u_info in sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:30]:
                b = wallets.get(u_id, 0)
                name = u_info.get("name","?")
                lines.append(f"👤 <b>{name}</b> <code>{u_id}</code> — <b>${float(b):.2f}</b>")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "💳 ប្រាក់បញ្ញើ":
            pend = [(k, v) for k, v in smm_deps.items() if v.get("status")=="pending"]
            if not pend:
                bot.send_message(uid, "✅ គ្មាន pending deposit", reply_markup=admin_kb()); return
            lines = ["<b>💳 ប្រាក់បញ្ញើ រង់ចាំ</b>\n━━━━━━━━━━━━━━━━━━"]
            for k, v in pend:
                lines.append(f"👤 <code>{v.get('uid','?')}</code> | ${v.get('amount',0):.2f}")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "💸 បន្ថែមប្រាក់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:15]
            btns = []
            for u_id, u_info in users_sorted:
                b    = float(wallets.get(u_id, 0))
                name = (u_info.get("name") or "?")[:18]
                btns.append([InlineKeyboardButton(
                    f"👤 {name}  ${b:.2f}", callback_data=f"useraction:addbal:{u_id}")])
            bot.send_message(uid,
                "💸 <b>បន្ថែមប្រាក់</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសអ្នកប្រើ:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "💔 កាត់ប្រាក់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:15]
            btns = []
            for u_id, u_info in users_sorted:
                b    = float(wallets.get(u_id, 0))
                name = (u_info.get("name") or "?")[:18]
                btns.append([InlineKeyboardButton(
                    f"👤 {name}  ${b:.2f}", callback_data=f"useraction:dedbal:{u_id}")])
            bot.send_message(uid,
                "💔 <b>កាត់ប្រាក់</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសអ្នកប្រើ:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "👥 អ្នកប្រើប្រាស់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)
            if not users_sorted:
                bot.send_message(uid, "❌ គ្មានអ្នកប្រើ", reply_markup=admin_kb()); return
            total = len(users_sorted)
            # Build table - chunk into pages of 50 to avoid Telegram 4096 char limit
            CHUNK = 50
            chunks = [users_sorted[i:i+CHUNK] for i in range(0, total, CHUNK)]
            for page, chunk in enumerate(chunks):
                lines = []
                for i, (u_id, u_info) in enumerate(chunk, start=page*CHUNK+1):
                    b      = float(wallets.get(u_id, 0))
                    name   = (u_info.get("name","?") or "?")[:12]
                    banned = "🚫" if u_info.get("banned") else "✅"
                    lines.append(f"{i:>3}. {banned} <code>{u_id}</code>  {name}  <b>${b:.2f}</b>")
                header = f"👥 <b>អ្នកប្រើ ({page*CHUNK+1}–{page*CHUNK+len(chunk)}/{total})</b>\n━━━━━━━━━━━━━━━━━━\n"
                bot.send_message(uid, header + "\n".join(lines), parse_mode="HTML",
                    reply_markup=admin_kb() if page == len(chunks)-1 else None)
            return

        if text == "📊 ស្ថិតិ":
            total_orders = len(smm_orders)
            total_users  = len(users_db)
            total_rev    = sum(float(o.get("price") or 0) for o in smm_orders.values())
            bot.send_message(uid,
                f"📊 <b>ស្ថិតិ</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"👥 អ្នកប្រើ: <b>{total_users}</b>\n"
                f"📊 SMM Orders: <b>{total_orders}</b>\n"
                f"💰 ចំណូលសរុប: <b>${total_rev:.2f}</b>\n"
                f"📋 Services: <b>{len(smm_services)}</b>\n"
                f"🎟️ Promos: <b>{len(promos)}</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "📢 ផ្សព្វផ្សាយ":
            waiting[uid] = "broadcast_msg"
            bot.send_message(uid, "📢 <b>ផ្សព្វផ្សាយ</b>\nផ្ញើ Message (text/photo/video):",
                             parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "⏱ ល្បឿន Poll":
            cur = smm_poll.get("interval", 5)
            bot.send_message(uid, f"⏱ ល្បឿន Poll (បច្ចុប្បន្ន: {cur}s)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚡ 3s",  callback_data="poll:3"),
                     InlineKeyboardButton("🟢 5s",  callback_data="poll:5"),
                     InlineKeyboardButton("🔵 10s", callback_data="poll:10")],
                    [InlineKeyboardButton("🟡 15s", callback_data="poll:15"),
                     InlineKeyboardButton("🔴 30s", callback_data="poll:30")],
                ])); return

        if text == "🖼️ Welcome Photo":
            cur = "✅ មានរូបហើយ" if welcome_cfg.get("photo_id") else "❌ មិនទាន់មានរូប"
            waiting[uid] = "set_welcome_photo"
            bot.send_message(uid,
                f"🖼️ <b>Welcome Photo</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ស្ថានភាព: <b>{cur}</b>\n\n"
                f"📤 ផ្ញើ រូបភាព ដែលចង់ប្រើ\n"
                f"<i>(រូបនេះនឹងបង្ហាញពេល User ចុច /start)</i>",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if text == "🔔 Notify Channel":
            cid  = notify_cfg.get("channel_id", "") or "មិនទាន់កំណត់"
            ison = "✅ បើក" if notify_cfg.get("enabled") else "❌ បិទ"
            waiting[uid] = "set_notify_channel"
            bot.send_message(uid,
                f"🔔 <b>Notify Channel</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Channel/Group ID: <code>{cid}</code>\n"
                f"ស្ថានភាព: <b>{ison}</b>\n\n"
                f"📝 ផ្ញើ Channel/Group ID ថ្មី\n"
                f"<i>ឧ: <code>-1001234567890</code> ឬ <code>@mychannel</code></i>\n\n"
                f"💡 ដើម្បី <b>បិទ</b> វាយ: <code>off</code>",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if text == "🔄 ធ្វើឱ្យទាន់សម័យ":
            bot.send_message(uid, "✅ បានធ្វើឱ្យទាន់សម័យ!", reply_markup=admin_kb()); return

        if text.startswith("━━━"):
            bot.send_message(uid, "👇 ជ្រើស menu ខាងក្រោម:", reply_markup=admin_kb()); return

        bot.send_message(uid, "❓ ប្រើប៊ូតុង Menu ខាងក្រោម។", reply_markup=admin_kb()); return

    # ════════════════════════════════════════
    #  USER SECTION
    # ════════════════════════════════════════

    # ── Custom amount step ──
    if isinstance(step, dict) and step.get("step") == "dep_custom_amt":
        try:
            amount = float(text.replace("$","").replace(",","").strip())
            if amount <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>3</code> ឬ <code>7.50</code>",
                             parse_mode="HTML", reply_markup=cancel_kb()); return
        waiting.pop(uid, None)
        _process_deposit(uid, uid_str, amount, None)
        return

    # Admin confirm deposit — enter amount
    if isinstance(step, dict) and step.get("step") == "adm_confirm_dep" and uid == ADMIN_ID:
        dep_id = step.get("dep_id")
        dep    = smm_deps.get(dep_id)
        if not dep:
            bot.send_message(uid, "❌ Deposit រកមិនឃើញ", reply_markup=admin_kb())
            waiting.pop(uid, None); return
        try:
            paid = float(text.replace("$","").strip())
            if paid <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>5.00</code>", parse_mode="HTML"); return
        waiting.pop(uid, None)
        user_uid = int(dep["uid"])
        # Credit balance manually
        bonus = float(dep.get("bonus") or 0)
        total = round(paid + bonus, 2)
        add_bal(user_uid, total)
        smm_deps[dep_id]["status"] = "confirmed"
        smm_deps[dep_id]["amount"] = paid
        _save(SMM_DEP_FILE, smm_deps)
        new_b = bal(user_uid)
        msg = (f"✅ <b>ដាក់លុយបានជោគជ័យ!</b>\n"
               f"━━━━━━━━━━━━━━━━━━\n"
               f"💰 បញ្ញើ: <b>${paid:.2f}</b>")
        if bonus > 0:
            msg += f"\n🎟️ Promo Bonus: <b>+${bonus:.2f}</b>"
        msg += f"\n💳 Balance: <b>${new_b:.2f}</b>"
        try: bot.send_message(user_uid, msg, parse_mode="HTML", reply_markup=main_kb(user_uid))
        except: pass
        bot.send_message(uid,
            f"✅ <b>Confirmed!</b>\n👤 <code>{dep['uid']}</code>\n💰 <b>${paid:.2f}</b>",
            parse_mode="HTML", reply_markup=admin_kb())
        return

    # SMM link step
    if isinstance(step, dict) and step.get("step") == "smm_link":
        slug  = step["slug"]
        qty   = step["qty"]
        price = step["price"]
        waiting.pop(uid, None)
        link  = text.strip()
        if bal(uid) < price:
            bot.send_message(uid,
                f"❌ Balance មិនគ្រប់!\n💳 ${bal(uid):.2f} | Need: ${price:.2f}",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        s = smm_services.get(slug)
        ded_bal(uid, price)
        key = smm_api.get("key",""); api_url = smm_api.get("url","")
        res = None
        if key and api_url and not s.get("manual"):
            res = _smm_api_post({"key":key,"action":"add","service":s["api_id"],"link":link,"quantity":qty})
        api_oid = str(res.get("order","")) if res else ""
        oid = _make_order_id()
        smm_orders[oid] = {
            "uid":uid_str,"slug":slug,"label":s.get("label",slug),
            "qty":qty,"price":price,"link":link,"api_order_id":api_oid,
            "status":"pending","ts":int(time.time())
        }
        _save(SMM_ORD_FILE, smm_orders)

        is_tiktok_promote = s.get("flat_price") and "tiktok" in slug.lower()
        is_manual = s.get("manual", False)

        if is_tiktok_promote:
            bot.send_message(uid,
                f"✅ <b>Order TikTok Promote បានជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"🎵 {s.get('label',slug)}\n"
                f"💰 <b>${price:.2f}</b>\n"
                f"🔗 <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⏳ <b>ចាំ Admin ដំណើរការ 5-15 នាទី</b>\n\n"
                f"📱 <b>រំឭក!</b> ចូល TikTok:\n"
                f"Inbox → System notifications\n"
                f"→ Promote Assistant → <b>Respond</b>\n"
                f"→ Authorize → <b>Confirm</b> ✅\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${bal(uid):.2f}</b>",
                parse_mode="HTML", reply_markup=main_kb(uid))
        else:
            bot.send_message(uid,
                f"✅ <b>បញ្ជា SMM បានជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"📊 {s.get('label',slug)}\n"
                f"🔢 ចំនួន: <b>{qty:,}</b> | 💰 <b>${price:.4f}</b>\n"
                f"🔗 <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${bal(uid):.2f}</b>",
                parse_mode="HTML", reply_markup=main_kb(uid))

        # ── Notify Admin ──
        if is_tiktok_promote:
            admin_msg = (
                f"🎵 <b>TikTok Promote Order!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 <code>{uid_str}</code>\n"
                f"💰 <b>${price:.2f}</b>\n"
                f"🔗 <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📋 <b>Admin Steps:</b>\n"
                f"1️⃣ ចូល TikTok → video → Promote\n"
                f"2️⃣ ជ្រើស budget → ផ្ញើ invite\n"
                f"3️⃣ User នឹង Accept → ចុច ✅ Done"
            )
            kb_adm = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Done",   callback_data=f"manord:done:{oid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"manord:reject:{oid}"),
            ]])
            try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=kb_adm)
            except: pass
        elif is_manual:
            admin_msg = (
                f"✍️ <b>Manual SMM Order</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 <code>{uid_str}</code>\n"
                f"📊 {s.get('label',slug)}\n"
                f"🔢 {qty:,} | 💰 ${price:.4f}\n"
                f"🔗 <code>{link}</code>"
            )
            kb_adm = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Done",   callback_data=f"manord:done:{oid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"manord:reject:{oid}"),
            ]])
            try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=kb_adm)
            except: pass
        else:
            try: bot.send_message(ADMIN_ID,
                f"📊 <b>SMM Order</b>\n👤 <code>{uid_str}</code> | {s.get('label',slug)} | {qty:,} | ${price:.4f}",
                parse_mode="HTML")
            except: pass
        return

    # Track order
    if step == "track_order":
        oid = text.strip().upper()
        o   = smm_orders.get(oid)
        waiting.pop(uid, None)
        if not o or o.get("uid") != uid_str:
            bot.send_message(uid, "❌ Order រកមិនឃើញ!", reply_markup=main_kb(uid)); return
        bot.send_message(uid,
            f"📊 <b>SMM Order: <code>{oid}</code></b>\n"
            f"{o.get('label','?')}\n"
            f"🔢 ចំនួន: {o.get('qty','?'):,} | 💰 ${o.get('price',0):.4f}\n"
            f"🔗 <code>{o.get('link','?')}</code>\n"
            f"📌 API: <code>{o.get('api_order_id','?')}</code>\n"
            f"✅ ស្ថានភាព: <b>{o.get('status','?')}</b>",
            parse_mode="HTML", reply_markup=main_kb(uid)); return

    # ── Main menu buttons ──
    if text in ("📊 SMM Services", "🛒 បញ្ជាទិញសេវា", "🛒 Order Service"):
        if not smm_services:
            bot.send_message(uid,
                "❌ គ្មាន SMM Service ទេ\n(Admin ចូល ⚙️ កំណត់ SMM API ដើម្បី import)",
                reply_markup=main_kb(uid)); return
        bot.send_message(uid,
            "📊 <b>SMM Services</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Platform:",
            parse_mode="HTML", reply_markup=smm_cat_kb()); return

    if text in ("💰 ដាក់ប្រាក់", "💰 Top Up", "💸 បញ្ចូលលុយ", "💸 Top Up"):
        b = bal(uid)
        waiting.pop(uid, None)
        bot.send_message(uid,
            f"💸 <b>{'ដាក់លុយ' if lang=='kh' else 'Top Up'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 Balance: <b>${b:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{'ជ្រើស ចំនួន:' if lang=='kh' else 'Choose Amount:'}",
            parse_mode="HTML", reply_markup=deposit_amt_kb(uid)); return

    if text in ("📦 ការបញ្ជា", "📦 Orders", "📋 ប្រវត្តិការបញ្ជាទិញ", "📋 Order History"):
        my_orders = {oid: o for oid, o in smm_orders.items() if o.get("uid") == uid_str}
        if not my_orders:
            bot.send_message(uid,
                "📦 <b>ការបញ្ជា</b>\n\n❌ គ្មាន Order ទេ!",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        lines = ["📦 <b>ការបញ្ជា SMM</b>\n━━━━━━━━━━━━━━━━━━"]
        for oid, o in sorted(my_orders.items(), key=lambda x: x[1].get("ts",0), reverse=True)[:10]:
            lines.append(f"📊 <code>{oid}</code> — {o.get('label','?')} x{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')}")
        bot.send_message(uid, "\n".join(lines), parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("📋 ប្រវត្តិ", "📋 History"):
        my_orders = {oid: o for oid, o in smm_orders.items() if o.get("uid") == uid_str}
        if not my_orders:
            bot.send_message(uid,
                "📋 <b>ប្រវត្តិ</b>\n\n❌ គ្មាន Order ទេ!",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        lines = ["📋 <b>ប្រវត្តិ</b>\n━━━━━━━━━━━━━━━━━━"]
        for oid, o in sorted(my_orders.items(), key=lambda x: x[1].get("ts",0), reverse=True)[:15]:
            dt = datetime.datetime.fromtimestamp(o.get("ts",0)).strftime("%d/%m %H:%M")
            lines.append(f"📊 <code>{oid}</code> | {o.get('label','?')} x{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')} | {dt}")
        bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("👜 កាបូបលុយ", "👜 Wallet", "👤 តំណាំការគណនី", "👤 គណនី", "👤 My Account"):
        waiting.pop(uid, None)
        b = bal(uid)
        my_deps = [(k, v) for k, v in smm_deps.items() if v.get("uid") == uid_str]
        confirmed = sum(float(v.get("amount") or 0) for _, v in my_deps if v.get("status") == "confirmed")
        pending   = sum(float(v.get("amount") or 0) for _, v in my_deps if v.get("status") == "pending")
        total_orders = sum(1 for o in smm_orders.values() if o.get("uid") == uid_str)
        u = users_db.get(uid_str, {})
        name = u.get("name", "") or ""
        uname = f"@{u['username']}" if u.get("username") else ""
        if lang == "kh":
            msg = (
                f"👤 <b>គណនីរបស់ខ្ញុំ</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🙍 ឈ្មោះ: <b>{name}</b>  {uname}\n"
                f"🆔 ID: <code>{uid_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${b:.2f}</b>\n"
                f"✅ សរុបដាក់: <b>${confirmed:.2f}</b>\n"
                f"⏳ រង់ចាំ: <b>${pending:.2f}</b>\n"
                f"📦 Orders: <b>{total_orders}</b>"
            )
        else:
            msg = (
                f"👤 <b>My Account</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🙍 Name: <b>{name}</b>  {uname}\n"
                f"🆔 ID: <code>{uid_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${b:.2f}</b>\n"
                f"✅ Total deposited: <b>${confirmed:.2f}</b>\n"
                f"⏳ Pending: <b>${pending:.2f}</b>\n"
                f"📦 Orders: <b>{total_orders}</b>"
            )
        bot.send_message(uid, msg, parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("Track 🔍", "🔍 Track Order", "🔍 តាមដានការបញ្ជាទិញ"):
        bot.send_message(uid,
            "🔍 <b>តាមដាន Order</b>\nផ្ញើ Order ID (ឧ: KZ12345):",
            parse_mode="HTML", reply_markup=cancel_kb())
        waiting[uid] = "track_order"; return

    if text in ("💬 Support", "💬 ជំនួយ"):
        bot.send_message(uid, t(uid, "support_msg"), parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("💡 របៀបប្រើប្រាស់", "💡 How to Use"):
        bot.send_message(uid, t(uid, "how_to_use"), parse_mode="HTML", reply_markup=main_kb(uid)); return

    bot.send_message(uid, t(uid, "fallback"), reply_markup=main_kb(uid))

# ═══════════════════════════════════════════════════════════
#  FLASK CONTROL SERVER
# ═══════════════════════════════════════════════════════════
flask_app = Flask(__name__)

def _check_key():
    key = flask_request.args.get("key") or (flask_request.get_json(silent=True) or {}).get("key")
    return key == CONTROL_KEY

@flask_app.route("/health")
def health():
    return jsonify({"status": "running", "bot": "Kairozen SMM"})

@flask_app.route("/status")
def status():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({
        "status": "running",
        "users": len(users_db),
        "smm_orders": len(smm_orders),
        "smm_services": len(smm_services),
        "wallets": len(wallets),
    })

@flask_app.route("/shutdown", methods=["GET", "POST"])
def shutdown():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    logger.warning("🛑 Shutdown requested!")
    try:
        bot.send_message(ADMIN_ID, "🛑 <b>Bot កំពុងបិទ...</b>", parse_mode="HTML")
        time.sleep(1)
    except: pass
    def _stop():
        time.sleep(0.5)
        bot.stop_polling()
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({"status": "shutting_down"})

@flask_app.route("/restart", methods=["GET", "POST"])
def restart():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    logger.warning("🔄 Restart requested!")
    try:
        bot.send_message(ADMIN_ID, "🔄 <b>Bot កំពុង Restart...</b>", parse_mode="HTML")
        time.sleep(1)
    except: pass
    def _restart():
        time.sleep(0.5)
        bot.stop_polling()
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({"status": "restarting"})

@flask_app.route("/broadcast_web", methods=["POST"])
def broadcast_web():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    data = flask_request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    sent = failed = 0
    for u_id in list(users_db.keys()):
        try:
            bot.send_message(int(u_id), text, parse_mode="HTML")
            sent += 1
        except: failed += 1
        time.sleep(0.05)
    return jsonify({"sent": sent, "failed": failed})

def run_flask():
    logger.info("🌐 Control Server running on port 5056")
    flask_app.run(host="0.0.0.0", port=5056, debug=False, use_reloader=False)

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("🚀 Kairozen SMM Bot កំពុងចាប់ផ្ដើម...")
    logger.info(f"🔑 Control Key: {CONTROL_KEY}  ← ដូរនៅ CONTROL_KEY!")
    logger.info(f"📊 Services loaded: {len(smm_services)}")
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=15)
