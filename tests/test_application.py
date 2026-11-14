import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash

from app import create_app
from app.models import AuthSession, BusService, BusStop, SavedRoute, User, db
from app.network import get_network
from scripts.seed_database import seed_network
from tests.helpers import api_change, csrf, post_form, register_and_sign_in, sign_in, signup


def test_signup_login_logout_and_duplicate_email(app, client, email):
    assert signup(client, email).status_code == 302
    assert client.get("/login").data.find(b"Account created.") >= 0
    assert client.get("/plan").status_code == 200
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == email))
        assert user.password_hash != "NightBus-123"
        assert check_password_hash(user.password_hash, "NightBus-123")
    assert signup(client, email.upper()).status_code == 400
    wrong = sign_in(client, email, "Incorrect-password")
    unknown = sign_in(client, "unregistered-" + email)
    assert wrong.status_code == unknown.status_code == 400
    assert b"Invalid email or password." in wrong.data
    assert b"Invalid email or password." in unknown.data

    restarted = create_app({
        "TESTING": True,
        "BUSADDA_STORAGE": "mysql",
        "SECRET_KEY": app.secret_key,
        "SQLALCHEMY_DATABASE_URI": app.config["SQLALCHEMY_DATABASE_URI"],
    })
    with restarted.test_client() as rider:
        assert post_form(rider, "/login", email=email, password="NightBus-123", remember="on").status_code == 302
        assert rider.get("/profile").status_code == 200
        captured = rider.get_cookie("session").value
        assert post_form(rider, "/logout").status_code == 302
        assert rider.get("/profile").status_code == 302
    old_browser = restarted.test_client()
    old_browser.set_cookie("session", captured)
    assert old_browser.get("/api/saved").status_code == 401
    with restarted.app_context():
        user = db.session.scalar(select(User).where(User.email == email))
        assert db.session.scalar(select(AuthSession).where(AuthSession.user_id == user.id)) is None


def test_rejects_invalid_fields_and_missing_csrf(client, email):
    assert client.post("/demo").status_code == 404
    assert b'data-view="plan"' in client.get("/").data
    assert client.post("/login", data={"email": email}).status_code == 400
    for path in ("/saved", "/profile"):
        assert client.get(path).location.endswith("/login")
    with client.session_transaction() as session:
        session["demo"] = True
    assert client.get("/api/network").status_code == 200
    assert client.get("/api/saved").status_code == 401
    assert client.get("/routes").status_code == 200
    headers = {"X-CSRFToken": csrf(client, "/login")}
    source, destination = client.get("/api/network").json["presets"][0]
    for mode in ("shortest", "interchanges"):
        payload = {"source": source, "destination": destination, "mode": mode}
        assert client.post("/api/route", json=payload, headers=headers).status_code == 200
    assert client.post("/api/saved", json=payload, headers=headers).status_code == 401
    assert client.delete("/api/saved/1", headers=headers).status_code == 401
    assert signup(client, email, "weak").status_code == 400
    assert post_form(client, "/signup", name="Valid Name", email=email, password="NightBus-123",
                     confirmation="Contrast-123").status_code == 400
    assert client.get("/api/network").status_code == 200


def test_seed_reproducibility_foreign_keys_and_coverage(app):
    with app.app_context():
        assert seed_network() is False
        assert db.session.scalar(select(func.count()).select_from(BusStop)) == 102
        assert db.session.scalar(select(func.count()).select_from(BusService)) == 29
        graph = get_network().graph
        visited, pending = {1}, [1]
        while pending:
            for edge in graph.outgoing[pending.pop()]:
                if edge.target not in visited:
                    visited.add(edge.target)
                    pending.append(edge.target)
        assert visited == set(graph.stops)
        db.session.add(SavedRoute(user_id=2_000_000_000, source_stop_id=1,
                                  destination_stop_id=2, routing_mode="shortest"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_planning_returns_distinct_valid_itineraries(client, email):
    register_and_sign_in(client, email)
    network = client.get("/api/network").json
    stops = {stop["id"]: stop for stop in network["stops"]}
    services = {service["id"]: service for service in network["services"]}
    result = []
    for mode in ("shortest", "interchanges"):
        for source, destination in network["presets"]:
            response = api_change(client, "POST", "/api/route", dict(source=source, destination=destination, mode=mode))
            assert response.status_code == 200
            journey = response.json
            assert journey["stops"][0] == source and journey["stops"][-1] == destination
            assert journey["interchanges"] == [leg["to"] for leg in journey["legs"][:-1]]
            for leg in journey["legs"]:
                sequence = services[leg["service"]]["directions"][str(leg["direction"])]["stops"]
                i = sequence.index(leg["from"])
                assert leg["stops"] == sequence[i:i + len(leg["stops"])]
                assert leg["geometry"] == [[stops[sid]["lat"], stops[sid]["lon"]] for sid in leg["stops"]]
            if stops[source]["name"] == "Dwarka":
                result.append(journey)
    short, direct = result
    assert direct["km"] > short["km"]
    assert len(direct["interchanges"]) == 0 < len(short["interchanges"])
    assert client.get("/api/saved").status_code == 200
    assert api_change(client, "POST", "/api/route", dict(source=True, destination=2, mode=[])).status_code == 400
    assert api_change(client, "POST", "/api/route", dict(source=1, destination=1, mode="shortest")).status_code == 400


def test_saved_routes_reload_and_enforce_ownership(app, client, email):
    register_and_sign_in(client, email)
    payload = {"source": 1, "destination": 37, "mode": "shortest"}
    created = api_change(client, "POST", "/api/saved", payload)
    assert created.status_code == 201
    route = created.json["route"]
    assert api_change(client, "POST", "/api/saved", payload).status_code == 200
    assert post_form(client, "/logout").status_code == 302
    assert post_form(client, "/login", email=email, password="NightBus-123").status_code == 302
    assert client.get("/api/saved").json["routes"] == [route]
    outsider = app.test_client()
    register_and_sign_in(outsider, "other-" + email)
    assert outsider.get("/api/saved").json["routes"] == []
    path = f'/api/saved/{route["id"]}'
    assert api_change(outsider, "DELETE", path).status_code == 404
    assert api_change(client, "DELETE", path).status_code == 204
    assert client.get("/api/saved").json["routes"] == []


def test_corridor_geometry_and_ncr_services(client, email):
    register_and_sign_in(client, email)
    network = client.get("/api/network").json
    stops = {stop["id"]: (stop["lat"], stop["lon"]) for stop in network["stops"]}
    by_name = {stop["name"]: stop["id"] for stop in network["stops"]}
    assert len({service["color"] for service in network["services"]}) == len(network["services"])
    for service in network["services"]:
        forward, reverse = service["directions"]["0"], service["directions"]["1"]
        for a, b, line in zip(forward["stops"], forward["stops"][1:], forward["geometry"], strict=False):
            assert tuple(line[0]) == stops[a] and tuple(line[-1]) == stops[b]
        assert reverse["geometry"] == [line[::-1] for line in forward["geometry"][::-1]]
    assert any(len(line) > 2 for service in network["services"]
               for line in service["directions"]["0"]["geometry"])
    for mode in ("shortest", "interchanges"):
        query = dict(source=by_name["Faridabad"], destination=by_name["Greater Noida"], mode=mode)
        assert api_change(client, "POST", "/api/route", query).status_code == 200
