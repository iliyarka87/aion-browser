#!/usr/bin/env python3
"""EasyList / EasyPrivacy (синтаксис Adblock Plus) → правила WebKit Content Blocker (JSON).

Собственный простой конвертер Lumo (без GPL-кода). Берёт только то, что WebKit умеет надёжно:
  • сетевые правила ||домен^ и шаблоны адресов с * и ^, с опциями third-party / типы ресурсов / domain=;
  • исключения @@ (ignore-previous-rules, в том же списке, после блокирующих);
  • скрытие элементов ТОЛЬКО для конкретных сайтов (домен##селектор) — общее скрытие на все сайты не берём
    (без его исключений #@# оно ломает сайты).
Регулярные выражения /.../, скриптлеты ##+js, расширенный CSS (#?#, #$#), redirect/csp/removeparam — пропускаются.
Лимит WebKit 150 000 правил на список — режем на части.

Списки EasyList — двойная лицензия GPLv3 / CC BY-SA 3.0, авторы «The EasyList authors (https://easylist.to/)».
Результат — производная работа по CC BY-SA 3.0 (указать авторство в приложении, экран Licenses).

    python3 convert_filters.py easylist.txt easyprivacy.txt --out ../Lumo/Blocking/Lists
"""
import json
import re
import sys
from pathlib import Path

LIMIT = 140_000            # запас под лимит WebKit 150 000
TYPES = {"script": "script", "image": "image", "stylesheet": "style-sheet", "subdocument": "document",
         "xmlhttprequest": "fetch", "media": "media", "font": "font", "popup": "popup", "ping": "ping",
         "websocket": "websocket", "other": "other", "object": "other"}
OK_OPTIONS = set(TYPES) | {"third-party", "3p", "domain", "match-case", "important", "all", "document"}
SELECTOR_BAD = re.compile(r":(has|xpath|contains|matches-|-abp-|upward|remove|style|min-text|watch-attr)|\[-ext-")


def url_regex(pattern: str):
    """Шаблон ABP → регулярка WebKit (без | и {} — WebKit их не поддерживает)."""
    p = pattern
    anchor_domain = p.startswith("||")
    anchor_start = not anchor_domain and p.startswith("|")
    p = p[2:] if anchor_domain else p[1:] if anchor_start else p
    anchor_end = p.endswith("|")
    if anchor_end:
        p = p[:-1]
    if not p or "|" in p:
        return None
    out = []
    for ch in p:
        if ch == "*":
            out.append(".*")
        elif ch == "^":
            out.append("[/:?=&]")
        elif ch in ".+?()[]{}\\$":
            out.append("\\" + ch)
        else:
            out.append(ch)
    body = "".join(out)
    if anchor_domain:
        body = r"^[a-z\-]+://([^/]+\.)?" + body
    elif anchor_start:
        body = "^" + body
    if anchor_end:
        body += "$"
    # «[/:?=&]» в самом конце адреса тоже должно совпадать с концом строки — WebKit этого не умеет; оставляем как есть
    return body


def network_rule(line: str):
    exception = line.startswith("@@")
    if exception:
        line = line[2:]
    pattern, _, opts = line.partition("$")
    if pattern.startswith("/") and pattern.endswith("/") and len(pattern) > 2:
        return None                                   # регулярки ABP — пропуск
    trigger = {}
    rtypes, if_dom, unless_dom = [], [], []
    for o in filter(None, opts.split(",")):
        neg = o.startswith("~")
        name, _, val = o.lstrip("~").partition("=")
        if name not in OK_OPTIONS:
            return None
        if name in ("third-party", "3p"):
            trigger["load-type"] = ["first-party" if neg else "third-party"]
        elif name == "domain":
            for d in val.split("|"):
                (unless_dom if d.startswith("~") else if_dom).append("*" + d.lstrip("~").lower())
        elif name in TYPES:
            if neg:
                return None                           # «все типы кроме» — WebKit так не умеет
            rtypes.append(TYPES[name])
        elif name == "document" and not exception:
            return None
    if if_dom and unless_dom:
        return None
    rx = url_regex(pattern)
    if not rx or not rx.isascii():
        return None
    trigger["url-filter"] = rx
    if rtypes:
        trigger["resource-type"] = sorted(set(rtypes))
    if if_dom:
        trigger["if-domain"] = if_dom
    if unless_dom:
        trigger["unless-domain"] = unless_dom
    return exception, {"trigger": trigger, "action": {"type": "ignore-previous-rules" if exception else "block"}}


def cosmetic_rule(line: str):
    domains, _, selector = line.partition("##")
    if not domains or not selector or SELECTOR_BAD.search(selector) or not selector.isascii():
        return None
    ds = [d.strip().lower() for d in domains.split(",") if d.strip()]
    if any(d.startswith("~") for d in ds) or any("*" in d or "/" in d for d in ds):
        return None
    return {"trigger": {"url-filter": ".*", "if-domain": ["*" + d for d in ds]},
            "action": {"type": "css-display-none", "selector": selector}}


def convert(paths):
    blocks, allows, cosmetic, skipped = [], [], [], 0
    for path in paths:
        for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith(("!", "[")):
                continue
            if "#@#" in line or "#?#" in line or "#$#" in line or "##+js" in line or "#%#" in line:
                skipped += 1
                continue
            if "##" in line:
                r = cosmetic_rule(line)
                (cosmetic.append(r) if r else None)
                skipped += r is None
                continue
            r = network_rule(line)
            if r is None:
                skipped += 1
                continue
            (allows if r[0] else blocks).append(r[1])
    return blocks, allows, cosmetic, skipped


def chunks(rules, allows):
    """Части по LIMIT; исключения дописываются в КАЖДУЮ часть (действуют только внутри своего списка)."""
    size = LIMIT - len(allows)
    for i in range(0, len(rules), size):
        yield rules[i:i + size] + allows


def main(argv):
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else Path(".")
    srcs = [a for a in argv if a.endswith(".txt")]
    blocks, allows, cosmetic, skipped = convert(srcs)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for n, part in enumerate(chunks(blocks, allows), 1):
        name = f"network-{n}.json"
        (out / name).write_text(json.dumps(part, separators=(",", ":")), encoding="utf-8")
        manifest.append({"file": name, "rules": len(part)})
    for n, part in enumerate(chunks(cosmetic, []), 1):
        name = f"cosmetic-{n}.json"
        (out / name).write_text(json.dumps(part, separators=(",", ":")), encoding="utf-8")
        manifest.append({"file": name, "rules": len(part)})
    (out / "lists.json").write_text(json.dumps({"lists": manifest, "sources": srcs,
                                                "license": "derived from EasyList/EasyPrivacy, CC BY-SA 3.0, The EasyList authors (https://easylist.to/)"},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"блок {len(blocks)}, исключений {len(allows)}, скрытие {len(cosmetic)}, пропущено {skipped}")
    for m in manifest:
        print(f"  {m['file']}: {m['rules']}")


if __name__ == "__main__":
    main(sys.argv[1:])
