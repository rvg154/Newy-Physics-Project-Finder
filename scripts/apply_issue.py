#!/usr/bin/env python3
"""Convert a GitHub issue-form submission into a proposed project update.

Only a PR is created; nothing is published until a maintainer merges it.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "projects.json"
HTML = ROOT / "index.html"
HEADINGS = {
    "Requested change": "action", "Project ID": "project_id",
    "Supervisor name": "supervisor", "University email": "email",
    "Project title": "title", "Project description": "description",
    "Research interests (comma separated)": "tags",
    "Methods (comma separated)": "methods",
    "Keywords (comma separated)": "keywords",
    "Software used (comma separated)": "software",
    "Supervisor profile URL": "profile", "Handbook page (optional)": "page",
    "Notes for the reviewer": "notes",
}
ALLOWED_TAGS = {
    "Astronomy & exoplanets", "Solar physics & space weather", "Plasma physics & fusion",
    "Quantum physics & quantum technologies", "Lasers & optical spectroscopy",
    "Medical imaging & radiotherapy", "Cancer research & disease diagnostics",
    "Nanotechnology & nanoparticles", "Materials science & surface imaging",
    "Biophysics & molecular biology", "Artificial intelligence & machine learning",
    "Programming & computational modelling", "Renewable energy & solar cells",
    "Electronics & sensors", "Mathematics & theoretical physics",
}
ALLOWED_METHODS = {"Laboratory experiments", "Programming & simulation", "Data analysis & imaging"}


def parse_issue(body):
    fields = {}
    parts = re.split(r"(?m)^### (.+?)\s*$", body)
    for heading, value in zip(parts[1::2], parts[2::2]):
        if heading in HEADINGS:
            cleaned = value.strip()
            fields[HEADINGS[heading]] = "" if cleaned in ("_No response_", "No response") else cleaned
    return fields


def comma_list(value):
    return list(dict.fromkeys(v.strip() for v in value.split(",") if v.strip()))


def apply(fields, projects):
    action = fields.get("action", "")
    id_text = fields.get("project_id", "").strip()
    if action not in {"Edit existing project", "Add new project", "Withdraw existing project"}:
        raise ValueError("Choose a valid action")
    if not re.fullmatch(r"[^\W\d_][\w .’'-]*", fields.get("supervisor", "")):
        raise ValueError("Supervisor name missing or invalid")
    if not re.fullmatch(r"[A-Za-z0-9._%+\-]+@newcastle\.edu\.au", fields.get("email", ""), re.I):
        raise ValueError("University email must end in @newcastle.edu.au")
    if action == "Add new project":
        if id_text.upper() != "NEW":
            raise ValueError("Use NEW as the project ID for additions")
        if not fields.get("title") or not fields.get("description"):
            raise ValueError("New projects require a title and description")
        project = {"id": max(p["id"] for p in projects) + 1,
                   "title": fields["title"], "description": fields["description"],
                   "supervisor": fields["supervisor"], "email": fields["email"],
                   "profile": "", "page": "—", "tags": [], "methods": [],
                   "keywords": [], "software": []}
        projects.append(project)
    else:
        if not id_text.isdigit():
            raise ValueError("Existing projects need a numeric project ID")
        project = next((p for p in projects if p["id"] == int(id_text)), None)
        if project is None:
            raise ValueError("Project ID not found")
        if project["email"].lower() != fields["email"].lower():
            raise ValueError("Submitted email does not match the existing project supervisor; manual verification needed")
        if action == "Withdraw existing project":
            projects.remove(project)
            return f"Withdraw project {id_text}"
    for key in ("title", "description", "profile"):
        if fields.get(key):
            project[key] = fields[key]
    for key in ("tags", "methods", "keywords", "software"):
        if fields.get(key):
            items = comma_list(fields[key])
            if key == "tags" and not set(items) <= ALLOWED_TAGS:
                raise ValueError("Unknown research-interest tag: " + str(set(items) - ALLOWED_TAGS))
            if key == "methods" and not set(items) <= ALLOWED_METHODS:
                raise ValueError("Unknown method: " + str(set(items) - ALLOWED_METHODS))
            project[key] = items
    if fields.get("page"):
        if not fields["page"].isdigit():
            raise ValueError("Handbook page must be a number")
        project["page"] = int(fields["page"])
    return f"{action}: {project['title']}"


def sync_html(projects):
    text = HTML.read_text(encoding="utf-8")
    pattern = r'(<script id="data" type="application/json">).*?(</script>)'
    payload = json.dumps(projects, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    updated, n = re.subn(pattern, lambda m: m.group(1) + payload + m.group(2), text, count=1, flags=re.S)
    if n != 1:
        raise ValueError("Could not locate embedded projects database")
    HTML.write_text(updated, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue-file", required=True)
    args = ap.parse_args()
    fields = parse_issue(Path(args.issue_file).read_text(encoding="utf-8"))
    projects = json.loads(DATA.read_text(encoding="utf-8"))
    summary = apply(fields, projects)
    DATA.write_text(json.dumps(projects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync_html(projects)
    print(summary)

if __name__ == "__main__":
    main()
