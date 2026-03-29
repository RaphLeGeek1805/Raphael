import os

# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

# API Keys (optional, improve results when set)
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Search settings
SEARCH_TIMEOUT = 15  # seconds per platform
MAX_RESULTS_PER_PLATFORM = 10

# Rate limiting (requests per minute)
RATE_LIMITS = {
    "github.com": 10,
    "google.com": 5,
    "yandex.com": 5,
    "instagram.com": 5,
    "nitter": 5,
}
