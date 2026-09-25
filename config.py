"""
Configuration for the Bargain Hunter bot.
Adjust these settings to customise what deals you're looking for.
"""

# --- Products to track ---
# One query is one product. Every keyword must appear, and a 1-2 digit model
# number has to sit next to another keyword (so "2 year warranty" does not match).
_GARDEN_PARTS = [
    "blade", "cover", "part", "catch", "catcher", "oil", "spark plug", "filter",
]

SEARCH_QUERIES = [
    {
        "keywords": ["beats", "powerbeats", "pro", "2"],
        "exclude": ["case", "cover", "tip", "cable"],
    },
    {
        "keywords": ["shokz", "openfit", "2"],
        "exclude": ["case", "cover"],
    },
    {
        "keywords": ["bose", "ultra", "open", "earbuds"],
        "exclude": ["case", "cover"],
    },
    {
        "keywords": ["airpods", "pro"],
        "exclude": ["case", "cover", "tip"],
    },
    {
        "keywords": ["lawn", "mower"],
        "exclude": _GARDEN_PARTS,
    },
    {
        "keywords": ["leaf", "blower"],
        "exclude": ["snow", *_GARDEN_PARTS],
    },
    {
        "keywords": ["line", "trimmer"],
        "exclude": _GARDEN_PARTS,
    },
    {
        "keywords": ["whipper", "snipper"],
        "exclude": _GARDEN_PARTS,
    },
]

# --- Global Excludes ---
# These keywords will be excluded globally from all search query matching
# to prevent refurbished, used, replica, or single replacement parts alerts.
GLOBAL_EXCLUDES = [
    "refurbished", "refurb", "renewed", "used", "pre-owned", "grade a", "grade b",
    "ex-demo", "second hand", "replica", "copy", "clone", "compatible", "fake",
    "non-genuine", "replacement", "left earbud", "right earbud", "single earbud",
    "single airpod", "earbud only", "charging case only", "replacement case",
    "left only", "right only",
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
# One Shopping search per query per run. Eight queries, twice a day, is about
# 480 calls a month. Do not add a search per retailer; one Shopping call
# already returns every retailer.
SERPER_ENABLED = True           # Set False to disable Serper entirely and rely only on OzBargain

# --- OzBargain RSS ---
OZBARGAIN_RSS_URL = "https://www.ozbargain.com.au/deals/feed"
OZBARGAIN_MAX_ITEMS = 50

# --- OzBargain Freebies ---
# Freebies are items in the main feed, not a separate feed.
# '$0 C&C' and 'free shipping' are delivery terms, not freebies.
# Matching the watchlist keeps a free game or a free lunch out of Slack.
OZBARGAIN_FREEBIES_ENABLED = True
OZBARGAIN_FREEBIES_MATCH_WATCHLIST = True
OZBARGAIN_FREEBIES_MIN_VOTES = 20   # Higher bar, so a handful of upvotes is not enough

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
