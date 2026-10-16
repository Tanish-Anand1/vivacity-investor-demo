"""Seeded joint-space routing and shared, time-parameterized stage commands."""
import numpy as np


def stage_path(stage):
    return np.asarray(stage.get('waypoints') or [stage['start'], stage['goal']], dtype=float)


def stage_distance(stage):
    return float(np.max(np.abs(np.diff(stage_path(stage), axis=0)), axis=1).sum())


def stage_commands(stage, fractions):
    path = stage_path(stage)
    lengths = np.max(np.abs(np.diff(path, axis=0)), axis=1)
    total = lengths.sum()
    if total < 1e-12:
        return np.tile(path[-1], (len(fractions), 1))
    ends = np.r_[0., np.cumsum(lengths)] / total
    positions = np.clip(np.asarray(fractions), 0, 1)
    indices = np.clip(np.searchsorted(ends, positions, side='right') - 1, 0, len(path)-2)
    alpha = (positions - ends[indices]) / np.maximum(ends[indices+1]-ends[indices], 1e-12)
    blend = alpha * alpha * (3 - 2*alpha)
    return path[indices] * (1-blend[:, None]) + path[indices+1] * blend[:, None]


def joint_route(start, goal, limits, valid, rng, iterations, checkpoint=None):
    """RRT with deterministic shortcutting; every accepted edge is checked."""
    def edge(a, b):
        return all(valid(a+(b-a)*t) for t in np.linspace(0, 1, max(2, int(np.linalg.norm(b-a)/.05)+1)))
    if not valid(start) or not valid(goal):
        return None
    if edge(start, goal):
        return [start, goal]
    nodes, parents = [start], [-1]
    for _ in range(iterations):
        if checkpoint and not checkpoint():
            raise InterruptedError('cancelled during pickup routing')
        sample = goal if rng.random() < .25 else rng.uniform(limits[:, 0]+.01, limits[:, 1]-.01)
        parent = int(np.argmin(np.linalg.norm(np.asarray(nodes)-sample, axis=1)))
        diff = sample-nodes[parent]
        q = nodes[parent]+diff*min(1., .3/max(np.linalg.norm(diff), 1e-12))
        if not edge(nodes[parent], q):
            continue
        nodes.append(q); parents.append(parent)
        if np.linalg.norm(q-goal) < .7 and edge(q, goal):
            path = [goal, q]
            while parent >= 0:
                path.append(nodes[parent]); parent = parents[parent]
            path.reverse()
            shortened = [path[0]]; i = 0
            while i < len(path)-1:
                j = len(path)-1
                while j > i+1 and not edge(path[i], path[j]): j -= 1
                shortened.append(path[j]); i = j
            return shortened
    return None
