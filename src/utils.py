import numpy as np
import networkx as nx
import random
import json


# Convert cumulative contact duration to saturated risk weight
def add_saturation_weight(duration_min, total_duration_min=180):
    duration_days = duration_min / (24 * 60)  
    total_days = total_duration_min / (24 * 60)
    return 1 - np.exp(-duration_days / total_days)
        

# Creating function to default to max edge weight for overlapping connections
def add_cumulative_weight(G:nx.Graph, u, v, duration, contact_type):
    if not G.has_edge(u, v):
        G.add_edge(u, v, cum_duration=0.0, contact_types=set(), duration_by_type={})

    G[u][v]["cum_duration"] += float(duration)
    G[u][v]["contact_types"].add(contact_type)

    d = G[u][v]["duration_by_type"]
    d[contact_type] = d.get(contact_type, 0.0) + float(duration)

    cum = float(G[u][v]["cum_duration"])
    G[u][v]["weight"] = add_saturation_weight(cum)


# return safe guarded sample 
def safe_sample(population, k):
        k = min(k, len(population))
        return random.sample(population, k)


def export_to_json(G:nx.Graph, output_path='results/network_graph.json'):
    nodes = []
    for n,d in G.nodes(data=True): 
        node = {"id": n}
        node.update(d)
        nodes.append(node)

    edges = []
    for u,v,d in G.edges(data=True): 
        edges.append({"source": u, "target": v, "weight":d.get("weight",0), "contact_type":list(d.get("contact_types",[]))})

    data = {"nodes": nodes, "links": edges}

    with open(output_path, 'w') as f: 
         json.dump(data, f, indent=2)

    print("exported to: ", output_path)
          