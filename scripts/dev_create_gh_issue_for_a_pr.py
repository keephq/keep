"""
It's a script for the Keep developers to create a GitHub issue for a given pull request.

Example PR: https://github.com/keephq/keep/pull/3511
Example Issue: https://github.com/keephq/keep/issues/3512

- Creates an issue
- Adds the issue URL to the PR description
- Assigns the issue to the authenticated user
- Adds the label "👨🏻‍💻 Internal" to the issue

Usage:
    python scripts/dev_create_gh_issue_for_a_pr.py <pr_number>
    
Uses local GitHub CLI (gh) for making API requests: https://cli.github.com/
"""

import re
import json
import argparse
import subprocess

GITHUB_API_URL = "https://api.github.com"
REPO_OWNER = "keephq"
REPO_NAME = "keep"


def remove_pr_prefix(pr_title):
    return re.sub(r"^\w+(\(\w+\))?:\s*", "", pr_title)


def gh_make_request(url, method="GET", data=None):
    command = [
        "gh",
        "api",
        "-X",
        method,
        url,
    ]

    if data:
        for key, value in data.items():
            if isinstance(value, list):
                for v in value:
                    command.extend(["-f", f"{key}[]={v}"])
            else:
                command.extend(["-f", f"{key}={value}"])

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        return json.loads(result.stdout)
    else:
        print(command)
        print(f"Failed to make GitHub API request: {result.stderr}")
        return None


def get_pr_title(pr_number):
    pr_url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}"
    response = gh_make_request(pr_url)
    return response["title"]


def get_authenticated_username():
    user_url = f"{GITHUB_API_URL}/user"
    response = gh_make_request(user_url)
    return response["login"]


def get_pr_details(pr_number):
    pr_url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}"
    response = gh_make_request(pr_url)
    return response


def update_pr_description(pr_number, issue_url):
    pr_details = get_pr_details(pr_number)
    if pr_details["body"] is None:
        pr_details["body"] = ""
    new_body = f"{pr_details['body']}\n\nclose {issue_url}"
    update_data = {"body": new_body}
    update_url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}"
    response = response = gh_make_request(update_url, "PATCH", update_data)
    return response


def create_issue_for_pr(pr_number):

    pr_title = get_pr_title(pr_number)

    issue_data = {
        "title": "[👨🏻‍💻 Internal]: " + remove_pr_prefix(pr_title),
        "body": "This issue is created for tracking purposes for the PR: #"
        + str(pr_number)
        + "\n\n Please don't pick it up.",
        "assignees": [get_authenticated_username()],
    }

    issue_url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/issues"

    return gh_make_request(issue_url, "POST", issue_data)


if __name__ == "__main__":
    # Argument parser for CLI input
    parser = argparse.ArgumentParser(
        description="Create a GitHub issue for a given pull request."
    )
    parser.add_argument("pr_number", type=int, help="The pull request number")

    # Parse CLI arguments
    args = parser.parse_args()

    # Create the issue using parsed arguments
    issue = create_issue_for_pr(args.pr_number)
    update_pr_description(args.pr_number, issue["html_url"])
