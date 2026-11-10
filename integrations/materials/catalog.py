#!/usr/bin/env python3
"""Read-only local discovery of existing Simba libraries and project manifests."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

LIBRARIES = {
    "archivarius": ("Archivarius", "AR-*.md"),
    "tia": ("Archivarius/TIA", "TIA-*.txt"),
    "kadr": ("Кадр/База/cards", "KADR-*.md"),
    "critic": ("Симба (Писатель)/Session-Logs", "*.md"),
    "content": ("SIMBA KNOWLEDGE BASE/03_CONTENT_LIBRARY", "*.md"),
    "projects": ("campaigns", "project.json"),
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ASSET_STATES = {"available", "historical", "partial", "unverified"}
APPROVAL_STATES = {"unknown", "pending", "approved", "rejected"}


def norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")


def inside(root: Path, relative: str) -> Path:
    raw = Path(relative)
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"Unsafe repository path: {relative}")
    target = (root / raw).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Path leaves repository: {relative}")
    return target


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines()
    # Front matter only, or the document's header before its first section.
    if lines and lines[0].lstrip("\ufeff").strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 1)
        header = lines[1:end]
    else:
        end = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
        header = lines[:min(end, 30)]
    fields = {}
    for line in header:
        match = re.match(r"^(title|status):\s*(.*?)\s*$", line, re.I)
        if match:
            fields[match[1].lower()] = match[2].strip("\"'")
    title = fields.get("title") or next((x.lstrip("# ") for x in lines if x.startswith("# ")), path.stem)
    return title, fields.get("status", "UNKNOWN")


def load_projects(root: Path) -> list[tuple[Path, dict]]:
    directory = inside(root, "campaigns")
    if not directory.is_dir():
        return []
    result = []
    seen = set()
    for path in sorted(directory.glob("*/project.json")):
        path = inside(root, path.relative_to(root).as_posix())
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Project must be an object: {path.name}")
        project_id = data.get("id", "")
        if not ID_RE.fullmatch(project_id) or project_id in seen:
            raise ValueError(f"Invalid or duplicate project ID: {project_id!r}")
        seen.add(project_id)
        result.append((path, data))
    return result


def resolve_project(root: Path, query: str) -> tuple[Path, dict]:
    projects = load_projects(root)
    exact = [(p, d) for p, d in projects if norm(query) in [norm(d["id"]), *map(norm, d.get("aliases", []))]]
    matches = exact or [(p, d) for p, d in projects if norm(query) in norm(d.get("title", ""))]
    if len(matches) != 1:
        raise ValueError("Project not found or ambiguous; use an exact project ID from list")
    return matches[0]


def project_issues(root: Path, path: Path, data: dict) -> list[str]:
    issues = []
    if data.get("schema_version") != 1:
        issues.append("Unsupported schema_version")
    for name in ("title", "stage", "next_action", "updated_at", "sources", "assets", "references", "approvals"):
        if not data.get(name):
            if name != "references":
                issues.append(f"Missing {name}")
    for source in data.get("sources", []):
        source_path = inside(root, source["path"])
        if not source_path.is_file():
            issues.append(f"MISSING_SOURCE: {source['path']}")
        elif digest(source_path) != source.get("sha256"):
            issues.append(f"STALE_SOURCE: {source['path']} — read current source and reconcile project")
    assets = data.get("assets", [])
    ids = [asset.get("id") for asset in assets]
    if len(set(ids)) != len(ids) or any(not x for x in ids):
        issues.append("Duplicate or empty asset ID")
    for asset in assets:
        if asset.get("state") not in ASSET_STATES:
            issues.append(f"Invalid asset state: {asset.get('id')}")
        url = asset.get("url", "")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            issues.append(f"Invalid HTTPS URL: {asset.get('id')}")
        if re.search(r"(?:[?&])(?:token|access_token|signature|x-amz-signature|x-goog-signature)=", url, re.I):
            issues.append(f"Temporary/credential URL is not an archive link: {asset.get('id')}")
        if not asset.get("evidence"):
            issues.append(f"Missing asset evidence: {asset.get('id')}")
    working = data.get("working_asset_id")
    approved = data.get("approved_asset_id")
    if working and working not in ids:
        issues.append("working_asset_id is not in assets")
    if approved and approved not in ids:
        issues.append("approved_asset_id is not in assets")
    approvals = data.get("approvals", {})
    for name in ("editorial", "publication"):
        if approvals.get(name) not in APPROVAL_STATES:
            issues.append(f"Invalid approval state: {name}")
    if approved and approvals.get("editorial") != "approved":
        issues.append("An approved asset needs explicit editorial approval")
    if approvals.get("editorial") == "approved" and (not approved or not approvals.get("editorial_evidence")):
        issues.append("Editorial approval needs an asset and recorded evidence")
    if approvals.get("publication") == "approved" and not approvals.get("publication_evidence"):
        issues.append("Publication needs recorded evidence")
    if approvals.get("publication") == "approved" and approvals.get("editorial") != "approved":
        issues.append("Publication requires editorial approval")
    for ref in data.get("references", []):
        if not inside(root, ref["path"]).is_file():
            issues.append(f"MISSING_REFERENCE: {ref['path']}")
    return issues


def project_progress(root: Path, path: Path, data: dict) -> dict:
    """Read-only status derived from local registry evidence, never remote media QA."""
    issues = project_issues(root, path, data)
    approvals = data.get("approvals") or {}
    assets = {a.get("id"): a for a in data.get("assets", []) if a.get("id")}
    working = assets.get(data.get("working_asset_id"))
    approved = data.get("approved_asset_id")
    stage = data.get("stage", "")
    missing = data.get("missing") or []
    if issues:
        state, status, owner = "BLOCKED", "ЗАБЛОКИРОВАНО", "PROCESS_OWNER"
        if any(i.startswith("STALE_SOURCE") for i in issues):
            action = ("Сверить измененные источники и последние решения Лео; "
                      "только затем пересчитать хеши project.json.")
        elif any(i.startswith(("MISSING_SOURCE", "MISSING_REFERENCE")) for i in issues):
            action = "Восстановить отсутствующие источники и повторить проверку проекта."
        else:
            action = "Исправить ошибки project.json и повторить catalog.py check."
    elif (approvals.get("editorial") == "approved" and approved
          and approvals.get("publication") == "approved" and not missing):
        state, status, owner = "REGISTERED_COMPLETE", "ГОТОВО", "PROCESS_OWNER"
        action = "Подтверждено по реестру; проверить внешние файлы и публикацию отдельно."
    elif (approvals.get("editorial") == "approved" and approved
          and approvals.get("publication") != "approved"):
        state, status, owner = "NEEDS_LEO", "НУЖНО РЕШЕНИЕ ЛЕО", "LEO"
        action = data.get("next_action") or "Решение о публикации утвержденного файла."
    elif (approvals.get("editorial") == "pending" and working
          and working.get("state") == "available"):
        state, status, owner = "NEEDS_LEO", "НУЖНО РЕШЕНИЕ ЛЕО", "LEO"
        action = data.get("next_action") or "Проверить рабочую версию и принять решение."
    else:
        state, status, owner = "IN_PROGRESS", "В РАБОТЕ", "PROFILE_EXECUTOR"
        if not working and "REVIEW" in stage.upper():
            action = ("Указать конкретный проверенный рабочий файл в working_asset_id "
                      "до передачи Лео на утверждение.")
        else:
            action = data.get("next_action") or "Продолжить работу профильного исполнителя."
    return {
        "id": data.get("id"), "title": data.get("title"), "stage": stage,
        "state": state, "status": status, "action_owner": owner,
        "next_action": action, "issues": issues, "missing": missing,
        "working_asset_id": data.get("working_asset_id"),
        "approved_asset_id": approved,
        "checks": {
            "local_manifest": "FAIL" if issues else "PASS",
            "local_sources": "FAIL" if any(i.startswith(("STALE_SOURCE", "MISSING_SOURCE"))
                                           for i in issues) else "PASS",
            "working_asset_record": "RECORDED" if working else "NOT_SET",
            "editorial": approvals.get("editorial", "unknown"),
            "publication": approvals.get("publication", "unknown"),
            "external_media_and_actual_publication": "NOT_VERIFIED_BY_CATALOG",
        },
        "verification_scope": "LOCAL_REPOSITORY_ONLY",
        "note": ("Каталог проверяет только локальные сведения, не Google Drive, "
                 "фактический MP4/QA или реальную публикацию. ГОТОВО = по реестру."),
    }


def search(root: Path, query: str, library: str | None, limit: int) -> list[dict]:
    terms = norm(query).split()
    if not terms:
        raise ValueError("Search query cannot be empty")
    results = []
    for name, (base, pattern) in LIBRARIES.items():
        if library and library != name:
            continue
        directory = inside(root, base)
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.rglob(pattern)):
            relative = candidate.relative_to(root).as_posix()
            if name == "archivarius" and relative.startswith("Archivarius/TIA/"):
                continue
            if any(x in relative for x in ("/99_", "/__OLD", "/.git/")):
                continue
            if name == "content" and candidate.name.startswith("_"):
                continue
            try:
                path = inside(root, relative)
                text = path.read_text(encoding="utf-8-sig")
            except (ValueError, UnicodeError):
                continue
            body = norm(relative + "\n" + text)
            if not all(term in body for term in terms):
                continue
            title, status = metadata(text, path)
            if name == "projects":
                record = json.loads(text)
                title, status = record["title"], record["stage"]
            if name == "tia":
                # Status in the canonical TIA registry overrides a matching filename.
                registries = list(inside(root, "Archivarius/TIA").glob("INDEX_v*.txt"))
                registries = [p for p in registries if re.fullmatch(r"INDEX_v\d+\.txt", p.name)]
                registry = max(registries, key=lambda p: int(re.search(r"\d+", p.name)[0])) if registries else None
                card_id = re.match(r"TIA-\d+", candidate.name)
                if registry is not None and registry.is_file() and card_id:
                    for line in registry.read_text(encoding="utf-8-sig").splitlines():
                        if re.match(r"\|\s*" + re.escape(card_id[0]) + r"\s*\|", line):
                            if "SOURCE_BLOCKED" in line:
                                status = "SOURCE_BLOCKED_CORRUPT"
            excerpt = next((line for line in text.splitlines() if any(term in norm(line) for term in terms)), "")
            results.append({"library": name, "title": title, "status": status, "path": relative,
                            "excerpt": excerpt[:260], "usage": "Read full source and applicable role gates before use"})
    return results[:limit]


def human(output: list | dict, command: str) -> str:
    if isinstance(output, list):
        if not output:
            return "Совпадений нет."
        lines = []
        for row in output:
            if command == "check":
                lines.append(row["id"] + ": " + ("; ".join(row["issues"]) or "PASS"))
            elif command == "list":
                lines.extend([f"{row['title']} [{row['id']}] — {row['stage']}",
                              "Дальше: " + row["next_action"], "Файл: " + row["path"]])
                lines.extend("ВНИМАНИЕ: " + x for x in row.get("issues", []))
            else:
                lines.extend([f"[{row['library']} / {row['status']}] {row['title']}", row["path"], row["excerpt"]])
            lines.append("")
        return "\n".join(lines)
    lines = [output.get("title", output["id"]) + " [" + output["id"] + "]"]
    lines.extend("ВНИМАНИЕ: " + x for x in output.get("issues", []))
    if command == "status":
        return "
".join([
            f"Проект: {output['title']} [{output['id']}]",
            "Статус: " + output["status"],
            "Этап: " + output["stage"],
            "Следующее действие: " + output["next_action"],
            "Ответственный: " + output["action_owner"],
            "Недостает: " + ("; ".join(output["missing"]) or "нет"),
            "Ошибки: " + ("; ".join(output["issues"]) or "нет"),
            "Внешние файлы: не проверены",
        ])
    if command == "resume":
        lines.extend(["Этап: " + output["stage"], "Дальше: " + output["next_action"],
                      "Рабочая версия: " + str(output.get("working_asset_id")),
                      "Утвержденный финал: " + str(output.get("approved_asset_id")),
                      "Утверждения: " + json.dumps(output["approvals"], ensure_ascii=False)])
        if output.get("latest_user_request"):
            lines.append("Последняя правка Лео: " + output["latest_user_request"]["text"])
        lines.append("Чего не хватает: " + "; ".join(output.get("missing", [])))
        lines.extend("Источник: " + x["path"] for x in output["sources"])
    for asset in output.get("assets", []):
        lines.append(f"{asset['id']} [{asset['state']}]: {asset['title']}\n{asset['url']}")
    lines.extend("Повторное использование: " + x for x in output.get("reuse_notes", []))
    if output.get("note"):
        lines.append(output["note"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true", dest="as_json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("check")
    for command in ("resume", "reuse", "status"):
        child = sub.add_parser(command)
        child.add_argument("project")
        if command == "reuse":
            child.add_argument("--kind")
    finder = sub.add_parser("search")
    finder.add_argument("query")
    finder.add_argument("--library", choices=LIBRARIES)
    finder.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        code = 0
        if args.command == "list":
            output = [{"id": d["id"], "title": d["title"], "stage": d["stage"],
                       "path": p.relative_to(root).as_posix(), "next_action": d["next_action"],
                       "issues": project_issues(root, p, d)}
                      for p, d in load_projects(root)]
            code = 2 if any(x["issues"] for x in output) else 0
        elif args.command == "check":
            output = [{"id": d["id"], "issues": project_issues(root, p, d)} for p, d in load_projects(root)]
            code = 2 if not output or any(x["issues"] for x in output) else 0
        elif args.command == "search":
            if not 1 <= args.limit <= 50:
                raise ValueError("limit must be between 1 and 50")
            output = search(root, args.query, args.library, args.limit)
        else:
            path, data = resolve_project(root, args.project)
            issues = project_issues(root, path, data)
            code = 2 if issues else 0
            if args.command == "status":
                output = project_progress(root, path, data)
            elif args.command == "reuse":
                output = {"id": data["id"], "issues": issues,
                          "assets": [a for a in data["assets"] if a.get("reuse") and
                                     (not args.kind or a.get("kind") == args.kind)],
                          "note": "Catalog evidence only; open and verify actual file before reuse. No generation is started."}
            else:
                output = dict(data, issues=issues,
                              progress=project_progress(root, path, data))
        if args.as_json:
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print(human(output, args.command))
        return code
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"CATALOG_ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
