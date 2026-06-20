from abc import ABC, abstractmethod
from typing import List
from src.models import Deal

class DealFetcher(ABC):
    """Abstract base class for all deal fetchers."""

    @abstractmethod
    def fetch(self) -> List[Deal]:
        """Fetch deals and return a list of Deal objects."""
        pass
