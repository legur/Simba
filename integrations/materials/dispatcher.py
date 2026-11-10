#!/usr/bin/env python3
"""Route validated Simba handoffs to a GitHub task, never to a paid provider.

This is a *real* issue task dispatcher, not an AI/renderer executor. On an
owner-controlled GitHub Actions push to main it files at most one public,
redacted issue for each unique validated next-stage fingerprint. No secrets,
private media links, dynamic offer fields or full handoff packets are posted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import catalog
import handoff

REPOSITORY = "legur/Simba"
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{40}$")
PROJECT_PATH = re.compile(r"^campaigns/([a-z0-9][a-z0-9-]{0,63})/project\.json$")
ROLE_BY_STAGE = {stage: producer for stage, producer, _, _ in handoff.STAGES}
ROLE_BY_STAGE["editorial_review"] = "LEO"
STAGE_HINTS = {
    "script": "Три разных полных сценария. Выбор Лео обязателен.",
    "storyboard": "Три полные раскадровки. Выбор Лео обязателен.",
    "a2e_prompts": "Три набора промптов на русском, затем точный английский перевод выбранного.",
    "a2e_clips": "Проверить стоимость, утвержденный лимит и реальный A2E task ID. Никакого автозапуска.",
    "voice_music": "Три варианта текста и музыки; использовать только утвержденный голос и лицензированный трек.",
    "edit_choice": "Три полных решения переходов и субтитров. Выбор Лео обязателен.",
    "render": "Собрать только утвержденную версию из доступных материалов, без платного повтора.",
    "qa": "Проверить реальный MP4, звук, субтитры, итоговый технический QA.",
    "editorial_review": "Получить решение Лео по конкретному готовому MP4. Публикация отдельно.",
}


class DispatchError(Exception):
    pass


def action_for(project: dict, hand: dict) -> dict | None:
    """Only validated, actionable next stages get a public task stub."""
    pid = project.get("id", "")
    if not isinstance(pid, str) or not PROJECT_ID.fullmatch(pid):
        raise DispatchError("invalid project ID")
    state = hand.get("state")
    if state == "NEEDS_FIRST_STAGE":
        stage = "script"
        stamp = hand.get("expected_input_fingerprint")
    elif state == "READY_FOR_HANDOFF":
        packet = hand.get("packet") or {}
        stage = packet.get("next_stage")
        stamp = packet.get("receipt_sha256")
    elif state == "NEEDS_LEO_REVIEW":
        packet = hand.get("packet") or {}
        if packet.get("next_stage") != "editorial_review":
            return None
        stage = "editorial_review"
        stamp = packet.get("receipt_sha256") or packet.get("source_revision")
    else:
        # BLOCKED, APPROVED_UNPUBLISHED, PUBLICATION_REPORTED_COMPLETE,
        # and all unknown states must NEVER enqueue a task.
        return None
    if stage not in ROLE_BY_STAGE or not isinstance(stamp, str) or not SHA.fullmatch(stamp):
        raise DispatchError("handoff has invalid stage or missing revision receipt")
    role = ROLE_BY_STAGE[stage]
    if hand.get("recipient") != role:
        raise DispatchError("handoff recipient and authorized role disagree")
    task_id = hashlib.sha256(
        f"simba-handoff-v1:{pid}:{stage}:{stamp}".encode("ascii")
    ).hexdigest()[:24]
    marker = f"<!-- simba-handoff:v1:{pid}:{stage}:{task_id} -->"
    # Public GitHub Issues: strictly static text and validated ASCII identifiers.
    # No source body, URL, per-customer data, offer text, tool receipts or credentials.
    title = f"Simba VIDEO: {pid} / {stage} / {role}"
    body = (f"{marker}\n\n"
            f"Проект: `{pid}`. Этап: `{stage}`. Исполнитель: `{role}`.\n\n"
            f"Задание: {STAGE_HINTS[stage]}\n\n"
            "Канонический источник: `campaigns/" + pid + "/project.json`. "
            "Прочитать проект и `SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/VIDEO_PIPELINE.md` "
            "перед исполнением.\n\n"
            "**Это автоматическое назначение задачи, а не выполнение агентом.** "
            "Передать выбор и фактические asset IDs назад в `stage_handoffs` той же "
            "карточки проекта. Следующая задача появится после проверенного write-back.\n\n"
            "Не помещать в публичную задачу клиентские сведения, приватные ссылки, "
            "ID голоса, ключи, коммерческий текст или исходные медиа. "
            "Никаких платных A2E/TTS-вызовов, повторов и публикации от этого триггера.\n")
    return {"project_id": pid, "stage": stage, "recipient": role,
            "task_id": task_id, "marker": marker, "title": title, "body": body,
            "state": "TASK_READY_NOT_EXECUTED"}


def plans_for_paths(root: Path, paths: list[str]) -> tuple[list[dict], list[dict]]:
    plans, skipped = [], []
    for path in sorted(set(paths)):
        match = PROJECT_PATH.fullmatch(path)
        if not match:
            continue
        target = catalog.inside(root, path)
        if not target.is_file():
            skipped.append({"path": path, "status": "NOT_FOUND_OR_DELETED"})
            continue
        project = json.loads(target.read_text(encoding="utf-8"))
        if project.get("id") != match.group(1):
            raise DispatchError("project path/ID mismatch")
        hand = handoff.make_handoff(root, target, project)
        task = action_for(project, hand)
        if task is None:
            skipped.append({"path": path, "status": hand.get("state", "UNKNOWN"),
                            "reason": hand.get("reason")})
        else:
            plans.append(task)
    return plans, skipped


def changed_projects(root: Path, before: str, after: str) -> list[str]:
    if not SHA.fullmatch(before) or not SHA.fullmatch(after):
        raise DispatchError("before/after must be full git SHA-1 identifiers")
    if before == "0" * 40:
        return []  # Never auto-dispatch entire repo on initial push.
    result = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMR",
                             before, after, "--", "campaigns/"],
                            cwd=root, capture_output=True, text=True, check=False)
    if result.returncode:
        raise DispatchError("git diff unavailable: refuse to dispatch")
    return [p for p in result.stdout.splitlines() if PROJECT_PATH.fullmatch(p)]


class GitHubIssueClient:
    def __init__(self, token: str, repo: str = REPOSITORY):
        if not token or repo != REPOSITORY:
            raise DispatchError("GitHub token/repository missing or unauthorized")
        self.token, self.repo = token, repo

    def request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request("https://api.github.com/repos/" + self.repo + path,
                                     data=data, method=method,
                                     headers={"Authorization": "Bearer " + self.token,
                                              "Accept": "application/vnd.github+json",
                                              "User-Agent": "simba-video-stage-dispatch/1",
                                              "X-GitHub-Api-Version": "2022-11-28",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Never echo API body/URL/tokens, including on 403/422/rate limit.
            raise DispatchError(f"GitHub Issues API failed: HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise DispatchError("GitHub Issues API unavailable; no blind retry") from None

    def existing_markers(self) -> set[str]:
        markers: set[str] = set()
        # Search all states (including closed) so workflow reruns never recreate
        # the same task; fail-closed if pagination could be truncated.
        for page in range(1, 31):
            rows = self.request("GET", f"/issues?state=all&per_page=100&page={page}")
            if not isinstance(rows, list):
                raise DispatchError("unexpected GitHub Issues response")
            for issue in rows:
                if "pull_request" in issue:
                    continue
                body = issue.get("body") or ""
                markers.update(re.findall(
                    r"<!-- simba-handoff:v1:[a-z0-9-]+:[a-z0-9_]+:[a-f0-9]{24} -->", body))
            if len(rows) < 100:
                return markers
        raise DispatchError("issue history exceeds safe scan limit; refuse duplicate creation")

    def create(self, item: dict) -> int:
        response = self.request("POST", "/issues", {"title": item["title"], "body": item["body"]})
        number = response.get("number")
        if type(number) is not int or number < 1:
            raise DispatchError("GitHub did not confirm issue creation")
        return number


def dispatch(plans: list[dict], client: GitHubIssueClient) -> list[dict]:
    seen = client.existing_markers()
    output = []
    for plan in plans:
        if plan["marker"] in seen:
            output.append({"project_id": plan["project_id"], "stage": plan["stage"],
                           "status": "ALREADY_QUEUED"})
            continue
        issue = client.create(plan)
        seen.add(plan["marker"])
        output.append({"project_id": plan["project_id"], "stage": plan["stage"],
                       "issue": issue, "status": "TASK_ISSUE_CREATED_NOT_EXECUTED"})
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--before", help="GitHub push before SHA")
    parser.add_argument("--after", help="GitHub push after SHA")
    parser.add_argument("--all", action="store_true", help="read-only preview of current projects")
    parser.add_argument("--execute", action="store_true", help="create public stage issues on trusted main push")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.all == bool(args.before or args.after):
            raise DispatchError("choose exactly --all or both --before and --after")
        if args.all and args.execute:
            raise DispatchError("--all is always read-only and cannot post issues")
        if args.execute:
            if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or
                os.environ.get("GITHUB_EVENT_NAME") != "push" or
                os.environ.get("GITHUB_REF") != "refs/heads/main" or
                os.environ.get("GITHUB_SHA") != args.after or
                not os.environ.get("GITHUB_TOKEN")):
                raise DispatchError("real dispatch only allowed for authenticated main push")
        if args.all:
            paths = [str(path.relative_to(root).as_posix())
                     for path, _ in catalog.load_projects(root)]
        else:
            if not args.before or not args.after:
                raise DispatchError("both --before and --after required")
            paths = changed_projects(root, args.before, args.after)
        plans, skipped = plans_for_paths(root, paths)
        result = ({"dispatch": dispatch(plans, GitHubIssueClient(os.environ["GITHUB_TOKEN"]))}
                  if args.execute else
                  {"dispatch": [{"project_id": x["project_id"], "stage": x["stage"],
                                  "recipient": x["recipient"], "status": "DRY_RUN_NOT_EXECUTED"}
                                 for x in plans]})
        result["skipped"] = skipped
        result["mode"] = "ISSUE_DISPATCH" if args.execute else "DRY_RUN"
        result["provider_calls"] = 0
        result["paid_jobs"] = 0
        result["published"] = False
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (DispatchError, ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("SIMBA_DISPATCH_ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())