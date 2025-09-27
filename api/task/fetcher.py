import os
import requests
from datetime import datetime, timezone
from typing import Tuple, List, Dict, Any

from ..storage import load_json, save_json, logger
from ..services import API_HOST, API_KEY

HEADERS = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": API_KEY,
}

BASE_DIR = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
DATA_DIR = os.path.join(BASE_DIR, "data")
REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")

os.makedirs(REVIEWS_DIR, exist_ok=True)


def _reviews_path(filename: str) -> str:
    return os.path.join(REVIEWS_DIR, filename)


# helper to parse timestamps like "2025-09-27T07:47:20.000Z"
def parse_iso_z(dt_str: str) -> datetime:
    if not dt_str:
        return None
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1]
    try:
        return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _fetch_page(domain: str, page: int) -> Dict[str, Any]:
    url = f"https://{API_HOST}/company-reviews"
    params = {"company_domain": domain, "page": page}
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _read_meta(domain: str) -> Dict[str, Any]:
    meta = load_json(_reviews_path(f"meta_{domain}.json"))
    if isinstance(meta, list):
        meta = {}
    return meta or {}


def _write_meta(domain: str, meta: Dict[str, Any]):
    save_json(_reviews_path(f"meta_{domain}.json"), meta)


def _read_reviews(domain: str) -> List[Dict[str, Any]]:
    reviews = load_json(_reviews_path(f"reviews_{domain}.json"))
    return reviews or []


def _write_reviews(domain: str, reviews: List[Dict[str, Any]]):
    save_json(_reviews_path(f"reviews_{domain}.json"), reviews)


def _newest_review_cursor(reviews: List[Dict[str, Any]]) -> Tuple[str, str]:
    newest_dt = None
    newest_id = None
    for r in reviews:
        rt = r.get("review_time")
        rid = r.get("review_id") or r.get("reviewId")
        dt = parse_iso_z(rt)
        if dt is None:
            continue
        if newest_dt is None or dt > newest_dt or (dt == newest_dt and (rid or "") > (newest_id or "")):
            newest_dt = dt
            newest_id = rid
    return (newest_dt.isoformat() if newest_dt else None, newest_id)


def fetch_all_pages_and_save(domain: str):
    """Initial sync: fetch all pages and save the full set (deduped, sorted newest-first)."""
    all_reviews = []
    page = 1
    while True:
        try:
            payload = _fetch_page(domain, page)
        except Exception as e:
            logger(f"Initial fetch error for {domain} page {page}: {e}")
            break

        reviews = payload.get("data", {}).get("reviews") or payload.get("reviews") or []
        if not reviews:
            break

        all_reviews.extend(reviews)
        page += 1

    if not all_reviews:
        logger(f"No reviews found for {domain} on initial fetch. Skipping save.")
        return

    # dedupe by review_id
    seen = {}
    deduped = []
    for r in all_reviews:
        rid = r.get("review_id")
        if not rid:
            rid = f'noid-{r.get("review_time")}-{hash(r.get("review_text", ""))}'
            r["review_id"] = rid
        if rid in seen:
            continue
        seen[rid] = True
        deduped.append(r)

    # sort newest-first by time, then by ID for tie-breaking
    deduped.sort(
        key=lambda rr: (
            parse_iso_z(rr.get("review_time")) or datetime.min.replace(tzinfo=timezone.utc),
            rr.get("review_id", "")
        ),
        reverse=True,
    )

    _write_reviews(domain, deduped)

    # update meta with newest cursor
    newest_time, newest_id = _newest_review_cursor(deduped)
    meta = {"last_seen_time": newest_time, "last_seen_id": newest_id}
    _write_meta(domain, meta)
    logger(f"Initial sync for {domain}: {len(deduped)} reviews saved; newest={newest_time},{newest_id}")


