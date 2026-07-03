"""
Configuration for the Bargain Hunter bot.
Adjust these settings to customise what deals you're looking for.
"""

# --- Products to track ---
# These are the specific products you want to monitor.
# Be specific enough to avoid false matches (e.g. include model number/version).
SEARCH_QUERIES = [
    {
        "keywords": ["beats", "powerbeats", "pro", "2"],
        "exclude": ["case", "cover", "tip", "cable"]
    },
    {
        "keywords": ["shokz", "openfit", "2"],
        "exclude": ["case", "cover"]
    },
    {
        "keywords": ["bose", "ultra", "open", "earbuds"],
        "exclude": ["case", "cover"]
    },
    {
        "keywords": ["airpods", "pro"],
        "exclude": ["case", "cover", "tip"]
    },
    {
        "keywords": ["lawn", "mower"],
        "exclude": ["blade", "cover", "part", "catch", "oil", "spark plug", "filter"]
    },
    {
        "keywords": ["lawn", "mower", "blower", "trimmer"],
        "exclude": ["blade", "cover", "part", "catch", "oil", "spark plug", "filter"]
    }
]

# --- Global Excludes ---
# These keywords will be excluded globally from all search query matching
# to prevent refurbished, used, replica, or single replacement parts alerts.
GLOBAL_EXCLUDES = [
    "refurbished", "refurb", "renewed", "used", "pre-owned", "grade a", "grade b", 
    "ex-demo", "second hand", "replica", "copy", "clone", "compatible", "fake", 
    "non-genuine", "replacement", "left earbud", "right earbud", "single", "earbud only", 
    "charging case only", "replacement case", "left only", "right only"
]

# Verify price by crawling the direct retailer landing page before alerting
VERIFY_PRICES_LIVE = True

# --- Deal Thresholds ---
# OzBargain: community votes are the signal — no discount % required
MIN_OZBARGAIN_VOTES = 10        # Minimum upvotes to surface an OzBargain deal

# Retailers: only alert on a heavy discount — these products rarely go on sale
# so 40%+ is the bar worth getting out of bed for
MIN_DISCOUNT_PERCENT = 40

# LLM quality gate — deals scoring below this are not sent to Slack
LLM_MIN_SCORE = 6

# --- OzBargain Trust Settings ---
# If something made it onto OzBargain with votes, alert immediately — the
# community has already validated it. OzBargain deals bypass the price drop
# threshold and go straight to LLM scoring with a trust boost.
OZBARGAIN_TRUSTED = True
OZBARGAIN_SCORE_BOOST = 2       # Added to LLM score for community-validated deals
OZBARGAIN_MIN_VOTES_TRUSTED = 5 # Votes needed for the trust boost

# --- Serper API Budget ---
# Free tier = 2500 searches/month.
# We use 1 Shopping search per product per run = len(SEARCH_QUERIES) × 2 runs/day.
# With 3 products that's ~180 calls/month — well within the free limit.
# Do NOT add per-retailer searches — one Shopping call returns all retailers at once.
SERPER_ENABLED = True           # Set False to disable Serper entirely and rely only on OzBargain

# --- OzBargain RSS ---
OZBARGAIN_RSS_URL = "https://www.ozbargain.com.au/deals/feed"
OZBARGAIN_MAX_ITEMS = 50

# --- OzBargain Freebies ---
# Freebies are in the main deals feed tagged as "freebie" — there's no separate feed.
# We detect them by looking for free/freebie signals in the title/description.
OZBARGAIN_FREEBIES_ENABLED = True
OZBARGAIN_FREEBIES_MIN_VOTES = 20   # Higher bar — only well-upvoted freebies (avoids spam)

# --- Cache ---
CACHE_FILE = "data/deals_cache.json"
CACHE_MAX_AGE_DAYS = 7

# --- Slack ---
SLACK_CHANNEL_NAME = "#bargains"
MAX_SLACK_ALERTS_PER_RUN = 10
# Who to notify when a deal is found.
# Options:
#   "@here"        — notifies active members in the channel (recommended)
#   "@channel"     — notifies ALL members (noisy)
#   "@your.name"   — notifies just you (replace with your Slack display name)
#   ""             — no mention, message just appears silently in channel
SLACK_NOTIFY_USER = "@channel"

# --- LLM ---
LLM_MODEL = "gemini-2.5-flash"  # Free tier — matches google-genai SDK model names
LLM_MAX_DEALS_PER_BATCH = 5
