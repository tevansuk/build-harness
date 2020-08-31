#!/usr/bin/env python3
# This script require python3, click, json and yaml installed
# pip3 install click pyyaml
import click
import json
import logging
import os
import subprocess
import sys
import yaml

log = logging.getLogger("github-automated-workflow")
log.setLevel(logging.DEBUG)

log.addHandler(logging.FileHandler("log/github-automated-workflow.log"))
log.addHandler(logging.StreamHandler(sys.stdout))

try:
    workflow_data = yaml.safe_load(open('workflow.yaml'))
except Exception:
    log.exception('Failed to load workflow.yaml')


@click.group(help='Single point of entry')
def main():
    pass


@main.group()
def mp():
    pass


@main.command()
def approve():
    log.info('Approving PRs')
    for repo in os.listdir('mp'):
        repo_path = os.path.join('mp', repo, 'plan', 'planned')
        if not os.path.isdir(os.path.join('mp', repo)):
            continue

        pr_approve(repo, repo_path)


@main.command(help='')
def tests():
    log.info('Running tests')
    for repo in os.listdir('mp'):
        repo_path = os.path.join('mp', repo, 'plan', 'planned')
        if not os.path.isdir(os.path.join('mp', repo)):
            continue

        pr_number = get_pr_number(repo_path)
        pr_run_tests(repo, pr_number, repo_path)


@mp.command(help='')
def init():
    log.info('Running init')
    repository_search = workflow_data["github"]["repository_search"]
    log.info(f'\nFinding repositories matching search {repository_search}')
    subprocess.check_call(f'mp init --repo-search {repository_search}', shell=True)

    log.debug('\nStarting to clone found repositories')
    subprocess.check_call('mp clone', shell=True)


@mp.command(help='')
def plan():
    branch = workflow_data["github"]["branch"]
    commit_message = workflow_data["github"]["commit_message"]
    subprocess.check_call(f'mp plan -b {branch} -m "{commit_message}" -- sh -c $PWD/migration.sh', shell=True)


@mp.command(help='')
def push():
    if not os.path.exists('pr-body.md'):
        raise Exception('pr-body.md doesnt exist')

    log.info('Starting mp push')

    assignee = workflow_data['github']['pr']['reviewers'][0]
    subprocess.check_call(
        f'mp push -b pr-body.md -a {assignee}',
        shell=True,
    )

    labels = {
        'labels': workflow_data['github']['pr'].get('labels')
    }
    reviewers = {
        'reviewers': workflow_data['github']['pr']['reviewers'],
        'team_reviewers': workflow_data['github']['pr']['team_reviewers']
    }

    for repo in os.listdir('mp'):
        repo_path = os.path.join('mp', repo, 'plan', 'planned')
        if not os.path.isdir(os.path.join('mp', repo)):
            continue


        pr_number = get_pr_number(repo_path)

        pr_add_labels(labels, pr_number, repo_path)
        pr_add_reviewers(pr_number, repo_path, reviewers)
        if workflow_data['tests']:
            pr_run_tests(repo, pr_number, repo_path)


# Helpers
def pr_add_reviewers(pr_number, repo_path, reviewers):
    log.info('Adding reviewers to PR')
    subprocess.check_call(
        f'''echo '{json.dumps(reviewers)}' | gh api -X POST repos/:owner/:repo/pulls/{pr_number}/requested_reviewers --input -''',
        cwd=repo_path,
        shell=True,
    )


def pr_add_labels(labels, pr_number, repo_path):
    log.info('Adding labels to PR')
    subprocess.check_call(
        f'''echo '{json.dumps(labels)}' | gh api -X PATCH repos/:owner/:repo/issues/{pr_number} --input -''',
        cwd=repo_path,
        shell=True
    )


def pr_run_tests(repo, pr_number, repo_path):
    log.info(f'Running tests in {repo}.')
    subprocess.check_call(
        f'gh api -X POST repos/:owner/:repo/issues/{pr_number}/comments -f body="/test all"',
        cwd=repo_path,
        shell=True
    )


def get_pr_number(repo_path):
    pr_number = subprocess.check_output(
        'gh pr create 2>&1 | tail -n1 | sed "s#.*pull/##"',
        cwd=repo_path,
        shell=True
    ).decode('utf8').strip()
    log.info(f'{repo_path} has PR {pr_number} on current branch.')
    return pr_number


def pr_approve(repo, repo_path):
    log.info(f'Approved PR for {repo}.')
    subprocess.check_call(
        f'gh pr review -a',
        cwd=repo_path,
        shell=True
    )


if __name__ == '__main__':
    os.makedirs('log', exist_ok=True)
    try:
        main()
    except Exception as ex:
        log.exception('\n\nFailed execution, got exception:')