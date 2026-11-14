from collections import defaultdict
from dataclasses import dataclass

from .haversine import haversine


@dataclass(frozen=True, slots=True)
class Edge:
    source: int
    target: int
    service: int
    direction: int
    km: float


class Graph:
    def __init__(self, stops, services, sequences):
        self.stops = stops
        self.services = services
        self.sequences = sequences
        self.outgoing = defaultdict(list)
        self.incoming = defaultdict(list)
        self.states = defaultdict(list)
        self.boarding = defaultdict(list)
        self.rides = {}
        self.segments = {}
        for (service, direction), sequence in sequences.items():
            segments = []
            for stop in sequence:
                self.states[stop].append((stop, service, direction))
            for source, target in zip(sequence, sequence[1:]):
                a, b = stops[source], stops[target]
                km = haversine(a["lat"], a["lon"], b["lat"], b["lon"])
                edge = Edge(source, target, service, direction, km)
                self.outgoing[source].append(edge)
                self.incoming[target].append(edge)
                state = (source, service, direction)
                self.boarding[source].append(state)
                self.rides[state] = edge
                segments.append(km)
            self.segments[service, direction] = segments

    def moves(self, state):
        stop, _, _ = state
        ride = self.rides.get(state)
        if ride is not None:
            yield (ride.target, ride.service, ride.direction), 0, ride
        for other in self.boarding.get(stop, ()):
            if other != state:
                yield other, 1, None
