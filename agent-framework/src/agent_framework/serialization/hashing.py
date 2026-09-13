"""Deterministic SHA-256 hashing for build artifacts."""

from hashlib import sha256

from .json import canonical_json


def content_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def artifact_hash(value: object) -> str:
    return content_hash(canonical_json(value))