def fetch_incremental(domain: str):
    """Incremental fetch: fetch pages until we find a page with no new reviews."""
    meta = _read_meta(domain)
    last_seen_time = meta.get("last_seen_time")
    last_seen_id = meta.get("last_seen_id")
    last_seen_dt = parse_iso_z(last_seen_time) if last_seen_time else None

    page = 1
    new_reviews = []
    found_old_review = False

    while not found_old_review:
        try:
            payload = _fetch_page(domain, page)
        except Exception as e:
            logger(f"Error fetching {domain} page {page}: {e}")
            break

        reviews = payload.get("data", {}).get("reviews") or payload.get("reviews") or []
        if not reviews:
            break

        page_has_new_reviews = False
        
        for r in reviews:
            rt = r.get("review_time")
            rid = r.get("review_id")
            if not rt:
                continue
            r_dt = parse_iso_z(rt)
            if r_dt is None:
                continue

            # Check if this review is newer than our last seen
            is_new = False
            if last_seen_dt is None:
                is_new = True
            else:
                if r_dt > last_seen_dt:
                    is_new = True
                elif r_dt == last_seen_dt and rid != last_seen_id:
                    # Same timestamp but different ID - could be newer or older
                    # Since we don't know the ordering of IDs, we need to be careful
                    # Let's assume any review with same timestamp but different ID is potentially new
                    is_new = True

            if is_new:
                new_reviews.append(r)
                page_has_new_reviews = True
            else:
                # Found a review that's not new - but don't stop yet
                # Only stop if we find a review that's definitely older
                if r_dt < last_seen_dt:
                    found_old_review = True
                # If same timestamp but same ID, we've found our stopping point
                elif r_dt == last_seen_dt and rid == last_seen_id:
                    found_old_review = True

        # If this page had no new reviews at all, we can stop
        if not page_has_new_reviews:
            found_old_review = True

        page += 1

    if not new_reviews:
        logger(f"No new reviews for {domain}")
        return

    stored = _read_reviews(domain)
    stored_ids = {x.get("review_id") for x in stored if x.get("review_id")}
    dedup_new = [r for r in new_reviews if r.get("review_id") not in stored_ids]

    if not dedup_new:
        logger(f"No new unique reviews to add for {domain} after dedupe")
        return

    # Insert new reviews at the beginning to maintain newest-first order
    combined = dedup_new + stored
    
    # Re-sort to be safe (in case of same timestamps)
    combined.sort(
        key=lambda rr: (
            parse_iso_z(rr.get("review_time")) or datetime.min.replace(tzinfo=timezone.utc),
            rr.get("review_id", "")
        ),
        reverse=True,
    )
    
    _write_reviews(domain, combined)

    newest_time, newest_id = _newest_review_cursor(combined)
    meta = {"last_seen_time": newest_time, "last_seen_id": newest_id}
    _write_meta(domain, meta)

    logger(f"Added {len(dedup_new)} new reviews for {domain}; newest={newest_time},{newest_id}")


def fetch_incremental_simple(domain: str, pages_to_fetch: int = 3):
    """Simpler alternative: always fetch first N pages and dedupe (more reliable but less efficient)."""
    new_reviews = []
    
    for page in range(1, pages_to_fetch + 1):
        try:
            payload = _fetch_page(domain, page)
            reviews = payload.get("data", {}).get("reviews") or payload.get("reviews") or []
            new_reviews.extend(reviews)
        except Exception as e:
            logger(f"Error fetching {domain} page {page}: {e}")
            break

    if not new_reviews:
        logger(f"No reviews fetched for {domain}")
        return

    stored = _read_reviews(domain)
    stored_ids = {x.get("review_id") for x in stored if x.get("review_id")}
    dedup_new = [r for r in new_reviews if r.get("review_id") not in stored_ids]

    if not dedup_new:
        logger(f"No new unique reviews to add for {domain} after dedupe")
        return

    # Insert new reviews at the beginning
    combined = dedup_new + stored
    
    # Sort to ensure proper ordering
    combined.sort(
        key=lambda rr: (
            parse_iso_z(rr.get("review_time")) or datetime.min.replace(tzinfo=timezone.utc),
            rr.get("review_id", "")
        ),
        reverse=True,
    )
    
    _write_reviews(domain, combined)

    newest_time, newest_id = _newest_review_cursor(combined)
    meta = {"last_seen_time": newest_time, "last_seen_id": newest_id}
    _write_meta(domain, meta)

    logger(f"Added {len(dedup_new)} new reviews for {domain} using simple method; newest={newest_time},{newest_id}")


def fetch_and_store_reviews_for_domain(domain: str, use_simple_method: bool = False):
    """Public function to fetch reviews for a single domain.
    
    Args:
        domain: The domain to fetch reviews for
        use_simple_method: If True, use the simpler but less efficient method that fetches
                          fixed number of pages. Useful for debugging complex pagination issues.
    """
    try:
        meta = _read_meta(domain)
        reviews = _read_reviews(domain)

        if not meta.get("last_seen_time") or not reviews:
            logger(f"Performing initial sync for {domain}")
            fetch_all_pages_and_save(domain)
        else:
            if use_simple_method:
                logger(f"Using simple incremental method for {domain}")
                fetch_incremental_simple(domain)
            else:
                logger(f"Using smart incremental method for {domain}")
                fetch_incremental(domain)
    except Exception as e:
        logger(f"Unexpected error processing {domain}: {e}")