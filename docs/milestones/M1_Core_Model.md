# M1: Core Model

## Goal

Implement and test the technology-independent model.

## Implement

- Agent
- Property
- Capability
- Channel
- Constraint
- Group
- PayloadSchema
- required enums
- explicit validation functions

## Required Tests

- mixed Group containing Property and Capability members,
- nested Groups and cycle rejection,
- multiple Channels on one Capability,
- sensing Capability with continuous output stream,
- sensing invocation with one-time result,
- contract-static Property with no runtime Channel,
- constraints targeting valid model elements,
- correlated request/response Channels.

## Do Not Implement

- binding discovery,
- YAML parsing,
- ROS2,
- code generation,
- runtime communication.
