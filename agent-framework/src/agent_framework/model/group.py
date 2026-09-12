"""Organizational Groups containing mixed primitive IDs and nested Group IDs."""

from collections import deque
from collections.abc import Collection
from dataclasses import dataclass

from .schema import _validate_id, _validate_ids


@dataclass(frozen=True, slots=True, kw_only=True)
class Group:
    id: str
    description: str
    members: tuple[str, ...] = ()
    subgroups: tuple[str, ...] = ()


def validate_group(group: Group) -> None:
    _validate_id(group.id, "group")
    _validate_ids(group.members, f"group {group.id!r} members")
    _validate_ids(group.subgroups, f"group {group.id!r} subgroups")


def validate_groups(groups: tuple[Group, ...], members: Collection[str]) -> None:
    """Validate references and reject cycles in O(groups + references) time.

    Shared subgroups are permitted. This build-time check can also be used by
    later resolution; it does not implement resolution or Group behavior.
    """
    by_id: dict[str, Group] = {}
    for group in groups:
        validate_group(group)
        if group.id in by_id:
            raise ValueError(f"duplicate group ID {group.id!r}")
        by_id[group.id] = group
    member_ids = set(members)
    indegree = dict.fromkeys(by_id, 0)
    for group in groups:
        for member in group.members:
            if member not in member_ids:
                raise ValueError(f"group {group.id!r}: unknown member {member!r}")
        for child in group.subgroups:
            if child not in by_id:
                raise ValueError(f"group {group.id!r}: unknown subgroup {child!r}")
            indegree[child] += 1
    ready = deque(name for name, count in indegree.items() if count == 0)
    visited = 0
    while ready:
        name = ready.popleft()
        visited += 1
        for child in by_id[name].subgroups:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(groups):
        raise ValueError("group cycle detected")
