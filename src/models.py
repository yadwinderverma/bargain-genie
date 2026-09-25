from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Deal(BaseModel):
    id: str
    source: str
    title: str
    url: str
    description: str = ""
    # Direct product page when `url` is a discussion or search result.
    merchant_url: str = ""
    original_price: Optional[float] = None
    sale_price: Optional[float] = None
    discount_pct: Optional[float] = None
    votes: int = 0
    community_validated: bool = False

    # Optional fields for freebies
    is_freebie: bool = False
    duration_note: str = ""

    # Optional fields for retailers
    price_beat_retailer: bool = False
    is_cheapest: bool = False
    market_low: Optional[float] = None
    market_median: Optional[float] = None
    retailer_count: int = 0
    deal_reason: str = ""

    # Dates
    published: str = ""
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # LLM analysis. analysis_error means the score is not a real judgement
    # and the deal should be tried again on the next run.
    llm_score: int = 0
    llm_reason: str = ""
    llm_category: str = "General"
    llm_genuine: bool = True
    analysis_error: bool = False
