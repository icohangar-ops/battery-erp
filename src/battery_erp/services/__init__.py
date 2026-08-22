"""Shared service layer used by both MCP tools and the REST adapter."""

from .inventory import InventoryService
from .store import InMemoryInventoryStore

__all__ = ["InventoryService", "InMemoryInventoryStore"]
