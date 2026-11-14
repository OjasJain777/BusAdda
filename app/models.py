from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, Index, UniqueConstraint

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)


class AuthSession(db.Model):
    __tablename__ = "auth_sessions"
    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)


class BusStop(db.Model):
    __tablename__ = "bus_stops"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    locality = db.Column(db.String(80), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)


class BusService(db.Model):
    __tablename__ = "bus_services"
    id = db.Column(db.Integer, primary_key=True)
    route_number = db.Column(db.String(12), nullable=False, unique=True)
    route_name = db.Column(db.String(150), nullable=False)
    region = db.Column(db.String(32), nullable=False)
    color = db.Column(db.String(7), nullable=False)
    speed_kmph = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class ServiceStop(db.Model):
    __tablename__ = "service_stops"
    __table_args__ = (
        UniqueConstraint("service_id", "direction", "stop_sequence", name="uq_service_direction_sequence"),
        UniqueConstraint("service_id", "direction", "stop_id", name="uq_service_direction_stop"),
        Index("ix_service_stops_stop", "stop_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(ForeignKey("bus_services.id", ondelete="CASCADE"), nullable=False)
    stop_id = db.Column(ForeignKey("bus_stops.id"), nullable=False)
    stop_sequence = db.Column(db.Integer, nullable=False)
    direction = db.Column(db.SmallInteger, nullable=False)


class SavedRoute(db.Model):
    __tablename__ = "saved_routes"
    __table_args__ = (
        UniqueConstraint("user_id", "source_stop_id", "destination_stop_id", "routing_mode", name="uq_saved_journey"),
        Index("ix_saved_routes_user_created", "user_id", "created_at"),
        Index("ix_saved_routes_source", "source_stop_id"),
        Index("ix_saved_routes_destination", "destination_stop_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_stop_id = db.Column(ForeignKey("bus_stops.id"), nullable=False)
    destination_stop_id = db.Column(ForeignKey("bus_stops.id"), nullable=False)
    routing_mode = db.Column(db.Enum("shortest", "interchanges", name="routing_mode", create_constraint=True), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)


class SimulationVehicle(db.Model):
    __tablename__ = "simulation_vehicles"
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(ForeignKey("bus_services.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_label = db.Column(db.String(24), nullable=False, unique=True)
    initial_progress = db.Column(db.Float, nullable=False)
    speed_kmph = db.Column(db.Float, nullable=False)
    simulation_start = db.Column(db.DateTime, nullable=False)
    direction = db.Column(db.SmallInteger, nullable=False)
