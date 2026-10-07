from datetime import date

import pytest
from sqlalchemy import create_engine

from app import create_app
from config import TestingConfig
from app.extensions import db
from app.models.item import Item
from app.models.message import Message
from app.models.audit_log import AuditLog
from app.models.user import User


@pytest.fixture()
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username, email):
    return client.post("/auth/register", data={
        "full_name": username.title(), "username": username,
        "email": email, "password": "correct-horse-123", "confirm_password": "correct-horse-123",
    }, follow_redirects=True)


def login(client, identity):
    return client.post("/auth/login", data={"email": identity, "password": "correct-horse-123"}, follow_redirects=True)


def test_public_pages_and_security_headers(client):
    assert client.get("/").status_code == 200
    assert client.get("/items").status_code == 200
    response = client.get("/health")
    assert response.json == {"status": "ok"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=(self)"


def test_location_picker_requests_explicit_permission_and_public_map_rounds_coordinates(client, app):
    register(client, "locationuser", "locationuser@example.com")
    form = client.get("/report/lost")
    assert b"Use my current location" in form.data
    assert b"never continuously" in form.data

    with app.app_context():
        owner = User.query.filter_by(username="locationuser").one()
        item = Item(
            user_id=owner.id, type="LOST", status="ACTIVE", title="Green umbrella",
            category="Other", description="Green umbrella with a wooden handle.",
            date=date.today(), location_name="Central Library", latitude=28.613219,
            longitude=77.208431,
        )
        db.session.add(item)
        db.session.commit()

    public_map = client.get("/map")
    assert public_map.status_code == 200
    assert b'"lat": 28.61' in public_map.data
    assert b'"lng": 77.21' in public_map.data
    assert b'28.613219' not in public_map.data
    assert b'77.208431' not in public_map.data


def test_lost_reporter_can_opt_in_to_exact_public_location(client, app):
    register(client, "exactlocation", "exactlocation@example.com")
    assert b"Share my exact lost location publicly" in client.get("/report/lost").data
    with app.app_context():
        owner = User.query.filter_by(username="exactlocation").one()
        item = Item(
            user_id=owner.id, type="LOST", status="ACTIVE", title="Black phone",
            category="Electronics", description="Black phone with a blue case.",
            date=date.today(), location_name="Central Library", latitude=28.613219,
            longitude=77.208431, share_exact_location=True,
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    detail = client.get(f"/items/{item_id}")
    assert b"Exact location shared by reporter" in detail.data
    assert b"28.613219" in detail.data

    public_map = client.get("/map")
    assert b'"lat": 28.613219' in public_map.data
    assert b'"lng": 77.208431' in public_map.data


def test_admin_chat_review_requires_either_participant_consent_and_logs_access(client, app):
    register(client, "chatowner", "chatowner@example.com")
    with app.app_context():
        owner = User.query.filter_by(username="chatowner").one()
        owner_id = owner.id
    client.post("/auth/logout")

    register(client, "chatpeer", "chatpeer@example.com")
    with app.app_context():
        peer = User.query.filter_by(username="chatpeer").one()
        peer_id = peer.id
    client.post("/auth/logout")

    register(client, "chatadmin", "chatadmin@example.com")
    with app.app_context():
        admin = User.query.filter_by(username="chatadmin").one()
        admin.role = "ADMIN"
        item = Item(
            user_id=owner_id, type="LOST", status="ACTIVE", title="Blue phone",
            category="Electronics", description="Blue phone with a cracked case.",
            date=date.today(), location_name="City Library",
        )
        db.session.add(item)
        db.session.flush()
        db.session.add(Message(
            sender_id=owner_id, receiver_id=peer_id, item_id=item.id,
            message="Private chat for consent test.",
        ))
        db.session.commit()
        item_id = item.id

    client.post("/auth/logout")
    login(client, "chatadmin@example.com")
    conversation_url = f"/admin/messages/{item_id}/{min(owner_id, peer_id)}/{max(owner_id, peer_id)}"
    assert client.get(conversation_url).status_code == 404
    assert b"No conversations have consent" in client.get("/admin/messages").data

    client.post("/auth/logout")
    login(client, "chatowner@example.com")
    client.post(f"/messages/{peer_id}/{item_id}/admin-access/allow")
    client.post("/auth/logout")
    login(client, "chatadmin@example.com")

    assert b"chatowner" in client.get("/admin/messages").data
    review = client.get(conversation_url)
    assert review.status_code == 200
    assert b"Private chat for consent test." in review.data
    with app.app_context():
        assert AuditLog.query.filter_by(action="VIEW_PRIVATE_MESSAGES").count() == 1

    client.post("/auth/logout")
    login(client, "chatowner@example.com")
    client.post(f"/messages/{peer_id}/{item_id}/admin-access/revoke")
    client.post("/auth/logout")
    login(client, "chatadmin@example.com")
    assert client.get(conversation_url).status_code == 404


def test_registration_login_and_safe_redirect(client):
    assert register(client, "alex", "alex@example.com").status_code == 200
    client.post("/auth/logout")
    assert login(client, "alex").status_code == 200
    client.post("/auth/logout")
    response = client.post("/auth/login?next=https://evil.example", data={
        "email": "alex@example.com", "password": "correct-horse-123",
    })
    assert response.status_code == 302
    assert response.location.endswith("/profile/")


def test_item_ownership_claim_and_return_flow(client, app):
    register(client, "finder", "finder@example.com")
    found_form = {
        "title": "Blue canvas backpack", "category": "Bags",
        "description": "Blue canvas backpack with a silver zipper and notebook inside.",
        "color": "blue", "brand": "North", "date": date.today().isoformat(),
        "location_name": "Central Library", "latitude": "28.612", "longitude": "77.208",
        "submit": "Publish report",
    }
    response = client.post("/report/found", data=found_form, follow_redirects=True)
    assert response.status_code == 200
    assert b"Blue canvas backpack" in response.data
    with app.app_context():
        item = Item.query.filter_by(title="Blue canvas backpack").one()
        item_id = item.id
        finder_id = item.user_id

    client.post("/auth/logout")
    register(client, "owner", "owner@example.com")
    lost_form = dict(found_form, title="Blue canvas backpack")
    assert client.post("/report/lost", data=lost_form, follow_redirects=True).status_code == 200
    claim_response = client.post(f"/items/{item_id}/claim", data={
        "message": "This is my backpack and I can identify what is inside.",
        "verification_answer_1": "A red notebook in the front pocket",
        "verification_answer_2": "Small stitched initials inside the top flap",
        "verification_answer_3": "There is a keychain in the side pocket",
    }, follow_redirects=True)
    assert claim_response.status_code == 200
    with app.app_context():
        from app.models.claim import Claim
        claim_id = Claim.query.filter_by(item_id=item_id).one().id

    forbidden = client.post(f"/claims/{claim_id}/approve")
    assert forbidden.status_code == 403
    client.post("/auth/logout")
    login(client, "finder")
    approved = client.post(f"/claims/{claim_id}/approve", follow_redirects=True)
    assert approved.status_code == 200
    with app.app_context():
        item = db.session.get(Item, item_id)
        assert item.status == "RETURNED"
        assert item.user_id == finder_id


def test_private_routes_and_map(client):
    assert client.get("/messages/").status_code == 302
    assert client.get("/profile/").status_code == 302
    assert client.get("/map").status_code == 200


def test_production_rejects_missing_secrets(monkeypatch):
    from config import ProductionConfig
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.validate()
    monkeypatch.setenv("SECRET_KEY", "replace-with-a-random-secret")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.validate()


def test_tidb_settings_build_verified_pymysql_connection(monkeypatch):
    from config import _database_settings

    for key in ("DATABASE_URL", "TIDB_URL", "MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TIDB_HOST", "gateway.example.tidbcloud.com")
    monkeypatch.setenv("TIDB_USER", "cluster.root")
    monkeypatch.setenv("TIDB_PASSWORD", "pass@word:/with#symbols")
    monkeypatch.setenv("TIDB_DATABASE", "foundry")
    monkeypatch.setenv("TIDB_PORT", "4000")

    url, engine_options = _database_settings()
    assert url.drivername == "mysql+pymysql"
    assert url.password == "pass@word:/with#symbols"
    assert url.host == "gateway.example.tidbcloud.com"
    assert url.port == 4000
    assert engine_options["connect_args"]["ssl_verify_cert"] is True
    assert engine_options["connect_args"]["ssl_verify_identity"] is True
    engine = create_engine(url, **engine_options)
    assert engine.dialect.name == "mysql"
    assert engine.dialect.driver == "pymysql"
    engine.dispose()

