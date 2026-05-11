import os
from typing import Any, Dict, List, Optional

import requests


class GitHubClient:
    """Thin read-only GitHub REST API client with pagination support."""

    def __init__(
        self,
        token: Optional[str] = None,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.owner = owner or os.getenv("GITHUB_OWNER")
        self.repo = repo or os.getenv("GITHUB_REPO")
        self.base_url = "https://api.github.com"

        if not self.token:
            raise ValueError("Missing GitHub token. Set GITHUB_TOKEN.")
        if not self.owner or not self.repo:
            raise ValueError("Missing repository config. Set GITHUB_OWNER and GITHUB_REPO.")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        response = requests.get(url, headers=self._headers, params=params, timeout=30)
        if response.status_code >= 400:
            message = response.text[:300]
            raise RuntimeError(f"GitHub API request failed ({response.status_code}): {message}")
        return response

    def _graphql_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/graphql",
            headers=self._headers,
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        if response.status_code >= 400:
            message = response.text[:300]
            raise RuntimeError(f"GitHub GraphQL request failed ({response.status_code}): {message}")
        payload = response.json()
        if "errors" in payload:
            msg = str(payload["errors"])[:300]
            raise RuntimeError(f"GitHub GraphQL error: {msg}")
        return payload.get("data", {})

    def _get_paginated(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        url = f"{self.base_url}{path}"
        query = dict(params or {})
        query.setdefault("per_page", 100)

        while url:
            response = self._request(url, params=query)
            page_items = response.json()
            if isinstance(page_items, list):
                items.extend(page_items)
            else:
                break

            next_url = response.links.get("next", {}).get("url")
            url = next_url
            query = None

        return items

    def _repo_path(self, suffix: str) -> str:
        return f"/repos/{self.owner}/{self.repo}{suffix}"

    def get_issues(self) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path("/issues"), params={"state": "all"})

    def get_pulls(self) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path("/pulls"), params={"state": "all", "sort": "updated"})

    def get_pull(self, number: int) -> Dict[str, Any]:
        response = self._request(f"{self.base_url}{self._repo_path(f'/pulls/{number}')}")
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def get_pull_reviews(self, number: int) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path(f"/pulls/{number}/reviews"))

    def get_pull_review_comments(self, number: int) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path(f"/pulls/{number}/comments"))

    def get_labels(self) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path("/labels"))

    def get_milestones(self) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path("/milestones"), params={"state": "all"})

    def get_assignees(self) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path("/assignees"))

    def get_commits(self) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path("/commits"), params={"per_page": 100})

    def get_workflow_runs(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        url = f"{self.base_url}{self._repo_path('/actions/runs')}"
        query: Optional[Dict[str, Any]] = {"per_page": 100}
        while url:
            response = self._request(url, params=query)
            payload = response.json()
            runs = payload.get("workflow_runs", []) if isinstance(payload, dict) else []
            if isinstance(runs, list):
                items.extend(runs)
            next_url = response.links.get("next", {}).get("url")
            url = next_url
            query = None
        return items

    def get_issue_events(self, number: int) -> List[Dict[str, Any]]:
        return self._get_paginated(self._repo_path(f"/issues/{number}/events"))

    def get_issue_project_fields(self) -> Dict[int, Dict[str, str]]:
        """
        Returns mapping:
          issue_number -> {"sprint": "...", "size": "...", "project_status": "..."}
        Best-effort; if GraphQL/projects access is unavailable, returns empty mapping.
        """
        query = """
        query($owner: String!, $repo: String!, $cursor: String) {
          repository(owner: $owner, name: $repo) {
            issues(first: 100, after: $cursor, states: [OPEN, CLOSED], orderBy: {field: UPDATED_AT, direction: DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes {
                number
                projectItems(first: 20) {
                  nodes {
                    fieldValues(first: 50) {
                      nodes {
                        ... on ProjectV2ItemFieldSingleSelectValue {
                          name
                          field {
                            ... on ProjectV2SingleSelectField {
                              name
                            }
                          }
                        }
                        ... on ProjectV2ItemFieldIterationValue {
                          title
                          field {
                            ... on ProjectV2IterationField {
                              name
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        out: Dict[int, Dict[str, str]] = {}
        cursor: Optional[str] = None

        while True:
            data = self._graphql_request(
                query,
                variables={"owner": self.owner, "repo": self.repo, "cursor": cursor},
            )
            repo = (data or {}).get("repository") or {}
            issues = repo.get("issues") or {}
            nodes = issues.get("nodes") or []

            for issue in nodes:
                number = issue.get("number")
                if not number:
                    continue
                fields: Dict[str, str] = out.setdefault(int(number), {})
                items = ((issue.get("projectItems") or {}).get("nodes")) or []
                for item in items:
                    values = (((item or {}).get("fieldValues") or {}).get("nodes")) or []
                    for val in values:
                        field_obj = val.get("field") or {}
                        field_name = str(field_obj.get("name") or "").strip().lower()

                        if "name" in val:
                            value = str(val.get("name") or "").strip()
                        else:
                            value = str(val.get("title") or "").strip()
                        if not value:
                            continue

                        if "sprint" in field_name or "iteration" in field_name:
                            fields.setdefault("sprint", value)
                        elif field_name == "size":
                            fields.setdefault("size", value)
                        elif field_name == "status":
                            fields.setdefault("project_status", value)

            page_info = issues.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        return out
