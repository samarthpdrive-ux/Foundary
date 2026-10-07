from flask import Blueprint, current_app, render_template

from app.models.item import Item

maps_bp = Blueprint("maps", __name__)


@maps_bp.get("/map")
def index():
    items = Item.query.filter(Item.status == "ACTIVE", Item.latitude.isnot(None), Item.longitude.isnot(None)).order_by(Item.created_at.desc()).limit(500).all()
    map_items = []
    for item in items:
        exact = item.type == "LOST" and item.share_exact_location
        map_items.append({
            "id": item.id, "type": item.type, "title": item.title,
            "location": item.location_name, "date": item.date.strftime("%b %d, %Y"),
            "url": f"/items/{item.id}",
            "lat": round(item.latitude, 6 if exact else 2),
            "lng": round(item.longitude, 6 if exact else 2),
            "exact": exact,
        })
    return render_template("maps/index.html", map_items=map_items,
                           tile_url=current_app.config["MAP_TILE_URL"])
