#### Module 7 (OAD) — Systems Integration & Architectural Coordination

**Purpose**
Ensure that each design version is **compatible with existing infrastructure, interfaces, resource flows, safety envelopes, and federated design standards** before it is optimized, certified, or deployed.

**Role in the system**
A design does not exist in isolation. This module ensures that:

- new designs **physically fit** into real environments,
- resource flows (energy, water, waste, heat, data) are **compatible**,
- interfaces match **OAD-certified standards**,
- safety clearances and code-like constraints are respected,
- and where possible, **circular resource loops** are enabled.

Systemically, this module prevents:

- siloed, incompatible designs,
- infrastructure dead-ends,
- unsafe integration into buildings or networks,
- and hidden coupling failures between subsystems.

For **COS**, it prevents scheduling work that will fail at install time. For **ITC**, it prevents incorrect valuation of designs that quietly impose integration penalties or hidden retrofit labor.

**Inputs**

- `DesignVersion`
- `SimulationResult` (Module 5)
- `LifecycleModel` (Module 4)
- Node-specific infrastructure descriptors:
  - power systems,
  - water systems,
  - waste systems,
  - spatial/architectural envelopes,
  - tooling & fabrication capabilities,
  - standard interface registries.

**Outputs**

- An `IntegrationCheck` object containing:
  - `compatible_systems`
  - `conflicts`
  - `circular_loops`
  - `integration_score`

These outputs directly influence:

- COS deployment planning,
- downstream optimization priorities (Module 8),
- final certification (Module 9),
- and long-term FRS telemetry mapping.

***

**Reminder: Integration Type**

From the OAD intro:

```python
@dataclass
class IntegrationCheck:
    """
    Compatibility and systems-architecture evaluation.
    """
    version_id: str
    compatible_systems: List[str]
    conflicts: List[str]
    circular_loops: List[str]
    integration_score: float  # 0–1
```

**Core Logic**

We assume a **node integration registry** describing what systems currently exist and what interface standards they expose.

1. Example Node Infrastructure Registry

```python
NODE_SYSTEM_REGISTRY = {
    "power": {
        "available": True,
        "voltage_standards": [24, 48, 120],
        "renewable_fraction": 0.85,
        "waste_heat_recovery": True,
    },
    "water": {
        "rain_capture": True,
        "greywater_loop": True,
        "potable_header_pressure_bar": 2.5,
    },
    "waste": {
        "composting": True,
        "biogas": False,
        "hazardous_handling": "limited",
    },
    "fabrication": {
        "max_machine_envelope_m": 2.0,
        "supports_welding": True,
        "supports_composites": True,
        "supports_5axis_machining": False,
    },
    "building_codes": {
        "max_floor_load_kg_m2": 500,
        "min_clearance_mm": 900,
    },
}
```

2. Interface Compatibility Checks

```python
def check_interface_compatibility(
    version: DesignVersion,
    node_registry: Dict,
) -> List[str]:
    """
    Identify conflicts between the design's interface needs and
    existing node infrastructure capabilities.
    """
    conflicts = []

    # Power compatibility
    if version.parameters.get("requires_power", False):
        req_voltage = version.parameters.get("required_voltage")
        if req_voltage not in node_registry["power"]["voltage_standards"]:
            conflicts.append(f"Power voltage {req_voltage}V not supported.")

    # Fabrication envelope
    envelope_req = version.parameters.get("max_part_dimension_m", 0)
    envelope_available = node_registry["fabrication"]["max_machine_envelope_m"]
    if envelope_req > envelope_available:
        conflicts.append("Part exceeds local machine envelope.")

    # Specialized manufacturing
    if version.parameters.get("requires_5axis_machining", False):
        if not node_registry["fabrication"]["supports_5axis_machining"]:
            conflicts.append("5-axis machining not available locally.")

    # Floor load
    floor_load = version.parameters.get("installed_load_kg_m2", 0)
    if floor_load > node_registry["building_codes"]["max_floor_load_kg_m2"]:
        conflicts.append("Installed floor load exceeds building limits.")

    return conflicts
```

3. Resource Flow & Circularity Detection

```python
def detect_circular_resource_loops(
    version: DesignVersion,
    node_registry: Dict,
) -> List[str]:
    """
    Identify opportunities for circular integration:
    waste heat, greywater reuse, material recovery, etc.
    """
    loops = []

    if version.parameters.get("waste_heat_output_w", 0) > 0:
        if node_registry["power"]["waste_heat_recovery"]:
            loops.append("Waste heat can feed building heat exchanger.")

    if version.parameters.get("greywater_output_lph", 0) > 0:
        if node_registry["water"]["greywater_loop"]:
            loops.append("Greywater can be reintegrated into irrigation loop.")

    if version.parameters.get("organic_waste_output", False):
        if node_registry["waste"]["composting"]:
            loops.append("Organic waste suitable for composting loop.")

    return loops
```

4. Integration Scoring

```python
def compute_integration_score(
    conflicts: List[str],
    circular_loops: List[str],
    base_score: float = 1.0,
) -> float:
    """
    Penalize conflicts and reward circular integration.
    """
    penalty = 0.2 * len(conflicts)
    bonus = 0.05 * len(circular_loops)

    score = base_score - penalty + bonus
    return max(0.0, min(1.0, score))
```

5. Main Integration Evaluator

```python
def evaluate_system_integration(
    version: DesignVersion,
    node_registry: Dict,
) -> IntegrationCheck:
    """
    OAD Module 7 — Systems Integration & Architectural Coordination
    ---------------------------------------------------------------
    """
    conflicts = check_interface_compatibility(version, node_registry)
    circular_loops = detect_circular_resource_loops(version, node_registry)

    compatible_systems = []
    if not conflicts:
        compatible_systems = list(node_registry.keys())

    integration_score = compute_integration_score(
        conflicts=conflicts,
        circular_loops=circular_loops,
    )

    return IntegrationCheck(
        version_id=version.id,
        compatible_systems=compatible_systems,
        conflicts=conflicts,
        circular_loops=circular_loops,
        integration_score=integration_score,
    )
```

***

**Math Sketch — Integration Scoring**

Let:
- $C$ = number of **integration conflicts**
- $L$ = number of **circular loop opportunities** discovered

Define:

$$I = \text{clamp}\big( 1 - \alpha C + \beta L \big)$$

Where:
- $\alpha$ = penalty weight per conflict (e.g., 0.2)
- $\beta$ = reward weight per circular loop (e.g., 0.05)

Thus:
- A design with **many interface conflicts** is strongly penalized.
- A design that enables **resource circularity** is softly rewarded.
- Final score $I \in [0,1]$ gives a clean compatibility signal.

---

**Interpretation in Plain Language**

> Module 7 answers: *"Does this thing actually fit into the world we are trying to build?"*

It prevents:
- COS from planning impossible installs,
- ITC from mis-valuing goods that secretly demand extra retrofits,
- and OAD from certifying designs that only work in abstract isolation.

Designs that integrate cleanly, enable circular reuse, and respect real spatial and infrastructure limits become **preferred templates** across the federation.
