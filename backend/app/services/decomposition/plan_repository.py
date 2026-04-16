"""Mongo persistence for enterprise decomposition plans (Planning §8)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from app.core.database import get_decomposition_plans_collection


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def insert_plan(document: dict[str, Any]) -> None:
    col = get_decomposition_plans_collection()
    document["created_at"] = _utcnow()
    document["updated_at"] = _utcnow()
    await col.insert_one(document)


async def find_by_plan_id(plan_id: str) -> dict[str, Any] | None:
    col = get_decomposition_plans_collection()
    return await col.find_one({"plan_id": plan_id, "withdrawn": {"$ne": True}})


async def find_by_plan_id_include_withdrawn(plan_id: str) -> dict[str, Any] | None:
    col = get_decomposition_plans_collection()
    return await col.find_one({"plan_id": plan_id})


async def list_kicked_off_for_enterprise(enterprise_profile_id: str) -> list[dict[str, Any]]:
    col = get_decomposition_plans_collection()
    cursor = (
        col.find(
            {
                "enterprise_profile_id": enterprise_profile_id,
                "kicked_off": True,
                "withdrawn": {"$ne": True},
            }
        )
        .sort("updated_at", -1)
        .limit(500)
    )
    return await cursor.to_list(length=500)


async def update_by_plan_id(plan_id: str, update_ops: dict[str, Any]) -> None:
    col = get_decomposition_plans_collection()
    merged = dict(update_ops)
    if "$set" in merged:
        merged["$set"] = {**merged["$set"], "updated_at": _utcnow()}
    else:
        merged["$set"] = {"updated_at": _utcnow()}
    await col.update_one({"plan_id": plan_id, "withdrawn": {"$ne": True}}, merged)


async def find_one_and_update(
    match: dict[str, Any],
    update_ops: dict[str, Any],
) -> dict[str, Any] | None:
    col = get_decomposition_plans_collection()
    merged = dict(update_ops)
    if "$set" in merged:
        merged["$set"] = {**merged["$set"], "updated_at": _utcnow()}
    else:
        merged["$set"] = {"updated_at": _utcnow()}
    return await col.find_one_and_update(match, merged, return_document=ReturnDocument.AFTER)
