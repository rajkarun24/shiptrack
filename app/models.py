"""Data shapes (schemas). FastAPI uses these to validate requests automatically."""
from enum import Enum

from pydantic import BaseModel, Field


class Status(str, Enum):
    CREATED = "CREATED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"


class ParcelCreate(BaseModel):
    sender: str = Field(min_length=1, max_length=100)
    recipient: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=200)


class StatusUpdate(BaseModel):
    status: Status


class Parcel(ParcelCreate):
    id: str
    status: Status = Status.CREATED
