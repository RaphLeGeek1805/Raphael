from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    platform: str
    username: str
    display_name: str
    profile_url: str
    avatar_url: str | None = None
    bio: str | None = None
    confidence: float = 0.5
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "platform": self.platform,
            "username": self.username,
            "display_name": self.display_name,
            "profile_url": self.profile_url,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "confidence": self.confidence,
            "extra": self.extra,
        }


class BaseSearcher(ABC):
    platform_name: str = ""
    platform_icon: str = ""

    @abstractmethod
    def search_by_name(self, first_name: str, last_name: str) -> list[SearchResult]:
        ...

    def search_by_image(self, image_path: str) -> list[SearchResult]:
        return []
