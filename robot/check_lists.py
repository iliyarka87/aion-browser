#!/usr/bin/env python3
"""Проверка перед публикацией: списки не пустые, не больше лимита WebKit, правила разумной формы,
параметры скриптов на месте. Провал — публикация останавливается, у пользователей остаётся прошлое."""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
total = 0
for f in sorted(out.glob("network-*.json")) + sorted(out.glob("cosmetic-*.json")):
    rules = json.loads(f.read_text())
    assert isinstance(rules, list) and 0 < len(rules) <= 150_000, f"{f.name}: {len(rules)} правил"
    for r in rules[:2000]:
        assert "trigger" in r and "action" in r and "url-filter" in r["trigger"], f"{f.name}: плохое правило {r}"
    total += len(rules)
assert total > 50_000, f"слишком мало правил: {total} — похоже, источник сломан"
p = json.loads((out / "params.json").read_text())
assert {"videoAdKeys", "hosts", "killSwitch"} <= set(p), "params.json неполный"
print(f"OK: {total} правил")
