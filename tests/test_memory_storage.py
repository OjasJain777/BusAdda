from werkzeug.security import check_password_hash

from app import create_app
from app.storage import get_store
from tests.helpers import api_change, post_form, register_and_sign_in, sign_in, signup


def test_database_free_demo_account_and_routes():
    config = {"TESTING": True, "SECRET_KEY": "memory-test", "BUSADDA_STORAGE": "memory",
              "SQLALCHEMY_DATABASE_URI": None}
    app = create_app(config)
    assert "sqlalchemy" not in app.extensions
    rider = app.test_client()
    assert b"Temporary demo" in rider.get("/login").data
    assert rider.get("/api/network").status_code == 401
    email = "memory-test@example.com"
    register_and_sign_in(rider, email)
    with app.app_context():
        stored_user = get_store().find_user(email)
        assert stored_user.password_hash != "NightBus-123"
        assert check_password_hash(stored_user.password_hash, "NightBus-123")

    network = rider.get("/api/network").json
    assert len(network["stops"]) == 102
    assert len(network["services"]) == 29
    source, destination = network["presets"][0]
    payload = {"source": source, "destination": destination, "mode": "shortest"}
    journey = api_change(rider, "POST", "/api/route", payload)
    assert journey.status_code == 200
    direct = api_change(rider, "POST", "/api/route", dict(payload, mode="interchanges"))
    assert direct.status_code == 200
    assert len(direct.json["interchanges"]) < len(journey.json["interchanges"])

    saved = api_change(rider, "POST", "/api/saved", payload)
    assert saved.status_code == 201
    assert api_change(rider, "POST", "/api/saved", payload).status_code == 200
    assert rider.get("/api/saved").json["routes"] == [saved.json["route"]]
    assert rider.get("/profile").status_code == 200
    route_id = saved.json["route"]["id"]

    second_rider = app.test_client()
    assert signup(second_rider, email.upper()).status_code == 400
    register_and_sign_in(second_rider, "other-memory-test@example.com")
    assert second_rider.get("/api/saved").json["routes"] == []
    assert api_change(second_rider, "DELETE", f"/api/saved/{route_id}").status_code == 404

    old_cookie = rider.get_cookie("session").value
    assert post_form(rider, "/logout").status_code == 302
    rider.set_cookie("session", old_cookie)
    assert rider.get("/api/network").status_code == 401
    assert sign_in(rider, email).status_code == 302
    assert api_change(rider, "DELETE", f"/api/saved/{route_id}").status_code == 204

    fresh_instance = create_app(config).test_client()
    assert sign_in(fresh_instance, email).status_code == 400
