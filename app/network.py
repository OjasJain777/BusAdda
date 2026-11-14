from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from flask import current_app
from sqlalchemy import select

from .algorithms.graph_builder import Graph
from .corridors import segment_geometry
from .models import BusService, BusStop, ServiceStop, SimulationVehicle, db

DWELL_SECONDS = 14
TRANSFER_MINUTES = 4
PRESETS = (
    ("Dwarka", "Connaught Place"), ("Rohini", "Saket"), ("Janakpuri", "AIIMS"),
    ("Kashmiri Gate", "Noida Sector 15"), ("Rajouri Garden", "Lajpat Nagar"),
)


@dataclass
class Network:
    graph: Graph
    payload: dict


class NetworkCache:
    def __init__(self, loader=None):
        self.loader = loader or load_network
        self.snapshot = None
        self.lock = Lock()

    def get(self):
        if self.snapshot is None:
            with self.lock:
                if self.snapshot is None:
                    network = self.loader()
                    if network.graph.stops:
                        self.snapshot = network
                    return network
        return self.snapshot

    def clear(self):
        with self.lock:
            self.snapshot = None


def get_network():
    return current_app.extensions["bus_network"].get()


def load_network():
    stops = {
        row.id: {"id": row.id, "name": row.name, "locality": row.locality, "lat": row.latitude, "lon": row.longitude}
        for row in db.session.scalars(select(BusStop).order_by(BusStop.id))
    }
    services = {
        row.id: {"id": row.id, "number": row.route_number, "name": row.route_name,
                 "color": row.color, "region": row.region, "speed": row.speed_kmph}
        for row in db.session.scalars(select(BusService).where(BusService.is_active).order_by(BusService.id))
    }
    sequences = defaultdict(list)
    statement = select(ServiceStop).order_by(
        ServiceStop.service_id, ServiceStop.direction, ServiceStop.stop_sequence
    )
    for row in db.session.scalars(statement):
        if row.service_id in services:
            sequences[row.service_id, row.direction].append(row.stop_id)
    vehicles = [{
        "id": row.id, "service": row.service_id, "label": row.vehicle_label, "progress": row.initial_progress,
        "speed": row.speed_kmph, "direction": row.direction,
        "start": row.simulation_start.replace(tzinfo=timezone.utc).timestamp() * 1000,
    } for row in db.session.scalars(select(SimulationVehicle).order_by(SimulationVehicle.id))
        if (row.service_id, row.direction) in sequences]
    return build_network(stops, services, sequences, vehicles)


def load_demo_network():
    from scripts.network_data import PALETTE, dataset

    stop_rows, corridors = dataset()
    keys = {key: sid for sid, (key, *_) in enumerate(stop_rows, 1)}
    stops = {
        keys[key]: {"id": keys[key], "name": name, "locality": area, "lat": float(lat), "lon": float(lon)}
        for key, name, area, lat, lon in stop_rows
    }
    services, sequences, vehicles = {}, {}, []
    start = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
    for sid, (number, region, route) in enumerate(corridors, 1):
        sequence = [keys[key] for key in route]
        name = f"{stops[sequence[0]]['name']} → {stops[sequence[-1]]['name']}"
        speed = 22 + sid % 6
        services[sid] = {"id": sid, "number": number, "name": name, "color": PALETTE[sid - 1],
                         "region": region, "speed": speed}
        sequences[sid, 0] = sequence
        sequences[sid, 1] = sequence[::-1]
        vehicles.append({"id": sid, "service": sid, "label": f"{number}-A",
                         "progress": (sid * 0.137) % 1, "speed": speed, "direction": sid % 2,
                         "start": start})
    return build_network(stops, services, sequences, vehicles)


def build_network(stops, services, sequences, vehicles):
    graph = Graph(stops, services, sequences)
    for sid, stop in stops.items():
        stop["services"] = sorted({state[1] for state in graph.states.get(sid, ())})
        stop["neighbors"] = sorted(
            {edge.target for edge in graph.outgoing.get(sid, ())} |
            {edge.source for edge in graph.incoming.get(sid, ())},
            key=lambda neighbor: stops[neighbor]["name"],
        )
    directions = defaultdict(dict)
    for (sid, direction), sequence in sequences.items():
        distances = graph.segments[sid, direction]
        minutes = sum(distances) / services[sid]["speed"] * 60
        minutes += max(0, len(sequence) - 2) * DWELL_SECONDS / 60
        directions[sid][direction] = {
            "stops": sequence, "segments": distances,
            "geometry": [segment_geometry(stops[a], stops[b]) for a, b in zip(sequence, sequence[1:])],
            "km": round(sum(distances), 2), "minutes": round(minutes),
        }
    network_services = [dict(service, directions=directions[sid]) for sid, service in services.items()]
    by_name = {stop["name"]: stop["id"] for stop in stops.values()}
    presets = [[by_name[a], by_name[b]] for a, b in PRESETS if a in by_name and b in by_name]
    return Network(graph, {
        "stops": list(stops.values()), "services": network_services, "vehicles": vehicles,
        "presets": presets, "dwell": DWELL_SECONDS,
    })
