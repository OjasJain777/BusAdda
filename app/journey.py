from itertools import groupby

from .algorithms.bidirectional_dijkstra import bidirectional_dijkstra
from .algorithms.zero_one_bfs import minimum_interchanges
from .network import DWELL_SECONDS, TRANSFER_MINUTES

MODES = {"shortest": "Shortest Route", "interchanges": "Minimum Interchange"}


def plan(graph, source, target, mode):
    if mode == "shortest":
        result = bidirectional_dijkstra(source, target, graph.outgoing, graph.incoming)
    else:
        result = minimum_interchanges(source, target, graph)
    if result is None:
        return None
    _, edges = result
    legs = []
    for (service_id, direction), group in groupby(edges, key=lambda edge: (edge.service, edge.direction)):
        route = list(group)
        service = graph.services[service_id]
        stops = [route[0].source, *(edge.target for edge in route)]
        km = sum(edge.km for edge in route)
        ride_minutes = km / service["speed"] * 60 + max(0, len(route) - 1) * DWELL_SECONDS / 60
        legs.append({
            "service": service_id, "number": service["number"], "direction": direction,
            "toward": graph.sequences[service_id, direction][-1], "stops": stops,
            "from": stops[0], "to": stops[-1], "km": round(km, 2), "minutes": max(1, round(ride_minutes)),
            "geometry": [[graph.stops[stop]["lat"], graph.stops[stop]["lon"]] for stop in stops],
            "ride_seconds": round(ride_minutes * 60),
        })
    interchanges = [leg["to"] for leg in legs[:-1]]
    return {
        "source": source, "destination": target, "mode": mode, "mode_label": MODES[mode],
        "km": round(sum(edge.km for edge in edges), 2),
        "minutes": round(sum(leg["ride_seconds"] for leg in legs) / 60 + len(interchanges) * TRANSFER_MINUTES),
        "stops": [source, *(edge.target for edge in edges)],
        "interchanges": interchanges, "transfer_minutes": TRANSFER_MINUTES, "legs": legs,
    }
