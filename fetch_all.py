#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

GITHUB_API = "https://api.github.com"
REPOS_JSON = "repos.json"


def fetch_url(url: str, headers: dict = None) -> bytes:
    """Fetch the given URL, return the response body as bytes."""
    req = Request(url, headers=headers or {"User-Agent": "python-urllib"})
    try:
        with urlopen(req) as resp:
            return resp.read()
    except HTTPError as e:
        print(f"Error fetching {url}: {e.code} {e.reason} {dict(e.headers)}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Network error fetching {url}: {e.reason}", file=sys.stderr)
        sys.exit(1)


def save_file(path: str, content: bytes):
    """Write bytes to the given file path, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)


def load_saved_list():
    """Load the saved repos.json if present, returning a list of entries."""
    if not os.path.exists(REPOS_JSON):
        return []
    try:
        return json.load(open(REPOS_JSON, "r", encoding="utf-8"))
    except Exception as e:
        print(f"Failed to parse {REPOS_JSON}: {e}", file=sys.stderr)
        sys.exit(1)


def extract_repos_list(data):
    """Given loaded JSON, return the list of {repo, pushed_at} dicts."""
    if (
        isinstance(data, list)
        and len(data) == 1
        and isinstance(data[0], dict)
        and "repos" in data[0]
    ):
        return data[0]["repos"]
    else:
        raise ValueError("Unexpected JSON format")


def find_old_entry(old_list, name):
    """Return the entry in old_list matching repo==name (or None)."""
    for e in old_list:
        if e.get("repo") == name:
            return e
    return None


def main():
    p = argparse.ArgumentParser(
        description="Fetch/update README.md and README.html for a list of GitHub repos."
    )
    p.add_argument(
        "url",
        help='URL returning JSON of the form [{ "repos": [ {{ repo, pushed_at }}, … ] }]',
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between HTTP requests (default: 1.0)",
    )
    args = p.parse_args()

    # Load previous snapshot if any
    old_list = load_saved_list()
    old_map = {entry["repo"]: entry["pushed_at"] for entry in old_list}

    # Fetch the live repo list
    raw = fetch_url(args.url)
    fetched = json.loads(raw.decode("utf-8"))
    repos_list = extract_repos_list(fetched)

    # Decide which repos to fetch
    to_fetch = []
    for entry in repos_list:
        name, pushed = entry["repo"], entry["pushed_at"]
        if old_map.get(name) != pushed:
            to_fetch.append((name, pushed))

    if not to_fetch:
        print("No repos have changed. Nothing to do.")
        return
    else:
        print(f"{len(to_fetch)} repos changed; will update those.")

    # Build the new list of entries for repos.json
    new_list = []

    for entry in repos_list:
        name, pushed = entry["repo"], entry["pushed_at"]
        owner, repo = name.split("/", 1)

        if old_map.get(name) == pushed:
            # unchanged → carry over the old entry
            old_entry = find_old_entry(old_list, name)
            new_list.append(old_entry or entry)
            continue

        # changed (or first run) → fetch both files
        print(f"Fetching {name}…")

        # 1) raw Markdown
        md_url = f"{GITHUB_API}/repos/{owner}/{repo}/readme"
        md_bytes = fetch_url(
            md_url,
            headers={
                "Accept": "application/vnd.github.v3.raw",
                "User-Agent": "python-urllib",
            },
        )
        save_file(f"{owner}/{repo}/README.md", md_bytes)
        time.sleep(args.sleep)

        # 2) rendered HTML
        html_bytes = fetch_url(
            md_url,
            headers={
                "Accept": "application/vnd.github.v3.html",
                "User-Agent": "python-urllib",
            },
        )
        save_file(f"{owner}/{repo}/README.html", html_bytes)

        # Save JSON list in case of crash
        new_list.append(entry)
        with open(REPOS_JSON, "w", encoding="utf-8") as f:
            json.dump(new_list, f, indent=2, ensure_ascii=False)

        time.sleep(args.sleep)

    print(f"Updated {REPOS_JSON} with {len(new_list)} entries.")


if __name__ == "__main__":
    main()
