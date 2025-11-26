#!/usr/bin/env python3

"""Given the `<owner/name>` of a GitHub repo, this script writes the raw information for specific or all repo's PRs to a single `.jsonl` file."""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing
import os
# import pysnooper

from datetime import datetime
from fastcore.xtras import obj2dict
from swebench.collect.utils import Repo
from typing import Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# @pysnooper.snoop()
def log_all_pulls(
        repo: Repo,
        output: str,
        max_pulls: int = None,
        cutoff_date: str = None,
        pr_lock: multiprocessing.Lock = None,
        repo_name: str = None,
    ) -> None:
    """
    Iterate over all pull requests in a repository and log them to a file

    Args:
        repo (Repo): repository object
        output (str): output file name
    """
    if cutoff_date is not None:
        cutoff_date = datetime.strptime(cutoff_date, "%Y%m%d").strftime("%Y-%m-%dT%H:%M:%SZ") 

    auto = pr_lock is not None
    cnt = 0
    log = os.path.join(os.getcwd(),'logs/pr_log')
    with open(output, "w") as file:
        log_file = open(log, "a") if auto else None
        for i_pull, pull in enumerate(repo.get_all_pulls()):
            setattr(pull, "resolved_issues", repo.extract_resolved_issues(pull))
            print(json.dumps(obj2dict(pull)), end="\n", flush=True, file=file)
            if auto:
                #count total number of PRs
                cnt += 1
                # record the log
                if i_pull % 100 == 0:
                    if i_pull != 0:
                        with pr_lock:
                            log_file.write("{}: {} pull requests\n".format(repo_name, i_pull))
                            log_file.flush()
            if max_pulls is not None and i_pull >= max_pulls:
                break
            if cutoff_date is not None and pull.created_at < cutoff_date:
                break
        if auto:
            with pr_lock:
                log_file.write("{}: {} pull requests\n".format(repo_name, cnt))
                log_file.write("Done:{}\n".format(repo_name))
                log_file.close()


def log_specific_pulls(
        repo: Repo,
        pull_numbers: list[int],
        output: str,
        pr_lock: multiprocessing.Lock,
        repo_name: str = None,
    ) -> None:
    """
    Log specific pull requests to a file

    Args:
        repo (Repo): repository object
        pull_numbers (list[int]): List of pull request numbers to log
        output (str): output file name
    """
    
    with open(output, "w") as file:
        
        for pull in repo.get_specific_pulls(pull_numbers):
            
            setattr(pull, "resolved_issues", repo.extract_resolved_issues(pull))
            
            print(json.dumps(obj2dict(pull)), end="\n", flush=True, file=file)


def main(
        repo_name: str,
        output: str,
        token: Optional[str] = None,
        pull_numbers: list[int] = None,
        max_pulls: int = None,
        cutoff_date: str = None,
        pr_lock: multiprocessing.Lock = None,
    ):
    print("list:",pull_numbers)
    """
    Logic for logging specific or all pull requests in a repository

    Args:
        repo_name (str): name of the repository
        output (str): output file name
        pull_numbers (list[int], optional): List of pull request numbers to log
        token (str, optional): GitHub token
    """
    if token is None:
        token = os.environ.get("GITHUB_TOKEN")
    owner, repo = repo_name.split("/")
    repo = Repo(owner, repo, token=token)

    
    if pull_numbers:
        log_specific_pulls(repo, pull_numbers, output, pr_lock, repo_name)
    else:
        log_all_pulls(repo, output, max_pulls, cutoff_date, pr_lock, repo_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_name", type=str, help="Name of the repository")
    parser.add_argument("output", type=str, help="Output file name")
    parser.add_argument("--pull_numbers", nargs='+', type=int, help="List of specific pull request numbers to log",default=None)
    parser.add_argument("--token", type=str, help="GitHub token")
    parser.add_argument("--max_pulls", type=int, help="Maximum number of pulls to log", default=None)
    parser.add_argument("--cutoff_date", type=str, help="Cutoff date for PRs to consider in format YYYYMMDD", default=None)
    args = parser.parse_args()
    main(**vars(args))
