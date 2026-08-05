"""Declarative base compartida. Los modelos del cap. 17 se definen en models.py (Fase 1)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
