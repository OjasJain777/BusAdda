from datetime import timezone
from functools import wraps
from time import time

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .journey import MODES, plan
from .models import SavedRoute, db
from .network import get_network

web = Blueprint("web", __name__)
api = Blueprint("api", __name__, url_prefix="/api")
PAGES = {"plan": "Plan Route", "buses": "Live Buses", "routes": "Explore Bus Routes", "stops": "Bus Stops", "saved": "Saved Routes", "profile": "Profile"}


def access(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated:
            return view(*args, **kwargs)
        if request.blueprint == "api":
            return jsonify(error="Your session has ended. Sign in to continue."), 401
        return redirect(url_for("auth.credentials"))
    return wrapped


@web.get("/")
def index():
    return redirect(url_for("web.page", view="plan") if current_user.is_authenticated else url_for("auth.credentials"))


@web.get("/<any(plan,buses,routes,stops,saved,profile):view>")
@access
def page(view):
    profile = None
    if view == "profile" and current_user.is_authenticated:
        profile = {
            "name": current_user.full_name, "email": current_user.email,
            "joined": current_user.created_at.strftime("%d %B %Y"),
            "count": db.session.scalar(select(func.count()).select_from(SavedRoute).where(
                SavedRoute.user_id == current_user.id
            )),
        }
    return render_template("dashboard.html", view=view, title=PAGES[view], profile=profile, pages=PAGES)


@api.get("/network")
@access
def network():
    return jsonify(**get_network().payload, now=int(time() * 1000))


def journey_parameters(data, graph):
    source, destination, mode = (data.get(key) for key in ("source", "destination", "mode"))
    if type(source) is not int or type(destination) is not int or source not in graph.stops or destination not in graph.stops:
        return None, "Choose two stops from the suggestions."
    if source == destination:
        return None, "Choose a destination different from the starting stop."
    if not isinstance(mode, str) or mode not in MODES:
        return None, "Choose a supported routing mode."
    return (source, destination, mode), None


@api.post("/route")
@access
def route():
    data = request.get_json(silent=True)
    graph = get_network().graph
    params, error = journey_parameters(data if isinstance(data, dict) else {}, graph)
    if error:
        return jsonify(error=error), 400
    result = plan(graph, *params)
    if result is None:
        return jsonify(error="These stops are not connected by a simulated bus service."), 404
    return jsonify(result)


def route_record(row):
    return {
        "id": row.id, "source": row.source_stop_id, "destination": row.destination_stop_id,
        "mode": row.routing_mode, "created": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
    }


@api.route("/saved", methods=["GET", "POST"])
@access
def saved():
    owned = select(SavedRoute).where(SavedRoute.user_id == current_user.id)
    if request.method == "GET":
        rows = db.session.scalars(owned.order_by(SavedRoute.created_at.desc(), SavedRoute.id.desc()))
        return jsonify(routes=[route_record(row) for row in rows])
    data = request.get_json(silent=True)
    graph = get_network().graph
    params, error = journey_parameters(data if isinstance(data, dict) else {}, graph)
    if error:
        return jsonify(error=error), 400
    if plan(graph, *params) is None:
        return jsonify(error="This route is currently unavailable."), 404
    source, target, mode = params
    existing = owned.where(SavedRoute.source_stop_id == source, SavedRoute.destination_stop_id == target,
                           SavedRoute.routing_mode == mode)
    row = db.session.scalar(existing)
    if row:
        return jsonify(route=route_record(row)), 200
    row = SavedRoute(user_id=current_user.id, source_stop_id=source, destination_stop_id=target, routing_mode=mode)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        row = db.session.scalar(existing)
        if row is None:
            raise
        return jsonify(route=route_record(row)), 200
    return jsonify(route=route_record(row)), 201


@api.delete("/saved/<int:route_id>")
@access
def delete_saved(route_id):
    row = db.session.scalar(select(SavedRoute).where(SavedRoute.id == route_id, SavedRoute.user_id == current_user.id))
    if row is None:
        return jsonify(error="Saved route not found."), 404
    db.session.delete(row)
    db.session.commit()
    return "", 204
