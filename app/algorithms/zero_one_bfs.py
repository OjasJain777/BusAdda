from collections import deque
from heapq import heappop, heappush
from itertools import count
from math import inf


def minimum_interchanges(source, target, graph):
    """Return (interchanges, directed ride edges), or None if unreachable."""
    if source == target:
        return 0, []
    starts = graph.boarding.get(source, ())
    ends = graph.states.get(target, ())
    transfers = dict.fromkeys(starts, 0)
    pending = deque((state, 0) for state in starts)

    while pending:
        state, cost = pending.popleft()
        if cost != transfers[state]:
            continue
        for neighbor, weight, _ in graph.moves(state):
            total = cost + weight
            if total < transfers.get(neighbor, inf):
                transfers[neighbor] = total
                if weight:
                    pending.append((neighbor, total))
                else:
                    pending.appendleft((neighbor, total))

    minimum = min((transfers.get(state, inf) for state in ends), default=inf)
    if minimum == inf:
        return None

    # Every prefix of a minimum-transfer path also has minimum transfer cost
    # for its state. Search only edges that preserve those costs.
    order = count()
    queue = [(0, next(order), state) for state in starts]
    distances = dict.fromkeys(starts, 0)
    parents = {}
    while queue:
        km, _, state = heappop(queue)
        if km > distances[state]:
            continue
        if state[0] == target and transfers[state] == minimum:
            path = []
            while state in parents:
                state, edge = parents[state]
                if edge is not None:
                    path.append(edge)
            return minimum, path[::-1]
        for neighbor, weight, edge in graph.moves(state):
            if transfers.get(neighbor) != transfers[state] + weight or transfers[neighbor] > minimum:
                continue
            total = km + (edge.km if edge else 0)
            if total < distances.get(neighbor, inf):
                distances[neighbor] = total
                parents[neighbor] = state, edge
                heappush(queue, (total, next(order), neighbor))
    raise RuntimeError("An optimal transfer path could not be reconstructed")
