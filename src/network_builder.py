
import numpy as np
import networkx as nx
from seirsplus.models import SEIRSNetworkModel
import random
import itertools
import yaml
from .utils import add_cumulative_weight, safe_sample, export_to_json



# read in variables from config.yml
def load_config(path="config/simulation_config.yml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


# build cruise network based on config
class CruiseNetwork: 
    def __init__(self, cfg: dict):
        self.population_cfg = cfg.get('population', {})
        self.facility_cfg = cfg.get('facilities', {})
        
        # population variables
        self.n_passengers = int(self.population_cfg['n_passengers'])
        self.passenger_crew_ratio = float(self.population_cfg['passenger_crew_ratio'])
        self.n_crew = int(self.n_passengers / self.passenger_crew_ratio)

        self.cabin_size_min = self.population_cfg['cabin_size_min']
        self.cabin_size_max = self.population_cfg['cabin_size_max']

        self.n_total = self.n_passengers + self.n_crew

        self.seed = self.population_cfg['seed']


        self.G_normal = None
        self.G_quarantine = None


    
    def assign_cabins(self): 
        random.seed(self.seed)
        passengers = list(range(self.n_passengers))
        random.shuffle(passengers)

        cabins = []
        idx = 0

        while idx < self.n_passengers:
            cabin_size = random.randint(self.cabin_size_min,
                                        self.cabin_size_max)

            cabin_members = passengers[idx: idx + cabin_size]

            # handle last partial cabin
            if len(cabin_members) < self.cabin_size_min:
                cabins[-1].extend(cabin_members)
                break

            cabins.append(cabin_members)
            idx += cabin_size

        return cabins


    def build_cruise_network(self) -> nx.Graph :
        random.seed(self.seed) # for reproducibility
        """
        Set the high-level cruise occupant parameters to correspond to industry averages

        Graph below establishes connections based on:
        - Shared cabins between passengers
        - Shared decks between passengers
        - Shared dinner table between passengers
        - Crew-to-passenger interactions
        - Shared cabins between crew
        - Shared workspaces between crew

        The weights are based on my take on interaction frequency - happy to tweak as necessary

        Layers to add (optional)"
        - Age demographics (will increase complication for other elements of the simulation)
        """

        G = nx.Graph()

        passengers = list(range(self.n_passengers))
        crew = list(range(self.n_passengers, self.n_total))
        total = passengers + crew

        n_passengers = len(passengers)
        total_nodes = self.n_total

        G.add_nodes_from(total)

        cabins = self.assign_cabins()

        crew_ids = list(range(n_passengers, total_nodes))
        

        # Adding labels and assign cabin for each passenger
        for cabin_id, members in enumerate(cabins):
            for p in members: 
                G.nodes[p]['type'] = 'passenger'
                G.nodes[p]['cabin_id'] = cabin_id
                G.nodes[p]['age'] = random.randint(0, 80) # randomly assign age from 0 to 80

        n_service = int(0.33 * self.n_crew)  # crew label
        service_set = set(crew[:n_service])

        # Adding labels and categories for each crew member
        for i in crew:
            G.nodes[i]['type'] = 'crew'
            G.nodes[i]['crew_type'] = 'passenger_service' if i in service_set else 'non_service'
            G.nodes[i]['age'] = random.randint(18, 50) # randomly assign age from 18 to 50


        # Add direct contact between cabin members
        for members in cabins: 
            duration = random.uniform(360, 480) # one shared cabin contact duration
            for p, q in itertools.combinations(members,2):
                add_cumulative_weight(G, p, q, duration, "cabin")

        service_crew = [i for i in crew_ids if G.nodes[i]['crew_type'] == 'passenger_service']


        # Creating the dining cohorts
        n_cohorts = 9
        waiters_for_dining = [c for i, c in enumerate(service_crew) if i < len(service_crew) * 0.5]
        waiters_per_cohort = len(waiters_for_dining) // 9
        cohort_size = n_passengers // n_cohorts

        for cohort_num in range(n_cohorts):
            start = cohort_num * cohort_size
            end = (cohort_num + 1) * cohort_size if cohort_num < n_cohorts - 1 else n_passengers
            cohort_passengers = list(range(start, end))

            # assign waiters
            w_start = cohort_num * waiters_per_cohort
            w_end = (cohort_num + 1) * waiters_per_cohort
            cohort_waiters = waiters_for_dining[w_start:w_end]

            # Creating tables of 8 passengers each, randomly assigned
            random.shuffle(cohort_passengers)

            # passenger dining weight
            for i in range(0, len(cohort_passengers), 8):
                table = cohort_passengers[i:i+8]
                duration = random.uniform(35, 90) # average dining time around 67 mins
                for u, v in itertools.combinations(table, 2):
                    add_cumulative_weight(G, u, v, duration, 'dining')
            
                # waiter - passenger interactions
                if cohort_waiters: 
                    table_waiter = safe_sample(cohort_waiters, 1)[0]
                    for passenger in table: 
                        service_duration = random.uniform(5, 20)
                        add_cumulative_weight(G, table_waiter, passenger, service_duration, 'dining')


        # Creating deck-level groups for moderate interaction
        n_decks = 17
        deck_contacts = int(self.population_cfg.get('deck_contacts',3))

        passengers_per_deck = max(1, n_passengers // n_decks)
        for i in range(n_passengers):
            G.nodes[i]["deck"] = min(n_decks - 1, i // passengers_per_deck)

        for deck_num in range(n_decks):
            deck_passengers = [i for i in range(n_passengers) if G.nodes[i]["deck"] == deck_num]
            if len(deck_passengers) < 2:
                continue

            for u in deck_passengers:
                partners = safe_sample([x for x in deck_passengers if x != u], deck_contacts)
                for v in partners:
                    duration = random.uniform(10, 240)
                    add_cumulative_weight(G, u, v, duration, "deck")
                        

        # Creating transient connections between passengers across the whole ship
        for i in range(self.n_total):
            contacts = safe_sample(list(range(self.n_total)), int(self.population_cfg.get("transient_contacts", 2)))
            for j in contacts:
                if i != j:
                    duration = random.uniform(0, 15) # short encounter
                    add_cumulative_weight(G,i,j,duration,'transient')


        # Connecting passenger_service crew to passengers
        for i in range(n_passengers, total_nodes):
            if G.nodes[i]['crew_type'] == 'passenger_service':
                served_passengers = safe_sample(range(n_passengers), 50)
                for p in served_passengers:
                    duration = random.uniform(0, int(self.population_cfg.get("service_contacts", 35))) # short service
                    add_cumulative_weight(G,i,p,duration, 'service crew contact')


        # Adding weak connection between non-service crew and passengers
        for i in range(n_passengers, total_nodes):
            if G.nodes[i]['crew_type'] == 'non_service':
                served_passengers = safe_sample(range(n_passengers), 10)
                for p in served_passengers:
                    duration = random.uniform(0, 20) # rare encounter
                    add_cumulative_weight(G,i,p,duration, 'non-service crew contact')


        # Adding crew-to-crew edges (cabinmates and shared category)
        for i in range(0, len(crew_ids), 2):
            cabin = crew_ids[i:i+2]
            if len(cabin) == 2:
                duration = random.uniform(360, 480)
                a, b = cabin
                add_cumulative_weight(G, a, b, duration, contact_type='crew_cabin')

        service_crew = [i for i in crew_ids if G.nodes[i]['crew_type'] == 'passenger_service']
        non_service_crew = [i for i in crew_ids if G.nodes[i]['crew_type'] == 'non_service']

        crew_peers = int(self.population_cfg.get("crew_peers", 10))

        for crew_group in [service_crew, non_service_crew]:
            for u in crew_group:
                peers = safe_sample(crew_group, crew_peers)
                for v in peers:
                    duration = random.uniform(30, 120) # less than sharing cabins
                    add_cumulative_weight(G,u,v,duration, contact_type='crew contact')


        # intergroup contacts
        cross_peers = int(self.population_cfg.get("crew_cross_peers", 5))
        for u in service_crew: 
            mixed_partners = safe_sample(non_service_crew, cross_peers)
            for v in mixed_partners: 
                duration = random.uniform(10, 30)
                add_cumulative_weight(G,u,v,duration, contact_type='crew contact')

        # adding shared facilities 
        shared_facilities = self.facility_cfg

        eligible_crew = [i for i in crew_ids if G.nodes[i]['crew_type'] == 'passenger_service' 
                 or random.random() < 0.5] # 50% of non-service also visit facilities

        eligible_nodes = passengers + eligible_crew

        k_fac = int(self.population_cfg.get("facility_k_per_node", 2))

        for facility_name, desc in shared_facilities.items():
            for _ in range(int(desc["count"]) * int(desc["repeats"])):
                size = min(int(desc["size"]), len(eligible_nodes))
                group = safe_sample(eligible_nodes, size)
                if len(group) < 2:
                    continue

                for u in group:
                    partners = safe_sample([x for x in group if x != u], k_fac)
                    for v in partners:
                        duration = random.uniform(desc["duration"][0], desc["duration"][1])
                        add_cumulative_weight(G, u, v, duration, contact_type=f"facility:{facility_name}")  


        return G, n_passengers
    
def get_top_weight_graph(G, min_edge_weight = 0.08):
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))

    for u, v, d in G.edges(data=True):
        if d.get("weight", 0) >= min_edge_weight:
            H.add_edge(u, v, **d)

    isolates = list(nx.isolates(H))
    H.remove_nodes_from(isolates)

    return H


    

if __name__ == "__main__":
    from pathlib import Path

    cfg_path = Path("config/simulation_config.yml")
    cfg = yaml.safe_load(cfg_path.read_text())

    cn = CruiseNetwork(cfg)
    G, n_passengers = cn.build_cruise_network()

    # visualization purpose - removed isolated groups and low weight nodes
    H = get_top_weight_graph(G)

    print("nodes:", G.number_of_nodes())
    print("edges:", G.number_of_edges())
    print("avg_degree:", sum(dict(G.degree()).values()) / G.number_of_nodes())
    print()


    print("reduced graph nodes:", H.number_of_nodes())
    print("reduced graph edges:", H.number_of_edges())
    print("reduced graph avg_degree:", sum(dict(H.degree()).values()) / H.number_of_nodes())

    export_to_json(H)