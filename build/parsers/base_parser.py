from abc import ABC, abstractmethod


class BaseParser(ABC):
    @abstractmethod
    def parse_characters(self, source):
        """Parse a roster from the given source (a URL or pre-loaded HTML).

        Returns a dict mapping character name -> image URL."""
        pass
