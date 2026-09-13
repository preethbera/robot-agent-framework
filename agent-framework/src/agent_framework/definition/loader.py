"""Safe YAML 1.2 loading at build time; never imported on the message path."""

from hashlib import sha256
from pathlib import Path

from .errors import DefinitionError
from .model import AgentDefinition
from .validation import parse_structure

MAX_DEFINITION_BYTES = 1_048_576


def parse_agent_definition(text: str) -> AgentDefinition:
    # Lazy dependency keeps installation/import of core semantics ROS/YAML-free.
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    from ruamel.yaml.events import CollectionEndEvent, CollectionStartEvent, DocumentStartEvent

    encoded = text.encode("utf-8")
    if len(encoded) > MAX_DEFINITION_BYTES:
        raise DefinitionError("Agent Definition exceeds 1 MiB")
    yaml = YAML(typ="safe", pure=True)
    yaml.version = (1, 2)
    yaml.allow_duplicate_keys = False
    try:
        depth = 0
        for event in yaml.parse(text):
            if isinstance(event, DocumentStartEvent) and event.version not in (None, (1, 2)):
                raise DefinitionError("only YAML 1.2 is supported")
            if isinstance(event, CollectionStartEvent):
                depth += 1
                if depth > 64:
                    raise DefinitionError("definition exceeds nesting limit")
            if isinstance(event, CollectionEndEvent):
                depth -= 1
        value = yaml.load(text)
        return parse_structure(value, sha256(encoded).hexdigest())
    except (YAMLError, RecursionError) as error:
        raise DefinitionError(f"invalid Agent Definition YAML: {error}") from error


def load_agent_definition(path: Path) -> AgentDefinition:
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_DEFINITION_BYTES + 1)
        if len(content) > MAX_DEFINITION_BYTES:
            raise DefinitionError("Agent Definition exceeds 1 MiB")
        return parse_agent_definition(content.decode("utf-8"))
    except (OSError, UnicodeError) as error:
        raise DefinitionError(f"cannot read Agent Definition {path}: {error}") from error
