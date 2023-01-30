# Copyright (c) 2020 IBM Corp. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Compliance Github service helper."""

import json
import secrets
from collections import OrderedDict
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from compliance.utils.credentials import Config
from compliance.utils.data_parse import deep_merge
from compliance.utils.http import BaseSession


class Github(object):
    """Github service helper class."""

    def __init__(self, config=None, base_url="https://github.com"):
        """Construct the Github service object."""
        if not config:
            config = Config()

        self.base_url = base_url
        api_url = "https://api.github.com"
        service = "github"
        if self.base_url != "https://github.com":
            service = "github_enterprise"
            api_url = f"{self.base_url}/api/v3/"
        self._creds = config[service]
        self.session = BaseSession(api_url)
        token = self._creds.token
        if hasattr(self._creds, "username"):
            self.session.auth = (self._creds.username, token)
        else:
            self.session.headers["Authorization"] = "token " + token
        self.session.headers.update(
            {"Accept": "application/vnd.github.inertia-preview+json"}
        )

    def extract_path_chunks(self, url):
        """Retrieve the path from the url."""
        if not url.startswith(self.base_url):
            raise ValueError(
                f'URL "{url}" is not valid. ' f'Expected base URL is: "{self.base_url}"'
            )
        return url.split(self.base_url)[1].strip("/").split("/")

    def extract_owner_repo(self, url):
        """Retrieve the owner (org) and repo from the url."""
        path_chunks = self.extract_path_chunks(url)
        if len(path_chunks) < 2:
            raise ValueError(
                f'URL "{url}" needs to include, at least, "<owner>/<repo>"'
            )
        return path_chunks[0:2]

    def extract_owner_repo_issue(self, url):
        """Retrieve the owner (org), repo and issue number from the url."""
        path_chunks = self.extract_path_chunks(url)
        if len(path_chunks) != 4 or path_chunks[2] != "issues":
            raise ValueError(
                f'URL "{url}" ' 'needs to include "<owner>/<repo>/issues/<number>"'
            )
        owner, repo, _, issue_number = path_chunks
        return owner, repo, issue_number

    def get_all_projects(self, repo_path):
        """
        Retrieve all GH repo projects.

        repo_path looks like: my-gh-org/my-gh-repo
        """
        owner, repo = repo_path.split("/")

        # /repos/:owner/:repo/projects
        return self._make_request("get", "/".join(["repos", owner, repo, "projects"]))

    def get_project(self, project, org=False):
        """
        Retrieve the GH org or org/repo project.

        For a repo project the project variable looks like:
            my-gh-org/my-gh-repo/projects/1

        For an org project the project variable looks like:
            my-gh-org/projects/1
        """
        pieces = []
        if org:
            owner, _, number = project.split("/")
            # /orgs/:org/projects
            pieces = ["orgs", owner]
        else:
            owner, repo, _, number = project.split("/")
            # /repos/:owner/:repo/projects
            pieces = ["repos", owner, repo]
        pieces.append("projects")
        r = self._make_request("get", "/".join(pieces))
        return [x["id"] for x in r if x["number"] == int(number)][0]

    def get_columns(self, project_id):
        """Retrieve the columns for a project."""
        return self._make_request(
            "get", "/".join(["projects", str(project_id), "columns"])
        )

    def get_all_cards(self, columns):
        """Retrieve all cards for a given list of project columns."""
        cards = OrderedDict()
        for column_id in columns:
            cards[column_id] = self.get_cards(column_id)
        return cards

    def get_cards(self, column_id):
        """Retrieve all cards for a given project column."""
        return self._paginate_api(
            "/".join(["projects", "columns", str(column_id), "cards"])
        )

    def move_card(self, card, to_column_id):
        """Move a card from one project column to another."""
        data = {"position": "bottom", "column_id": to_column_id}
        return self._make_request(
            "post",
            "/".join(["projects", "columns", "cards", str(card), "moves"]),
            json=data,
        )

    def add_card(self, column_id, message=None, issue=0):
        """Create a card in a project column."""
        data = {}
        if issue > 0:
            data = {"content_id": issue, "content_type": "Issue"}
        else:
            data = {"note": message}
        return self._make_request(
            "post",
            "/".join(["projects", "columns", str(column_id), "cards"]),
            json=data,
        )

    def add_milestone(self, owner, repo, milestone):
        """Create a repository milestone."""
        return self._make_request(
            "post", "/".join(["repos", owner, repo, "milestones"]), json=milestone
        )

    def list_milestones(
        self, owner, repo, state="open", sort="due_on", direction="asc"
    ):
        """Retrieve a repository's milestones."""
        return self._paginate_api(
            "/".join(["repos", owner, repo, "milestones"]),
            **{"state": state, "sort": sort, "direction": direction},
        )

    def add_issue(self, owner, repo, title, body="", annotation=None, **kwargs):
        """Create a repository issue."""
        issue = {"title": title, "body": body}
        issue.update(kwargs)
        if annotation:
            issue["body"] = self._annotate_body(issue["body"], annotation)
        return self._make_request(
            "POST", "/".join(["repos", owner, repo, "issues"]), json=issue
        )

    def patch_issue(self, owner, repo, issue, annotation=None, **params):
        """Edit a repository issue."""
        if annotation and "body" in params:
            params["body"] = self._annotate_body(params["body"], annotation)
        return self._make_request(
            "PATCH", "/".join(["repos", owner, repo, "issues", str(issue)]), json=params
        )

    def get_issue(self, owner, repo, issue, parse_annotations=False):
        """
        Retrieve the content and metadata for a repository issue.

        If parse_annotations is True, then returns (issue, body, annotations),
        where body is the body with the JSON annotations removed, and
        annotations is a dictionary of the annotations. The annotations will
        be an empty dictionary if there aren't any.
        """
        issue = self._make_request(
            "get", "/".join(["repos", owner, repo, "issues", str(issue)])
        )
        if parse_annotations:
            body, annotations = extract_annotations(issue["body"])
            return issue, body, annotations
        return issue

    def update_annotations(self, owner, repo, issue, annotations):
        """
        Update the body of an existing issue, only changing the annotations.

        If there are no existing annotations, the annotation block will be
        added. If there is existing annotations, the given annotations will
        be merged into them.
        """
        _, body, old_anno = self.get_issue(owner, repo, issue, parse_annotations=True)
        new_anno = deep_merge(old_anno, annotations)
        return self.patch_issue(owner, repo, issue, annotation=new_anno, body=body)

    def get_issue_comments(self, owner, repo, issue, parse_annotations=False):
        """Retrieve a repository issue's comments."""
        comments = self._paginate_api(
            "/".join(["repos", owner, repo, "issues", str(issue), "comments"])
        )
        if parse_annotations:
            annotated_comments = []
            # TODO: make this actually work...
            for comment in comments:
                body, annotations = extract_annotations(comment["body"])
                annotated_comments.extend((body, annotations))
            return comments, annotated_comments
        return comments

    def get_issues_page(self, owner, repo, **kwargs):
        """Retrieve a repository's issues by page."""
        params = kwargs
        # get the page number or default to 1
        params["page"] = params.get("page", 1)
        response = self._make_request(
            "get",
            "/".join(["repos", owner, repo, "issues"]),
            parse=False,
            params=params,
        )
        return response

    def get_all_issues(self, owner, repo, **kwargs):
        """Retrieve all issues for a repository."""
        all_issues = {}
        page = 1
        response = self.get_issues_page(owner, repo, page=page, **kwargs)
        max_page = 1
        if "Link" in response.headers:
            # Link is only present if there are multiple pages
            link = response.headers["Link"]
            urls = link.replace(">", "").replace("<", "").split()
            parsed_url = urlparse(urls[2].strip(";"))
            max_page = int(parse_qs(parsed_url.query)["page"][0])
        while response:
            for i in response.json():
                all_issues[i["number"]] = i
            page += 1
            if page > max_page:
                response = False
            else:
                response = self.get_issues_page(owner, repo, page=page, **kwargs)
        return all_issues

    def search_issues(self, query, sort=None, order=None, owner=None, repo=None):
        """
        Perform a search against all issues based on the query provided.

        If an owner and repo are passed in, then restrict the results to
        that repo. Note that this can also be done in the query directly.
        """
        if not query:
            raise ValueError("Must specify a query")
        if owner and repo:
            query += f" repo:{owner}/{repo}"
        return self._paginate_api("search/issues", q=query, sort=sort, order=order)

    def add_issue_comment(self, owner, repo, issue, body, annotation=None):
        """Create a comment for a repository issue."""
        if annotation:
            body = self._annotate_body(body, annotation)
        return self._make_request(
            "POST",
            "/".join(["repos", owner, repo, "issues", str(issue), "comments"]),
            json={"body": body},
        )

    def create_project(self, repo, name, body="", org=False):
        """Create a repository project."""
        owner, repo = repo.split("/")
        return self.creates_for_project(
            "/".join(["repos", owner, repo, "projects"]), {"name": name, "body": body}
        )

    def create_column(self, project_id, column, org=False):
        """Create a project column."""
        return self.creates_for_project(
            "/".join(["projects", str(project_id), "columns"]), {"name": column}
        )

    def creates_for_project(self, url, data, org=False):
        """Create a repository project based on a properly formed url."""
        if org:
            raise NotImplementedError("orgs not supported yet")
        return self._make_request("post", url, json=data)

    def rand_color(self):
        """Generate a random color for labels."""
        return (
            f"{secrets.randbelow(255):02X}"
            f"{secrets.randbelow(255):02X}"
            f"{secrets.randbelow(255):02X}"
        )

    def create_label(self, repo, name, org=False):
        """Create a label within a repository."""
        return self.creates_for_project(
            "/".join(["repos", repo, "labels"]),
            {"name": name, "color": self.rand_color()},
        )

    def apply_labels(self, repo, issue, *labels):
        """
        Add label(s) to an issue.

        repo looks like: my-gh-org/my-gh-repo
        issue is an issue number (not id)
        API takes a json list of labels
        POST /repos/:owner/:repo/issues/:number/labels
        """
        response = self._make_request(
            "post",
            "/".join(["repos", repo, "issues", str(issue), "labels"]),
            json={"labels": labels},
        )

        return response

    def remove_labels(self, repo, issue, *labels):
        """
        Remove label(s) from an issue.

        repo looks like: my-gh-org/my-gh-repo
        issue is an issue number (not id)
        API takes a json list of labels
        POST /repos/:owner/:repo/issues/:number/labels
        """
        for line in labels:
            response = self._make_request(
                "delete",
                "/".join(["repos", repo, "issues", str(issue), "labels", line]),
            )
        # Each response has all the labels, so only return the last one
        return response

    def get_repo_details(self, repo):
        """
        Retrieve a repository's metadata.

        :param repo: the organization/repository as a string.

        :returns: the repository's metadata details.
        """
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        return self._make_request("get", f"repos/{repo}")

    def get_commit_details(self, repo, since, branch="master", path=None):
        """
        Retrieve a repository branch's commit details since a given date/time.

        :param repo: the organization/repository as a string.
        :param since: the starting date/time as a datetime.
        :param branch: the branch as a string.  Defaults to master.
        :param path: if provided, only commits for the path will be returned.

        :returns: the repo branch's commit details since a given date/time.
        """
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        opts = {"since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "sha": branch}
        if path:
            opts["path"] = path
        return self._make_request("get", f"repos/{repo}/commits", params=opts)

    def get_pull_requests(self, repo, since=None, **kwargs):
        """
        Retrieve a repository's pull request information.

        :param repo: the organization/repository as a string.
        :param since: the starting date/time of a pull request as a datetime.
        :param kwargs: key/value pairs of GH pulls API accepted params
        :returns: Repository pull request metadata
        """
        api_url = f'repos/{repo.strip("/")}/pulls'
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        if not since:
            return self._paginate_api(api_url, **kwargs)
        pull_requests = []
        params = {**kwargs}
        params["page"] = kwargs.get("page", 1)
        # Sort results by "created" in descending order
        params["sort"] = "created"
        params["direction"] = "desc"
        response = self._make_request("get", api_url, parse=False, params=params)
        max_page = 1
        if "Link" in response.headers:
            # Link is only present if there are multiple pages
            link = response.headers["Link"]
            urls = link.replace(">", "").replace("<", "").split()
            parsed_url = urlparse(urls[2].strip(";"))
            max_page = int(parse_qs(parsed_url.query)["page"][0])
        while response:
            for pull_request in response.json():
                created_at = datetime.strptime(
                    pull_request["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                )
                # Filter based on provided since datetime
                if created_at < since:
                    response = None
                    break
                pull_requests.append(pull_request)
            params["page"] += 1
            if params["page"] > max_page:
                response = None
            else:
                response = self._make_request(
                    "get", api_url, parse=False, params=params
                )
        return pull_requests

    def get_branch_protection_details(self, repo, branch="master"):
        """
        Retrieve a repository branch's branch protection details.

        :param repo: the organization/repository as a string.
        :param branch: the branch as a string.

        :returns: the repository branch's branch protection details.
        """
        self.session.headers.update(
            {"Accept": "application/vnd.github.zzzax-preview+json"}
        )
        return self._make_request("get", f"repos/{repo}/branches/{branch}/protection")

    def make_request(self, method, url, parse=True, **kwargs):
        """
        Perform a REST call to the Github API.

        :param method: HTTP request method
        :param url: The URL to make the request to
        :param parse: Return the JSON response content, defaults to True.  If
          False then the entire response is returned
        :param kwargs: Additional arguments added directly to the request call

        :returns: response content from the request made
        """
        return self._make_request(method, url, parse, **kwargs)

    def paginate_api(self, api_url, **kwargs):
        """
        Perform GET calls handling pagination.

        :param api_url: The URL to make the GET request to
        :param kwargs: Additional arguments added directly to the request call

        :returns: Combined paginated JSON content
        """
        return self._paginate_api(api_url, **kwargs)

    def _make_request(self, method, url, parse=True, **kwargs):
        r = self.session.request(method, url, **kwargs)
        r.raise_for_status()
        if parse:
            return r.json()
        return r

    def _annotate_body(self, body, annotation):
        anno_str = json.dumps(annotation, indent=2)
        return f"```application/json+utilitarian\n{anno_str}\n```\n{body}"

    def _paginate_api(self, api_url, **kwargs):
        params = kwargs
        params["page"] = params.get("page", 1)
        response = self._make_request("get", api_url, parse=False, params=params)
        max_page = 1
        all_items = []
        if "Link" in response.headers:
            # Link is only present if there are multiple pages
            link = response.headers["Link"]
            urls = link.replace(">", "").replace("<", "").split()
            parsed_url = urlparse(urls[2].strip(";"))
            max_page = int(parse_qs(parsed_url.query)["page"][0])
        while response:
            if api_url.startswith("search/"):
                all_items.extend(response.json()["items"])
            else:
                all_items.extend(response.json())
            params["page"] += 1
            if params["page"] > max_page:
                response = False
            else:
                response = self._make_request(
                    "get", api_url, parse=False, params=params
                )
        return all_items


def extract_annotations(content):
    """
    Retrieve JSON annotations from a string (issue body).

    Returns the remaining content without the annotations,
    and then the annotations themselves as a dictionary.
    """
    body = []
    annotations_json = ""
    started = False
    stopped = False
    for line in content.splitlines():
        if line == "```application/json+utilitarian":
            started = True
            continue
        if line == "```" and started:
            stopped = True
            started = False
            continue
        if started and not stopped:
            annotations_json += line
        else:
            body.append(line)

    content_no_annotations = "\n".join(body)
    if annotations_json:
        annotations = json.loads(annotations_json, object_pairs_hook=OrderedDict)
    else:
        annotations = OrderedDict({})

    return content_no_annotations, annotations
