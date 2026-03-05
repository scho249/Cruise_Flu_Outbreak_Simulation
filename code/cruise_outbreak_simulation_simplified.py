import numpy as np
import networkx as nx
from seirsplus.models import SEIRSNetworkModel
import random

class CruiseSimulation:
    
    def __init__(self, n_people: int = 3700):
        # Calculate passengers and crew (roughly 70% passengers, 30% crew)
        self.n_passengers = int(n_people * 0.7)
        self.n_crew = n_people - self.n_passengers
        self.n_people = n_people  # Keep for compatibility
        self.n_total = n_people
        self.results = {}
        
        self.config = {
            'transmission_rate': 0.8,
            'infectious_days': 7,
            'incubation_days': 5,
            'mortality_rate': 0.013,  # 1.3% - constant across all scenarios
            'vaccine_1dose_efficacy': 0.70,
            'vaccine_2dose_efficacy': 0.95,
            'quarantine_effectiveness': 0.8,  # 80% transmission reduction
        }
        
        self.G_normal = None
        self.G_quarantine = None
        
        print(f"🚢 Cruise Intervention Simulation: {n_people:,} people")
        print(f"   {self.n_passengers:,} passengers, {self.n_crew:,} crew")
    
    def build_cruise_network(self) -> nx.Graph:
        random.seed(123)
        G = nx.Graph()
        
        # Add nodes with crew/passenger distinction
        passengers = list(range(self.n_passengers))
        crew = list(range(self.n_passengers, self.n_total))
        
        # Add passenger nodes
        for p in passengers:
            G.add_node(p, type='passenger', cabin=p//2)
        
        # Add crew nodes
        for c in crew:
            G.add_node(c, type='crew', cabin=(c-self.n_passengers)//2)
        
        # 1. HIGH RISK: Cabin pairs (closest contacts)
        # Passenger cabins (2 per cabin)
        for i in range(0, self.n_passengers, 2):
            if i+1 < self.n_passengers:
                G.add_edge(i, i+1, weight=1.0, contact_type='cabin')
        
        # Crew cabins (2 per cabin)  
        for i in range(self.n_passengers, self.n_total, 2):
            if i+1 < self.n_total:
                G.add_edge(i, i+1, weight=1.0, contact_type='cabin')
        
        # 2. MEDIUM RISK: Dining/social groups (8 people each)
        # Passenger dining groups
        passengers_list = list(range(self.n_passengers))
        random.shuffle(passengers_list)
        for group in range(self.n_passengers // 8):
            start = group * 8
            members = passengers_list[start:start+8]
            for i in range(len(members)):
                for j in range(i+1, len(members)):
                    G.add_edge(members[i], members[j], weight=0.5, contact_type='social')
        
        # Crew work groups (higher contact weight since they work together)
        crew_list = list(range(self.n_passengers, self.n_total))
        random.shuffle(crew_list)
        for group in range(len(crew_list) // 8):
            start = group * 8
            members = crew_list[start:start+8]
            for i in range(len(members)):
                for j in range(i+1, len(members)):
                    G.add_edge(members[i], members[j], weight=0.7, contact_type='work')  # Higher weight for work
        
        # Passenger-crew service interactions (medium risk)
        for crew_member in crew[:len(crew)//3]:  # 1/3 of crew serve passengers
            served_passengers = random.sample(passengers, random.randint(8, 15))
            for passenger in served_passengers:
                G.add_edge(crew_member, passenger, weight=0.3, contact_type='service')
        
        # 3. LOW RISK: Random encounters (2 per person)
        for person in range(self.n_total):
            possible_contacts = [p for p in range(self.n_total) if p != person]
            contacts = random.sample(possible_contacts, 2)
            for contact in contacts:
                if not G.has_edge(person, contact):
                    G.add_edge(person, contact, weight=0.1, contact_type='random')
        
        print(f"✅ Normal network: {G.number_of_edges():,} connections")
        print(f"   Passengers: {self.n_passengers:,}, Crew: {self.n_crew:,}")
        return G
    
    def build_quarantine_network(self) -> nx.Graph:
        """Build quarantine network - cabin isolation only."""
        random.seed(123)
        G_Q = nx.Graph()
        
        # Add all nodes with same attributes
        for node, data in self.G_normal.nodes(data=True):
            G_Q.add_node(node, **data)
        
        # Only keep cabin connections during quarantine (complete isolation to cabins)
        for i in range(0, self.n_total, 2):
            if i+1 < self.n_total:
                G_Q.add_edge(i, i+1, weight=1.0, contact_type='cabin')
        
        print(f"✅ Quarantine network: {G_Q.number_of_edges():,} connections "
              f"({(1-G_Q.number_of_edges()/self.G_normal.number_of_edges())*100:.1f}% reduction)")
        return G_Q
    
    def run_scenario(self, scenario_name: str, network: nx.Graph, effective_transmission: float) -> dict:
        """Run a single simulation scenario."""
        print(f"🧪 Running {scenario_name}...")
        
        # SEIRS parameters
        gamma = 1 / self.config['infectious_days']
        sigma = 1 / self.config['incubation_days']
        
        # Initialize model
        model = SEIRSNetworkModel(
            G=network,
            beta=effective_transmission,
            sigma=sigma,
            gamma=gamma,
            mu_I=self.config['mortality_rate'] * gamma,
            initI=100,  # Start with outbreak in progress
            initE=20
        )
        
        # Run simulation
        model.run(T=60)
        
        # Extract results (use working S, E, I from SEIRS+)
        time = model.tseries
        S, E, I = model.numS, model.numE, model.numI
        
        # Manual R, F calculation (only because SEIRS+ is buggy)
        R, F = self._calculate_outcomes(time, I)
        
        total_infected = R[-1] + F[-1] + I[-1]
        attack_rate = total_infected / self.n_people * 100
        
        return {
            'time': time, 'S': S, 'E': E, 'I': I, 'R': R, 'F': F,
            'attack_rate': attack_rate,
            'peak_infections': np.max(I),
            'total_infected': total_infected,
            'deaths': F[-1]
        }
    
    def _calculate_outcomes(self, time, I):
        dt = np.diff(time, prepend=time[0])
        R, F = np.zeros_like(time), np.zeros_like(time)
        
        recovery_rate = 1 / self.config['infectious_days']
        death_rate = self.config['mortality_rate'] * recovery_rate
        
        for i in range(1, len(time)):
            R[i] = R[i-1] + I[i-1] * recovery_rate * dt[i]
            F[i] = F[i-1] + I[i-1] * death_rate * dt[i]
        
        return R, F
    
    def run_all_scenarios(self):
        # Build networks
        self.G_normal = self.build_simple_network()
        self.G_quarantine = self.build_quarantine_network()
        
        base_transmission = self.config['transmission_rate']
        
        # 1. Baseline (no interventions)
        self.results['baseline'] = self.run_scenario(
            'Baseline', self.G_normal, base_transmission)
        
        # 2. Quarantine intervention (reduced transmission + limited network)
        quarantine_transmission = base_transmission * (1 - self.config['quarantine_effectiveness'])
        self.results['quarantine'] = self.run_scenario(
            'Quarantine', self.G_quarantine, quarantine_transmission)
        
        # 3. One dose for all (70% efficacy for everyone)
        eff_trans_1dose = base_transmission * (1 - self.config['vaccine_1dose_efficacy'])
        self.results['vaccination_1dose'] = self.run_scenario(
            'One Dose All', self.G_normal, eff_trans_1dose)
        
        # 4. Two doses for half (95% efficacy for 50%, 0% for other 50%)
        eff_trans_2dose = base_transmission * (0.5 * (1 - self.config['vaccine_2dose_efficacy']) + 0.5 * 1.0)
        self.results['vaccination_2dose'] = self.run_scenario(
            'Two Dose Half', self.G_normal, eff_trans_2dose)
    
    def print_summary(self):
        """Print comprehensive intervention comparison results."""
        print("\n" + "="*70)
        print("🎯 CRUISE SHIP INTERVENTION COMPARISON RESULTS")
        print("="*70)
        
        baseline = self.results['baseline']['total_infected']
        
        print(f"\n📊 ATTACK RATE OUTCOMES:")
        for scenario, results in self.results.items():
            print(f"   {scenario.replace('_', ' ').title():20s}: {results['attack_rate']:6.1f}% attack rate")
        
        print(f"\n💪 INTERVENTION EFFECTIVENESS:")
        for scenario, results in self.results.items():
            if scenario == 'baseline':
                continue
            prevented = baseline - results['total_infected']
            effectiveness = prevented / baseline * 100
            print(f"   {scenario.replace('_', ' ').title():20s}: {prevented:6.0f} infections prevented ({effectiveness:.1f}%)")
        
        # Find best intervention
        best_scenario = min([s for s in self.results.keys() if s != 'baseline'], 
                           key=lambda s: self.results[s]['attack_rate'])
        best_prevented = baseline - self.results[best_scenario]['total_infected']
        
        print(f"\n🏆 BEST INTERVENTION:")
        print(f"   {best_scenario.replace('_', ' ').title()}")
        print(f"   Prevents {best_prevented:.0f} infections ({best_prevented/baseline*100:.1f}% reduction)")
        
        # Quarantine vs Vaccination comparison
        quarantine_prevented = baseline - self.results['quarantine']['total_infected']
        vacc1_prevented = baseline - self.results['vaccination_1dose']['total_infected']
        vacc2_prevented = baseline - self.results['vaccination_2dose']['total_infected']
        
        print(f"\n🔄 INTERVENTION COMPARISON:")
        print(f"   Quarantine:        {quarantine_prevented:6.0f} infections prevented")
        print(f"   One dose for all:  {vacc1_prevented:6.0f} infections prevented")
        print(f"   Two dose for half: {vacc2_prevented:6.0f} infections prevented")
        
        if vacc1_prevented > vacc2_prevented:
            print(f"   📋 Vaccination: One dose strategy is {vacc1_prevented-vacc2_prevented:.0f} infections better")
        else:
            print(f"   📋 Vaccination: Two dose strategy is {vacc2_prevented-vacc1_prevented:.0f} infections better")
        
        print(f"\n📋 SIMULATION DETAILS:")
        print(f"   Population: {self.n_people:,} people")
        print(f"   Network: {self.G_normal.number_of_edges():,} normal connections")
        print(f"   Quarantine: {self.G_quarantine.number_of_edges():,} connections (cabin only)")
        print(f"   CFR: {self.config['mortality_rate']*100:.1f}% (constant across all scenarios)")
        print("="*70)


def main():
    """Run the complete intervention comparison simulation."""
    print("🚢 CRUISE SHIP INTERVENTION COMPARISON SIMULATION")
    print("="*55)
    print("Comparing: Baseline vs Quarantine vs Vaccination Strategies")
    print("Simplified network, comprehensive intervention analysis")
    print("")
    
    # Run simulation
    sim = SimpleCruiseSimulation()
    sim.run_all_scenarios()
    
    # Results
    sim.print_summary()
    
    print(f"\n✅ SIMULATION COMPLETE!")
    print(f"   Code: {__file__}")
    
    return sim


if __name__ == "__main__":
    simulation = main() 