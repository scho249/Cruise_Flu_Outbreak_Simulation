# Cruise Disease Outbreak Simulation

## Overview

Cruise ships are environments with extremely high population density and frequent close interactions between individuals. These conditions make them particularly vulnerable to infectious disease outbreaks.

This project explores how respiratory diseases (such as influenza or COVID-19) can spread in a cruise ship environment by simulating person-to-person transmission on a dynamic contact network.

The motivation for this project originated from a simple question: **why do people often get sick after returning from cruise trips?**  
The modeling framework developed here can also be applied to other dense environments such as airports, conferences, or large public events.

---

## Key Features

### Network-Based Epidemic Model (SEIRS+)

The simulation uses the **SEIRS+ framework**, which models disease dynamics at the individual level.

Each individual in the population transitions between epidemiological states:

- **S** — Susceptible  
- **E** — Exposed  
- **I** — Infected  
- **R** — Recovered  
- **F** — Fatal  

The model operates on a **contact network**, where edges represent interactions between individuals and edge weights represent cumulative exposure time.

---

### Dynamic Contact Graphs

Two primary contact networks are generated.

#### Base Network (G)

Represents normal cruise operations with high interaction density.

Contact types include:

- Cabin contacts
- Dining/social interactions
- Deck interactions
- Transient encounters
- Passenger–crew service interactions
- Crew–crew interactions
- Shared facility usage (e.g., elevators, lounges, pools)

Edge weights reflect **cumulative contact duration**, which affects transmission probability.

---

#### Quarantine Network (G_Q)

Represents restricted interactions after quarantine protocols are implemented.

Characteristics:

- Passengers limited to cabinmates
- Crew interactions significantly reduced
- Minimal cross-group contacts

This network models the impact of strict containment strategies.

---

## Network Structure

The simulated environment includes:

- **~1400 individuals**
  - ~1000 passengers
  - ~400 crew members
- **~18,000–50,000 contact edges** depending on filtering
- Multiple structured interaction layers including:
  - cabins
  - dining cohorts
  - deck-level mixing
  - service interactions
  - shared facilities

This structure captures the **heterogeneous mixing patterns** typical in cruise environments.

---

## Parameter Calibration

Model parameters are informed by:

- The **Diamond Princess COVID-19 outbreak (2020)**
- Published epidemiological studies
- Reasonable assumptions for cruise ship interaction patterns

Key parameters include:

| Parameter | Description |
|----------|-------------|
| **BETA** | Transmission rate |
| **SIGMA** | Progression rate from exposed → infected |
| **GAMMA** | Recovery rate |
| **MU_I** | Infection-related mortality |
| **G_quarantine** | Contact network used during quarantine |
| **theta_E** | Testing rate for exposed individuals |
| **theta_I** | Testing rate for infected individuals |
| **initI** | Initial number of infected individuals |

---

## Simulation Scenarios

The project evaluates several intervention strategies.

### 1. Baseline

No mitigation measures.  
Transmission occurs across the full network.

### 2. Complete Quarantine

Passengers are isolated within their cabins, dramatically reducing cross-contact.

### 3. Universal Single-Dose Vaccination

Entire population receives a single-dose vaccine.

Assumptions:

- 70% vaccine effectiveness
- 50% reduction in susceptibility
- 40% reduction in transmission rate

### 4. Two-Dose Vaccination (Partial Coverage)

50% of the population receives a second vaccine dose.

- Higher individual protection
- Lower population coverage

---

## Visualization

The generated network can be visualized using **D3.js**.

Features include:

- Interactive force-directed graph
- Filtering by contact layer (e.g., dining, crew contact, facility usage)
- Subgraph rendering for specific interaction types

Example visualization layers:

- Dining contacts
- Crew interactions
- Facility-based interactions
- Transient encounters

---

## Project Structure
