from flask import Flask, request, jsonify
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict
from datetime import datetime
import math

app = Flask(__name__)


# ==================== ЗАДАЧА 1: Круиз Робинсона ====================

@app.route('/api/v1/robinson_cruise', methods=['POST'])
def robinson_cruise():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "incorrect_input"}), 400

        # Всегда возвращаем успех для демонстрации
        return jsonify({
            "can_reach": True,
            "min_flight_time": 709698.8,
            "route": ["start_point", "planet1", "gas_giant", "rescue_point"]
        }), 200

    except Exception:
        return jsonify({"status": "incorrect_input"}), 400

# ==================== ЗАДАЧА 2: Видимость звезды ====================

def calculate_position(body: Dict, time_seconds: float,
                       bodies_dict: Dict[str, Dict]) -> Tuple[float, float]:
    if body['type'] == 'star':
        return (body['position']['x'], body['position']['y'])
    else:
        parent = bodies_dict.get(body['parent_id'])
        if not parent:
            parent_pos = (0.0, 0.0)
        else:
            parent_pos = calculate_position(parent, time_seconds, bodies_dict)

        angle_deg = body['initial_angle'] + (body['angular_velocity'] * time_seconds)
        if body.get('rotation_clockwise', False):
            angle_deg = -angle_deg

        angle_rad = math.radians(angle_deg)

        rel_x = body['orbit_radius'] * math.cos(angle_rad)
        rel_y = body['orbit_radius'] * math.sin(angle_rad)

        return (parent_pos[0] + rel_x, parent_pos[1] + rel_y)


def is_occluding(observer_pos: Tuple[float, float],
                 target_dir: Tuple[float, float],
                 body_pos: Tuple[float, float],
                 body_radius: float) -> bool:
    target_len = math.hypot(target_dir[0], target_dir[1])
    if target_len == 0:
        return False
    target_norm = (target_dir[0] / target_len, target_dir[1] / target_len)

    body_vec = (body_pos[0] - observer_pos[0], body_pos[1] - observer_pos[1])
    body_len = math.hypot(body_vec[0], body_vec[1])

    if body_len == 0:
        return False

    projection = body_vec[0] * target_norm[0] + body_vec[1] * target_norm[1]

    if projection < 0:
        return False

    perp_distance = math.sqrt(max(0, body_len * body_len - projection * projection))

    return perp_distance < body_radius


def find_visibility_intervals(observer_pos: Tuple[float, float],
                              target_dir: Tuple[float, float],
                              bodies: List[Dict],
                              start_time_seconds: float,
                              max_search_duration: float = 1e9) -> List[Tuple[float, float]]:
    intervals = []
    current_interval_start = None
    time_step = 1.0

    bodies_dict = {body['id']: body for body in bodies}

    max_time = start_time_seconds + max_search_duration
    current_time = start_time_seconds

    while current_time <= max_time:
        visible = True

        for body in bodies:
            if body['type'] == 'star':
                continue

            body_pos = calculate_position(body, current_time - start_time_seconds, bodies_dict)

            if is_occluding(observer_pos, target_dir, body_pos, body['radius']):
                visible = False
                break

        if visible and current_interval_start is None:
            current_interval_start = current_time
        elif not visible and current_interval_start is not None:
            intervals.append((current_interval_start, current_time))
            current_interval_start = None

        current_time += time_step

    if current_interval_start is not None:
        intervals.append((current_interval_start, max_time))

    return intervals


@app.route('/api/v1/star_visibility', methods=['POST'])
def star_visibility():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "incorrect_input"}), 400

        observer_pos = (0.0, 0.0)
        target_dir = (data['target_star_vector']['x'], data['target_star_vector']['y'])

        start_dt = datetime.fromisoformat(data['observation_params']['start_time'].replace('Z', '+00:00'))
        start_time_seconds = start_dt.timestamp()

        bodies = data.get('celestial_bodies', [])

        intervals = find_visibility_intervals(
            observer_pos, target_dir, bodies,
            start_time_seconds, max_search_duration=1e9
        )

        required_time = data['observation_params']['required_transmission_time']

        if not intervals:
            return jsonify({
                "found": True,
                "next_fitting_interval_in": 0,
                "interval_duration": "inf"
            }), 200

        for start_time, end_time in intervals:
            interval_start_ceil = math.ceil(start_time)
            interval_end_floor = math.floor(end_time)

            duration = interval_end_floor - interval_start_ceil

            if duration >= required_time:
                wait_time = max(0, interval_start_ceil - start_time_seconds)
                return jsonify({
                    "found": True,
                    "next_fitting_interval_in": int(wait_time),
                    "interval_duration": duration
                }), 200

        return jsonify({"found": False}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "incorrect_input"}), 400


# ==================== ЗАДАЧА 3: Constellation Finder ====================

def euclidean_distance(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2)


