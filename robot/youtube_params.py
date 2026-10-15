#!/usr/bin/env python3
"""Робот: какие поля рекламы вырезать на видеосайтах. Берём базовый список (params.json) и добавляем
названия полей, которые сообщество uBlock Origin вырезает правилами json-prune для youtube.com
(названия полей — факты, кода оттуда не берём). Строгий фильтр: только поля, похожие на рекламные.
    python3 youtube_params.py params.json uassets1.txt [uassets2.txt ...] > out/params.json"""
import json, re, sys

base = json.load(open(sys.argv[1]))
keys = list(dict.fromkeys(base["videoAdKeys"]))
ADLIKE = re.compile(r"^(ad[A-Z][A-Za-z]*|[a-z]+Ads?|[a-z]+Ad[A-Z][A-Za-z]*|adPlacements|adSlots|playerAds)$")
SAFE_EXCLUDE = {"loadAds", "canAds", "hasAds"}        # не трогать флаги, которые могут ломать плеер
found = set()
for path in sys.argv[2:]:
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    for line in text.splitlines():
        if "youtube" not in line or "json-prune" not in line or line.startswith("!"):
            continue
        m = re.search(r"json-prune(?:-fetch-response|-xhr-response)?,\s*([^,)]+)", line)
        if not m:
            continue
        for path_ in m.group(1).split():
            name = path_.split(".")[-1].replace("[]", "").replace("[-]", "").strip("'\"")
            if ADLIKE.match(name) and name not in SAFE_EXCLUDE and len(name) <= 40:
                found.add(name)
for k in sorted(found):
    if k not in keys:
        keys.append(k)
keys = keys[:20]                                      # потолок: не больше 20 полей
assert all(k in keys for k in base["videoAdKeys"]), "базовые поля потерялись"
out = dict(base, videoAdKeys=keys)
print(json.dumps(out, ensure_ascii=False, indent=1))
print(f"fields: {len(keys)} (+{len(keys) - len(base['videoAdKeys'])} from community)", file=sys.stderr)
