from datetime import datetime

import click
from flask import current_app
from sqlalchemy import select

from app.models import BusService, BusStop, ServiceStop, SimulationVehicle, db
from scripts.network_data import PALETTE, dataset


def seed_network():
    """Add new demo corridors without deleting user data or changing existing stop IDs."""
    stops, corridors = dataset()
    by_name = {stop.name: stop for stop in db.session.scalars(select(BusStop))}
    by_number = {service.route_number: service for service in db.session.scalars(select(BusService))}
    by_key = {}
    changed = False
    for key, name, area, lat, lon in stops:
        stop = by_name.get(name)
        if stop is None:
            stop = BusStop(name=name, locality=area, latitude=float(lat), longitude=float(lon))
            db.session.add(stop)
            changed = True
        by_key[key] = stop
    db.session.flush()

    for i, (number, region, route) in enumerate(corridors):
        color = PALETTE[i]
        service = by_number.get(number)
        if service is not None:
            if service.color != color:
                service.color = color
                changed = True
            continue
        service = BusService(route_number=number,
                             route_name=f"{by_key[route[0]].name} → {by_key[route[-1]].name}",
                             region=region, color=color, speed_kmph=22 + (i + 1) % 6)
        db.session.add(service)
        db.session.flush()
        for direction, ordered in enumerate((route, route[::-1])):
            db.session.add_all(
                ServiceStop(service_id=service.id, stop_id=by_key[key].id,
                            stop_sequence=index, direction=direction)
                for index, key in enumerate(ordered)
            )
        db.session.add(SimulationVehicle(
            service_id=service.id, vehicle_label=f"{number}-A", initial_progress=((i + 1) * 0.137) % 1,
            speed_kmph=service.speed_kmph, simulation_start=datetime(2025, 1, 1), direction=(i + 1) % 2,
        ))
        changed = True
    db.session.commit()
    if changed:
        current_app.extensions["bus_network"].clear()
    return changed


@click.command("seed-network")
def seed_command():
    if seed_network():
        click.echo("Seeded or updated the Delhi NCR demonstration network.")
    else:
        click.echo("Network already up to date.")
