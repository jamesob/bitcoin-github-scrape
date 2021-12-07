#!/usr/bin/env python3
"""
Quick-and-dirty script to scrape GitHub for all essential pull request and conversation
data.
"""
import os
import csv
import calendar
import time
import json
import datetime
import shutil
import sys
from pathlib import Path
from pprint import pprint

import github
from github.GithubException import RateLimitExceededException, GithubException

import logging

log = logging.getLogger('main')
log.setLevel(logging.DEBUG)
hand = logging.StreamHandler()
hand.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
hand.setFormatter(formatter)
log.addHandler(hand)


GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'bitcoin/bitcoin')
GIT_PATH = Path.home() / 'src' / 'bitcoin'
OUTPUT_DIR = Path.cwd() / 'output'


def main():
    g = github.Github(GITHUB_TOKEN)
    sleep_for_rate_limit(g)

    repo = g.get_repo(GITHUB_REPO)

    if len(sys.argv) > 1:
        pulls = [repo.get_pull(int(sys.argv[1]))]
    else:
        pulls = list(repo.get_pulls(state='all', sort='created', direction='desc'))
        log.info(f"saw {len(pulls)} pulls")

    for pr in pulls:
        log.info(f"processing PR {pr.number}")
        try:
            process_pull(pr)
        except RateLimitExceededException as e:
            log.warning(f"hit rate limit: {e}")
            time.sleep(5)
            sleep_for_rate_limit(g)
            process_pull(pr)
        except GithubException:
            log.exception("retrying PR")
            try:
                process_pull(pr)
            except Exception:
                log.exception(f"finally failed - skipping {pr.number}")
                Path("failed-prs.txt").write_text
                with open("failed-prs.txt", "a") as f:
                    print(pr.number, file=f)


def sleep_for_rate_limit(g):
    """Get our global rate-limit from GitHub and wait it out with a sleep if necessary."""
    core_rate_limit = g.get_rate_limit().core
    if core_rate_limit.remaining != 0:
        return

    log.warning("rate limit hit!")
    reset_timestamp = calendar.timegm(core_rate_limit.reset.timetuple())
    sleep_time = reset_timestamp - calendar.timegm(time.gmtime()) + 3
    log.warning(f"sleeping for {sleep_time / 60.} minutes")
    time.sleep(sleep_time)


def write_to_csv(path, data):
    with open(path, 'w') as f:
        writer = csv.writer(f)
        writer.writerows(data)


def body_for_csv(body: str) -> str:
    CHAR_LIMIT = 400  # enough to detect ACKs?
    return body.replace('\n', '\\n')[:CHAR_LIMIT]


def process_pull(pr):
    """
    Persist data related to a pull request. This serializes to disk the JSON
    representation of the PR as well as all comments, both "issue" (normal) and review.

    An abbreviated CSV format is also generated to allow convenient analysis.
    """
    dir = OUTPUT_DIR / str(pr.number)
    done_sentinel = dir / 'done'

    if done_sentinel.exists():
        log.debug(f"  {pr.number} already done")
        return
    elif dir.exists():
        shutil.rmtree(str(dir))
        log.debug(f"  removing partial dir for {pr.number}")

    dir.mkdir(parents=True)
    (dir / 'pr.json').write_text(json.dumps(pr.raw_data, indent=2))

    comments = list(pr.get_issue_comments())
    review_comments = list(pr.get_comments())

    all = comments + review_comments
    all_data = [i.raw_data for i in all]
    (dir / 'comments.json').write_text(json.dumps(all_data, indent=2))
    log.debug(f"  wrote {len(all_data)} comments")

    comment_abbrevs = []
    for c in all_data:
        username = c['user']['login'] if c['user'] else ''
        try:
            comment_abbrevs.append(
                (username, c['created_at'], body_for_csv(c['body']), c['html_url'], c['id'], c.get('path', '')))
        except Exception:
            log.warning(f"failed on {c}")
            raise

    write_to_csv(dir / 'comments_abbrev.csv', comment_abbrevs)

    commits = list(pr.get_commits())
    commits_data = [i.raw_data for i in commits]
    (dir / 'commits.json').write_text(json.dumps(commits_data, indent=2))
    log.debug(f"  wrote {len(commits_data)} commits")

    commits_abbrevs = []
    for c in commits_data:
        files = [f['filename'] for f in c['files']]
        author = c['commit']['author']
        author_name = author['name']
        if c['author']:
            author_name = c['author'].get('login', '')

        try:
            commits_abbrevs.append((c['sha'], author['date'], author_name, ','.join(files)))
        except Exception:
            log.warning(f"failed on {pprint(c)}")
            raise

    write_to_csv(dir / 'commits_abbrev.csv', commits_abbrevs)

    merged_by = ''
    merged_at = ''
    closed_at = pr.closed_at or ''

    if pr.merged:
        try:
            merged_by = pr.merged_by.login
        except Exception:
            # This will trip around PR 117; guess the user who merged isn't around anymore.
            pass
        merged_at = pr.merged_at

    labels = [i.name for i in pr.labels]

    pr_row = (
        pr.number, pr.created_at, pr.user.login, pr.title, ','.join(labels), closed_at, merged_at, merged_by)
    write_to_csv(dir / 'pr_abbrev.csv', [pr_row])
    log.debug(f"  finished PR: {pr_row}")

    done_sentinel.write_text(datetime.datetime.utcnow().isoformat())


if __name__ == '__main__':
    main()
