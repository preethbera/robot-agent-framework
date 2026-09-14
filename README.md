# Agent Framework

**Agent Framework** is a production-grade robotics framework that abstracts hardware, communication, and middleware complexities (such as ROS2 and PX4) behind a clean, auto-generated Python API. 

It allows developers to write a single **Agent Definition** (YAML), select reusable bindings, and automatically resolve the agent's capabilities into a robust runtime API. Applications interact purely with the generated Python API without needing to know anything about the underlying ROS2 nodes, QoS profiles, sensor drivers, or flight controllers.

## Core Features

- **Declarative Agent Definitions:** Define your robot's Properties (state/info) and Capabilities (functions/sensors) in a technology-agnostic YAML file.
- **Auto-Generated Python API:** The framework parses your definition and generates a fully typed Python API for controlling your agent.
- **Reusable Bindings:** Hardware and technology specifics (e.g., PX4) are isolated into independent binding packages.
- **ROS2 Realization:** Automatically constructs the ROS2 communication topology, mapping logical channels to physical endpoints without manual configuration.
- **Multi-Agent Support:** Built-in deployment systems to handle multiple instances of the same agent or different agents seamlessly.

## Repository Structure

This repository provides the core framework and hardware bindings:

- `agent-framework/` - The core Python library, resolver, and API generator.
- `bindings/` - Independent technology bindings (e.g., PX4) that bridge the framework to hardware/simulation.

When you install and use this framework in your own project, you will create your own workspace to house your YAML agent definitions and deployment configurations.

## Usage Overview

### 1. Define Your Agent
Create an Agent Definition (`.yaml`) describing the physical and software capabilities of your robot.

```yaml
# agents/my_drone/agent.yaml
name: my_drone
version: 1.0.0
bindings:
  - agent-binding-px4
capabilities:
  flight_control:
    type: px4.offboard
```

### 2. Generate the API
Run the framework resolver and generator on your agent definition. This analyzes the requested bindings, determines the ROS2 realization, and compiles a Python module specifically tailored to your drone.

### 3. Build Your Application
Import your generated API and write your control application natively in Python. The framework handles all underlying ROS2 communication under the hood.

```python
from agent_framework.deployment import create_instance

# Example usage of the generated API
def execute_flight(agent):
    agent.arm()
    agent.offboard.takeoff(z=-3.0)
    agent.land()
```
