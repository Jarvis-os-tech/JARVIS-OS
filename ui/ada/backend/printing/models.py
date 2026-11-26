from ipaddress import IPv4Address
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrinterSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    host: str = ''
    port: int = Field(default=7125, ge=1, le=65535)
    # Bind this installation to the identity observed during setup.
    hostname: str = ''
    material: Literal['unknown', 'PLA', 'PETG'] = 'unknown'
    source: Literal['unknown', 'external', 'cfs'] = 'unknown'
    profile_verified: bool = False
    profile_revision: str = ''
    cfs_box: int = Field(default=1, ge=1, le=4)
    cfs_slot: int = Field(default=1, ge=1, le=4)

    @field_validator('host')
    @classmethod
    def private_host(cls, value):
        if value:
            ip = IPv4Address(value)
            if not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_link_local:
                raise ValueError('Use the printer’s private LAN IPv4 address.')
        return value


class PlatePart(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    part_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    rotation: list[float] = Field(default_factory=lambda: [0, 0, 0], min_length=3, max_length=3)
    position: list[float] = Field(default_factory=lambda: [130, 130], min_length=2, max_length=2)


class PrintRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    revision_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    instances: list[PlatePart] = Field(min_length=1, max_length=32)
    acknowledge_stale: bool = False
    material: Literal['PLA', 'PETG']
    quality: Literal['standard', 'draft', 'fine'] = 'standard'
    infill: int = Field(default=20, ge=5, le=100)
    supports: Literal['off', 'buildplate', 'everywhere'] = 'everywhere'
    support_angle: int = Field(default=45, ge=30, le=70)
    brim: bool = False


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')


class StartRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    bed_clear: Literal[True]
    filament_ready: Literal[True]
    calibration_test: bool = False


class ControlRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['pause', 'resume', 'cancel']
    filename: str = Field(min_length=1, max_length=512)
