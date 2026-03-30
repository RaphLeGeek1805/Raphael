import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, jsonify, render_template, request

import config
from searchers.base import SearchResult
from searchers.github_searcher import GitHubSearcher
from searchers.twitter_searcher import TwitterSearcher
from searchers.linkedin_searcher import LinkedInSearcher
from searchers.instagram_searcher import InstagramSearcher
from searchers.facebook_searcher import FacebookSearcher
from searchers.image_searcher import ImageSearcher
from utils.cache import cache
from utils.face import prepare_search_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

NAME_SEARCHERS = [
    GitHubSearcher(),
    TwitterSearcher(),
    LinkedInSearcher(),
    InstagramSearcher(),
    FacebookSearcher(),
]

IMAGE_SEARCHER = ImageSearcher()

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def run_searcher(searcher, method: str, *args) -> tuple[str, str, list[SearchResult]]:
    """Run a searcher and return (platform_name, status, results)."""
    try:
        fn = getattr(searcher, method)
        results = fn(*args)
        logging.info(f"{searcher.platform_name}: {len(results)} result(s)")
        return searcher.platform_name, "ok", results
    except Exception as e:
        logging.warning(f"{searcher.platform_name} failed: {e}")
        return searcher.platform_name, f"error: {e}", []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search/name", methods=["POST"])
def search_by_name():
    data = request.get_json()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    selected = data.get("platforms") or []

    if not first_name and not last_name:
        return jsonify({"error": "Veuillez entrer un nom ou un prénom."}), 400

    query = f"{first_name} {last_name}".strip()

    # Check cache
    cached = cache.get("name", query)
    if cached is not None:
        return jsonify(cached)

    searchers = NAME_SEARCHERS
    if selected:
        searchers = [s for s in NAME_SEARCHERS if s.platform_name.lower().replace(" / ", "").replace(" ", "") in
                      [p.lower().replace(" / ", "").replace(" ", "") for p in selected]]
        if not searchers:
            searchers = NAME_SEARCHERS

    all_results = []
    platform_status = {}

    with ThreadPoolExecutor(max_workers=len(searchers)) as pool:
        futures = {
            pool.submit(run_searcher, s, "search_by_name", first_name or last_name, last_name or first_name): s
            for s in searchers
        }
        for future in as_completed(futures, timeout=config.SEARCH_TIMEOUT + 5):
            try:
                platform, status, results = future.result()
                platform_status[platform] = status
                all_results.extend(results)
            except Exception as e:
                s = futures[future]
                platform_status[s.platform_name] = f"timeout: {e}"

    response = {
        "query": query,
        "total": len(all_results),
        "results": [r.to_dict() for r in all_results],
        "platform_status": platform_status,
    }

    cache.set("name", query, response)
    return jsonify(response)


@app.route("/search/photo", methods=["POST"])
def search_by_photo():
    if "photo" not in request.files:
        return jsonify({"error": "Aucune photo envoyée."}), 400

    file = request.files["photo"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Format de fichier non supporté. Utilisez JPG, PNG, GIF ou WEBP."}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(config.UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        search_image = prepare_search_image(filepath)
        results = IMAGE_SEARCHER.search_by_image(search_image)

        # Clean up temp face crop if different from original
        if search_image != filepath and os.path.exists(search_image):
            os.unlink(search_image)

        response = {
            "query": "photo",
            "total": len(results),
            "results": [r.to_dict() for r in results],
            "platform_status": {"Reverse Image": "ok" if results else "no_results"},
        }
        return jsonify(response)
    finally:
        if os.path.exists(filepath):
            os.unlink(filepath)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