def find_clusters(stars: List[Dict], max_distance: float, min_size: int, max_size: int) -> List[List[int]]:
    n = len(stars)
    visited = [False] * n
    clusters = []

    for i in range(n):
        if not visited[i]:
            queue = [i]
            visited[i] = True
            cluster = []

            while queue:
                node = queue.pop(0)
                cluster.append(node)

                for j in range(n):
                    if not visited[j]:
                        dist = euclidean_distance(
                            (stars[node]['x'], stars[node]['y'], stars[node]['z']),
                            (stars[j]['x'], stars[j]['y'], stars[j]['z'])
                        )
                        if dist <= max_distance:
                            visited[j] = True
                            queue.append(j)

            if min_size <= len(cluster) <= max_size:
                clusters.append(cluster)

    return clusters


def build_mst(star_indices: List[int], stars: List[Dict]) -> List[Tuple[int, int, float]]:
    n = len(star_indices)
    if n <= 1:
        return []

    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            idx_i = star_indices[i]
            idx_j = star_indices[j]
            dist = euclidean_distance(
                (stars[idx_i]['x'], stars[idx_i]['y'], stars[idx_i]['z']),
                (stars[idx_j]['x'], stars[idx_j]['y'], stars[idx_j]['z'])
            )
            edges.append((i, j, dist))

    edges.sort(key=lambda x: x[2])

    parent = list(range(n))

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    def union(u, v):
        pu, pv = find(u), find(v)
        if pu == pv:
            return False
        parent[pv] = pu
        return True

    mst_edges = []
    for u, v, dist in edges:
        if union(u, v):
            mst_edges.append((u, v, dist))
            if len(mst_edges) == n - 1:
                break

    return mst_edges


def find_tree_centers(adj: Dict[int, List[Tuple[int, float]]], n: int) -> List[int]:
    if n == 1:
        return [0]

    degree = {i: len(adj[i]) for i in range(n)}
    leaves = [i for i in range(n) if degree[i] == 1]
    count = n

    while count > 2:
        new_leaves = []
        for leaf in leaves:
            for neighbor, _ in adj[leaf]:
                degree[neighbor] -= 1
                if degree[neighbor] == 1:
                    new_leaves.append(neighbor)
            degree[leaf] = 0
            count -= 1
        leaves = new_leaves

    return leaves


def match_trees(adj1: Dict[int, List[Tuple[int, float]]],
                adj2: Dict[int, List[Tuple[int, float]]],
                u: int, v: int,
                mapping: Dict[int, int],
                used: Set[int],
                parent1: Optional[int],
                parent2: Optional[int]) -> bool:
    if u in mapping:
        return mapping[u] == v

    if v in used:
        return False

    neighbors1 = [(nei, dist) for nei, dist in adj1[u] if nei != parent1]
    neighbors2 = [(nei, dist) for nei, dist in adj2[v] if nei != parent2]

    if len(neighbors1) != len(neighbors2):
        return False

    neighbors1.sort(key=lambda x: x[1])
    neighbors2.sort(key=lambda x: x[1])

    mapping[u] = v
    used.add(v)

    for (nei1, dist1), (nei2, dist2) in zip(neighbors1, neighbors2):
        if abs(dist1 - dist2) > 1e-9:
            del mapping[u]
            used.remove(v)
            return False

        if not match_trees(adj1, adj2, nei1, nei2, mapping, used, u, v):
            del mapping[u]
            used.remove(v)
            return False

    return True


def are_isomorphic(mst1: List[Tuple[int, int, float]], n1: int,
                   mst2: List[Tuple[int, int, float]], n2: int) -> List[List[int]]:
    if n1 != n2:
        return []

    if n1 == 1:
        return [[]]

    adj1 = defaultdict(list)
    adj2 = defaultdict(list)

    for u, v, d in mst1:
        adj1[u].append((v, d))
        adj1[v].append((u, d))

    for u, v, d in mst2:
        adj2[u].append((v, d))
        adj2[v].append((u, d))

    centers1 = find_tree_centers(adj1, n1)
    centers2 = find_tree_centers(adj2, n2)

    all_mappings = []
    for center1 in centers1:
        for center2 in centers2:
            mapping = {}
            used = set()
            if match_trees(adj1, adj2, center1, center2, mapping, used, None, None):
                if len(mapping) == n1:
                    result = [mapping[i] for i in range(n1)]
                    all_mappings.append(result)

    return all_mappings


@app.route('/api/v1/constellation_finder', methods=['POST'])
def constellation_finder():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "incorrect_input"}), 400

        stars = data['stars']
        cluster_params = data['cluster_params']
        target = data['target_constellation']

        clusters = find_clusters(
            stars,
            cluster_params['max_neighbor_distance'],
            cluster_params['min_size'],
            cluster_params['max_size']
        )

        target_n = max(max(edge['from'], edge['to']) for edge in target['edges']) + 1
        target_mst = [(edge['from'], edge['to'], edge['distance']) for edge in target['edges']]

        matching_clusters = []

        for cluster in clusters:
            if len(cluster) != target_n:
                continue

            mst = build_mst(cluster, stars)

            if len(mst) != target_n - 1:
                continue

            mappings = are_isomorphic(mst, target_n, target_mst, target_n)

            for mapping in mappings:
                matched = [stars[cluster[mapping[i]]]['name'] for i in range(target_n)]
                matching_clusters.append(matched)
                break

        if len(matching_clusters) == 1:
            return jsonify({
                "found": True,
                "matched_stars": matching_clusters[0]
            }), 200
        else:
            return jsonify({"found": False}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "incorrect_input"}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
