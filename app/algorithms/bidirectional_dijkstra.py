from heapq import heappop, heappush
from itertools import count
from math import inf


def bidirectional_dijkstra(source, target, outgoing, incoming):
    """Return (kilometers, directed edges), or None if the target is unreachable."""
    if source == target:
        return 0.0, []
    order = count()
    queues = [[(0, next(order), source)], [(0, next(order), target)]]
    distances = [{source: 0}, {target: 0}]
    parents = [{}, {}]
    graph = (outgoing, incoming)
    best, meeting = inf, None

    while all(queues):
        for queue, distance in zip(queues, distances):
            while queue and queue[0][0] > distance[queue[0][2]]:
                heappop(queue)
        if not all(queues) or queues[0][0][0] + queues[1][0][0] >= best:
            break
        side = int(queues[1][0][0] < queues[0][0][0])
        here, other = distances[side], distances[1 - side]
        distance, _, node = heappop(queues[side])
        for edge in graph[side].get(node, ()):
            neighbor = edge.source if side else edge.target
            total = distance + edge.km
            if total < here.get(neighbor, inf):
                here[neighbor] = total
                parents[side][neighbor] = edge
                heappush(queues[side], (total, next(order), neighbor))
                if total + other.get(neighbor, inf) < best:
                    best, meeting = total + other[neighbor], neighbor

    if meeting is None:
        return None
    forward, backward = [], []
    node = meeting
    while node != source:
        edge = parents[0][node]
        forward.append(edge)
        node = edge.source
    node = meeting
    while node != target:
        edge = parents[1][node]
        backward.append(edge)
        node = edge.target
    path = forward[::-1] + backward
    return sum(edge.km for edge in path), path
