from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEFAULT_ALIASES: dict[str, str] = {
    "销售额": "orders.total_amount",
    "GMV": "orders.total_amount",
    "订单金额": "orders.total_amount",
    "用户": "users",
    "客户": "users",
}


@dataclass(frozen=True)
class AliasMatch:
    alias: str
    target: str
    target_type: str
    table_name: str
    column_name: str | None = None


class SemanticAliasResolver:
    """Minimal alias resolver backed by a dict or an optional JSON file."""

    def __init__(
        self,
        aliases: Mapping[str, str] | None = None,
        json_path: str | Path | None = None,
    ) -> None:
        merged = dict(DEFAULT_ALIASES)
        if aliases:
            merged.update(dict(aliases))
        if json_path:
            merged.update(self._load_json_aliases(Path(json_path)))
        self.aliases = merged

    def resolve(self, text: str) -> list[AliasMatch]:
        normalized_text = text.lower()
        matches: list[AliasMatch] = []
        seen: set[tuple[str, str]] = set()

        for alias, target in self.aliases.items():
            if alias.lower() not in normalized_text:
                continue
            parsed = self._parse_target(alias, target)
            identity = (parsed.alias.lower(), parsed.target.lower())
            if identity in seen:
                continue
            seen.add(identity)
            matches.append(parsed)

        return matches

    def _parse_target(self, alias: str, target: str) -> AliasMatch:
        normalized_target = target.strip()
        if "." in normalized_target:
            table_name, column_name = normalized_target.split(".", 1)
            return AliasMatch(
                alias=alias,
                target=normalized_target,
                target_type="column",
                table_name=table_name.strip(),
                column_name=column_name.strip(),
            )
        return AliasMatch(
            alias=alias,
            target=normalized_target,
            target_type="table",
            table_name=normalized_target,
        )

    def _load_json_aliases(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}

        aliases: dict[str, str] = {}
        for alias, target in raw.items():
            if isinstance(alias, str) and isinstance(target, str):
                aliases[alias] = target
        return aliases
