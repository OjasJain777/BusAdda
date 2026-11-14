from collections import defaultdict
from heapq import heappop, heappush
from math import inf
from random import Random

import pytest

from app.algorithms.bidirectional_dijkstra import bidirectional_dijkstra
from app.algorithms.graph_builder import Edge, Graph
from app.algorithms.haversine import haversine
from app.algorithms.zero_one_bfs import minimum_interchanges


def directed_graph(records):
    outgoing, incoming = defaultdict(list), defaultdict(list)
    for i, (source, target, distance) in enumerate(records):
        edge = Edge(source, target, i, 0, distance)
        outgoing[source].append(edge)
        incoming[target].append(edge)
    return outgoing, incoming


def reference(source, target, outgoing):
    best = {source: 0}
    queue = [(0, source)]
    while queue:
        distance, node = heappop(queue)
        if distance != best[node]:
            continue
        if node == target:
            return distance
        for edge in outgoing.get(node, ()):
            total = distance + edge.km
            if total < best.get(edge.target, inf):
                best[edge.target] = total
                heappush(queue, (total, edge.target))
    return None


def test_haversine_identical():
    assert haversine(28.6, 77.2, 28.6, 77.2) == 0


def test_haversine_known_distance():
    assert haversine(0, 0, 0, 1) == pytest.approx(111.195, abs=.01)


def test_dijkstra_directed_path_and_reconstruction():
    out, incoming = directed_graph([(1, 2, 5), (1, 3, 1), (3, 2, 1), (2, 4, 2), (3, 4, 12)])
    distance, edges = bidirectional_dijkstra(1, 4, out, incoming)
    assert distance == 4
    assert [(e.source, e.target) for e in edges] == [(1, 3), (3, 2), (2, 4)]
    assert bidirectional_dijkstra(4, 1, out, incoming) is None
    assert bidirectional_dijkstra(3, 3, out, incoming) == (0, [])


def test_dijkstra_matches_reference_on_seeded_graphs():
    random = Random(108)
    for _ in range(12):
        out, incoming = directed_graph(
            (a, b, random.randrange(0, 25)) for a in range(12) for b in range(12)
            if a != b and random.random() < .24
        )
        for start in range(12):
            for end in range(12):
                expected = reference(start, end, out)
                actual = bidirectional_dijkstra(start, end, out, incoming)
                if expected is None:
                    assert actual is None
                else:
                    distance, edges = actual
                    assert distance == expected
                    assert [(e.source, e.target) for e in edges] == list(zip(
                        [start, *(e.target for e in edges[:-1])], [e.target for e in edges]
                    ))
                    assert not edges or edges[-1].target == end


def transfer_graph():
    points = {1: (0, 0), 2: (0, 1), 3: (0, 2), 4: (0, 3), 5: (1, 1), 6: (0, 4), 7: (2, 3)}
    stops = {i: {"lat": lat, "lon": lon} for i, (lat, lon) in points.items()}
    return Graph(stops, {}, {
        (100, 0): [1, 2, 3], (200, 0): [3, 4], (300, 0): [4, 6], (400, 0): [1, 5, 3],
    })


@pytest.mark.parametrize("end,changes,path", [(3, 0, [2, 3]), (4, 1, [2, 3, 4]), (6, 2, [2, 3, 4, 6])])
def test_zero_one_bfs_transfer_count_and_distance_tie_break(end, changes, path):
    cost, edges = minimum_interchanges(1, end, transfer_graph())
    assert cost == changes
    assert [e.target for e in edges] == path
    assert edges[0].service == 100


def test_zero_one_bfs_terminals_and_boarding():
    graph = transfer_graph()
    assert minimum_interchanges(3, 4, graph)[0] == 0
    assert minimum_interchanges(6, 1, graph) is None
    assert minimum_interchanges(1, 7, graph) is None
    assert minimum_interchanges(1, 1, graph) == (0, [])
