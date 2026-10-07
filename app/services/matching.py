from difflib import SequenceMatcher
from pathlib import Path

from flask import current_app
from sqlalchemy import or_

from app.extensions import db
from app.models.item import Item
from app.models.match import ItemMatch
from app.models.notification import Notification
from app.services.image_similarity import image_similarity
from app.services.image_service import local_image_path


MATCH_THRESHOLD = 60


def _text_similarity(first, second):
    first = (first or "").strip().casefold()
    second = (second or "").strip().casefold()
    if not first or not second:
        return 0.0
    return SequenceMatcher(None, first, second).ratio()


def calculate_score(first, second, upload_dir=None):
    score = 0.0
    if first.category.casefold() == second.category.casefold():
        score += 25
    score += 15 * _text_similarity(first.color, second.color)
    score += 15 * _text_similarity(first.brand, second.brand)
    score += 20 * _text_similarity(first.location_name, second.location_name)
    day_gap = abs((first.date - second.date).days)
    score += 15 * max(0, 1 - day_gap / 30)
    score += 10 * _text_similarity(first.description, second.description)
    image_score = None
    if upload_dir and first.image_path and second.image_path:
        first_path = local_image_path(first.image_path, upload_dir)
        second_path = local_image_path(second.image_path, upload_dir)
        if first_path and second_path:
            image_score = image_similarity(first_path, second_path)
    if image_score is not None:
        score = score * 0.85 + image_score * 0.15
    return round(min(100, score), 1), image_score


def recalculate_for_item(item):
    if item.type not in {"LOST", "FOUND"}:
        return []
    if item.status != "ACTIVE":
        for existing in ItemMatch.query.filter((ItemMatch.lost_item_id == item.id) | (ItemMatch.found_item_id == item.id)).all():
            existing.status = "CLOSED"
        return []
    other_type = "FOUND" if item.type == "LOST" else "LOST"
    candidates = Item.query.filter_by(type=other_type, status="ACTIVE").filter(Item.id != item.id).all()
    existing_matches = ItemMatch.query.filter(
        or_(ItemMatch.lost_item_id == item.id, ItemMatch.found_item_id == item.id)
    ).all()
    matches_by_candidate = {
        (match.found_item_id if item.type == "LOST" else match.lost_item_id): match
        for match in existing_matches
    }
    matches = []
    for candidate in candidates:
        if candidate.user_id == item.user_id:
            continue
        lost, found = (item, candidate) if item.type == "LOST" else (candidate, item)
        score, image_score = calculate_score(lost, found, Path(current_app.config["UPLOAD_FOLDER"]))
        match = matches_by_candidate.get(candidate.id)
        if score < MATCH_THRESHOLD:
            if match:
                db.session.delete(match)
            continue
        is_new = match is None
        if is_new:
            match = ItemMatch(lost_item_id=lost.id, found_item_id=found.id)
            db.session.add(match)
        match.score = score
        match.image_score = image_score
        match.match_reason = "Category, appearance, location, date, and description similarity"
        if image_score is not None:
            match.match_reason += f"; image similarity {image_score:.0f}%"
        match.status = "SUGGESTED"
        matches.append(match)
        if is_new:
            for owner in (lost.owner, found.owner):
                db.session.add(Notification(
                    user_id=owner.id,
                    title="A possible item match was found",
                    message=f"A report may match {item.title}.",
                    type="MATCH",
                    related_item_id=item.id,
                ))
    db.session.flush()
    return matches
