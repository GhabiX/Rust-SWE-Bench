import json
import requests
import time

from argparse import ArgumentParser
from enum import Enum
from pathlib import Path
from pydantic import BaseModel
from tqdm import tqdm
from typing import Dict, List


class Commit(BaseModel):
    sha: str
    parents_sha: List[str]


class CommitsUrl(BaseModel):
    pull_number: int
    url: str
    commits: List[Commit] = []
    base_commit: str | List[str] = None

    def fetch_commits(self):
        response = requests.get(self.url)
        response.raise_for_status()
        data = response.json()

        for commit in data:
            current_sha = commit["sha"]
            parents_sha = [parent["sha"] for parent in commit["parents"]]

            if len(parents_sha) == 0:
                raise ValueError(f"Commit {current_sha} should have parents")

            self.commits.append(Commit(sha=current_sha, parents_sha=parents_sha))

        if len(self.commits) == 0:
            raise ValueError(f"No commits found for {self.url}")

        if len(self.commits[0].parents_sha) > 1:
            self.base_commit = self.commits[0].parents_sha
        else:
            self.base_commit = self.commits[0].parents_sha[0]


class SourceType(str, Enum):
    from_prs = "from_prs"
    from_instances = "from_instances"


def get_all_commits_urls_from_prs(repo: str, jsonl: Path) -> List[CommitsUrl]:
    commits_urls: List[CommitsUrl] = []

    with jsonl.open("r") as f:
        for line in f:
            data = json.loads(line)
            pull_number = data["number"]
            url = data["commits_url"]
            assert (
                url
                == f"https://api.github.com/repos/{repo}/pulls/{pull_number}/commits"
            ), f"Invalid commits url {url}"

            commits_urls.append(CommitsUrl(pull_number=pull_number, url=url))

    return commits_urls


def get_all_commits_urls_from_instances(repo: str, jsonl: Path) -> List[CommitsUrl]:
    commits_urls: List[CommitsUrl] = []

    with jsonl.open("r") as f:
        for line in f:
            data = json.loads(line)
            pull_number = data["pull_number"]
            url = f"https://api.github.com/repos/{repo}/pulls/{pull_number}/commits"

            commits_urls.append(CommitsUrl(pull_number=pull_number, url=url))

    return commits_urls


def read_processed_pull_numbers(file_path: Path) -> Dict[int, CommitsUrl]:
    processed: Dict[int, CommitsUrl] = {}
    try:
        with open(file_path, "r") as f:
            for line in f:
                record = json.loads(line)
                processed[record["pull_number"]] = CommitsUrl(**record)
    except FileNotFoundError:
        pass
    return processed


def save_commit_url(commit_url: CommitsUrl, file_path: Path):
    with open(file_path, "a") as f:
        f.write(commit_url.model_dump_json() + "\n")


def main(base_dir: Path, source_type: SourceType, repo: str, interval: float):
    splited_repo: List[str] = repo.split("/")
    assert len(splited_repo) == 2, f"repo should be in form of 'owner/repo', got {repo}"

    repo_dir = base_dir / repo.replace("/", "__")
    base_name = splited_repo[-1]
    prs_jsonl = repo_dir / f"{base_name}-prs.jsonl"
    instances_jsonl = repo_dir / f"{base_name}-task-instances.jsonl"
    commits_jsonl = repo_dir / f"{base_name}-commits.jsonl"

    if source_type == SourceType.from_prs:
        all_commit_urls = get_all_commits_urls_from_prs(repo, prs_jsonl)
    elif source_type == SourceType.from_instances:
        all_commit_urls = get_all_commits_urls_from_instances(repo, instances_jsonl)
    else:
        raise ValueError(f"Invalid source type {source_type}")

    processed_pull_numbers = read_processed_pull_numbers(commits_jsonl)

    unprocessed_commit_urls = [
        commit_url
        for commit_url in all_commit_urls
        if commit_url.pull_number not in processed_pull_numbers
    ]
    print(
        f"Skipping {len(all_commit_urls) - len(unprocessed_commit_urls)}/{len(all_commit_urls)} already processed commit_urls for {repo}"
    )

    if len(unprocessed_commit_urls) == 0:
        return

    for commit_url in tqdm(unprocessed_commit_urls, desc="Fetching commits"):
        try:
            commit_url.fetch_commits()
            save_commit_url(commit_url, commits_jsonl)
            time.sleep(interval)
        except Exception as e:
            raise ValueError(f"Error fetching commits for {commit_url}: {e}")


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument(
        "--base_dir",
        "-d",
        type=Path,
        help="Base directory for storing data.",
    )
    parser.add_argument(
        "--source_type",
        "-s",
        type=str,
        choices=[t.value for t in SourceType],
        default=SourceType.from_instances.value,
        help="Source type for fetching commits.",
    )
    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        required=True,
        help="Repository name to fetch commits from.",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=5.0,
        help="Interval between requests in seconds.",
    )

    args = parser.parse_args()
    main(**vars(args))