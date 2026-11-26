"""Versioned CAD contracts shared by the designer and the trusted geometry worker."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Parameter(Contract):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    value: float
    unit: Literal['mm', 'deg', 'number']
    description: str = Field(max_length=500)


class Part(Contract):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,47}$')
    name: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=1000)
    steps: list[str] = Field(min_length=1, max_length=16)
    printable: bool
    material: str = Field(max_length=100)
    print_notes: str = Field(max_length=1500)
    dimensions_mm: list[float] = Field(min_length=3, max_length=3)
    dimension_tolerance_mm: float = Field(ge=0.01, le=2)

    @model_validator(mode='after')
    def bounds(self):
        if any(not 0.1 <= n <= 2000 for n in self.dimensions_mm):
            raise ValueError('Part envelopes must be between 0.1 and 2000 mm.')
        return self


class Instance(Contract):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,47}$')
    part_id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,47}$')
    position_mm: list[float] = Field(min_length=3, max_length=3)
    rotation_deg: list[float] = Field(min_length=3, max_length=3)


class Connection(Contract):
    name: str = Field(min_length=1, max_length=150)
    a: str
    b: str
    kind: Literal['fixed', 'pivot', 'sliding', 'clearance']
    min_gap_mm: float = Field(ge=0, le=100)
    max_gap_mm: float = Field(ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=1500)


class Design(Contract):
    name: str = Field(min_length=1, max_length=150)
    summary: str = Field(min_length=1, max_length=3000)
    assumptions: list[str] = Field(max_length=20)
    missing_measurements: list[str] = Field(max_length=20)
    parameters: list[Parameter] = Field(max_length=100)
    parts: list[Part] = Field(min_length=1, max_length=16)
    instances: list[Instance] = Field(min_length=1, max_length=32)
    connections: list[Connection] = Field(max_length=64)
    assembly_steps: list[str] = Field(min_length=1, max_length=30)
    checks: list[str] = Field(min_length=1, max_length=30)
    printer_build_volume_mm: list[float] | None = Field(default=None, min_length=3, max_length=3)

    @model_validator(mode='after')
    def relationships(self):
        if self.printer_build_volume_mm and any(not 1 <= n <= 2000 for n in self.printer_build_volume_mm):
            raise ValueError('Printer build dimensions must be between 1 and 2000 mm.')
        for values in ([p.id for p in self.parts], [i.id for i in self.instances], [p.name for p in self.parameters]):
            if len(set(values)) != len(values):
                raise ValueError('Part, instance and parameter identifiers must be unique.')
        parts = {p.id for p in self.parts}
        instances = {i.id for i in self.instances}
        if {i.part_id for i in self.instances} != parts:
            raise ValueError('Every defined part must appear in the assembly; unknown parts are forbidden.')
        for i in self.instances:
            if any(abs(v) > 5000 for v in i.position_mm) or any(abs(v) > 360 for v in i.rotation_deg):
                raise ValueError('Assembly positions or angles exceed the supported bounds.')
        edges = {i: set() for i in instances}
        for c in self.connections:
            if c.a not in instances or c.b not in instances or c.a == c.b or c.max_gap_mm < c.min_gap_mm:
                raise ValueError('Connections must reference two different instances and an ordered gap range.')
            edges[c.a].add(c.b)
            edges[c.b].add(c.a)
        seen, pending = set(), [self.instances[0].id]
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(edges[current] - seen)
        if seen != instances:
            raise ValueError('Describe connections for all assembly instances; disconnected parts need a connection plan.')
        if not any(p.printable for p in self.parts):
            raise ValueError('Include at least one printable part.')
        return self


class PartReview(Contract):
    part_id: str
    passed: bool
    notes: str = Field(min_length=1, max_length=3000)


class Review(Contract):
    passed: bool
    summary: str = Field(min_length=1, max_length=4000)
    parts: list[PartReview] = Field(min_length=1, max_length=16)
    assembly_notes: list[str] = Field(min_length=1, max_length=30)
    issues: list[str] = Field(max_length=30)

    def check_parts(self, design):
        ids = [p.part_id for p in self.parts]
        if len(set(ids)) != len(ids) or set(ids) != {p.id for p in design.parts}:
            raise ValueError('Review must cover every part exactly once.')
        if self.passed and (self.issues or any(not p.passed for p in self.parts)):
            raise ValueError('Review cannot pass with unresolved issues or rejected parts.')
        return self


class Program(Contract):
    source: str = Field(min_length=1, max_length=100000)
    explanation: str = Field(max_length=3000)


def provider_schema(schema):
    """Keep provider grammar small; apply the full contract again on receipt."""
    if isinstance(schema, dict):
        return {k: provider_schema(v) for k, v in schema.items()
                if k not in {'minLength', 'maxLength', 'minItems', 'maxItems', 'pattern'}}
    if isinstance(schema, list):
        return [provider_schema(v) for v in schema]
    return schema
