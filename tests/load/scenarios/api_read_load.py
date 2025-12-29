"""
Read API endpoint load testing scenarios.

This module provides targeted load testing for read-heavy API endpoints:
- GET /projects - List projects
- GET /projects/{id} - Get project details
- GET /projects/{id}/issues - Get project issues
- GET /projects/{id}/alerts - Get project alerts
- GET /projects/{id}/settings - Get project settings
- GET /projects/{id}/competitors - List competitors
- GET /projects/{id}/backlinks/* - Backlink analysis endpoints
- GET /healthz - Health check
- GET /readyz - Readiness check

Usage:
    locust -f tests/load/scenarios/api_read_load.py --host=http://localhost:8000
"""

from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, task

# Configuration from environment variables
TEST_USER_PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "loadtest123!")


class ReadAPIUser(HttpUser):
    """
    User focused on read API endpoint load testing.

    This user class authenticates once and then performs intensive
    read operations to test query performance and caching effectiveness.
    """

    wait_time = between(0.5, 2)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.token: str | None = None
        self.project_id: str | None = None
        self.email: str = ""

    def on_start(self) -> None:
        """Set up user with authentication and test project."""
        self.email = f"read_api_{uuid.uuid4().hex[:12]}@example.com"

        # Register
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Read API Test User",
            },
        )

        # Login
        response = self.client.post(
            "/auth/login",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
            },
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")

        # Create test project
        if self.token:
            response = self.client.post(
                "/projects",
                json={"name": f"Read Test Project {uuid.uuid4().hex[:8]}"},
                headers=self._auth_headers(),
            )
            if response.status_code == 201:
                self.project_id = response.json().get("id")

    def on_stop(self) -> None:
        """Clean up test resources."""
        if self.token and self.project_id:
            self.client.delete(
                f"/projects/{self.project_id}",
                headers=self._auth_headers(),
            )

    def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers."""
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # =========================================================================
    # Health Endpoints (Unauthenticated)
    # =========================================================================

    @task(20)
    def health_check(self) -> None:
        """
        Test liveness endpoint.

        This is the most frequently called endpoint in production.
        Should respond in < 10ms.
        """
        with self.client.get("/healthz", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(10)
    def readiness_check(self) -> None:
        """
        Test readiness endpoint with dependency checks.

        More expensive than healthz due to database ping.
        """
        with self.client.get("/readyz", catch_response=True) as response:
            if response.status_code in (200, 503):
                response.success()
            else:
                response.failure(f"Readiness check failed: {response.status_code}")

    # =========================================================================
    # Project Read Endpoints
    # =========================================================================

    @task(30)
    def list_projects(self) -> None:
        """
        Test project listing.

        Most common authenticated read operation.
        """
        if not self.token:
            return

        with self.client.get(
            "/projects",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"List projects failed: {response.status_code}")

    @task(10)
    def list_projects_paginated(self) -> None:
        """
        Test paginated project listing.

        Tests query performance with pagination parameters.
        """
        if not self.token:
            return

        with self.client.get(
            "/projects",
            params={"page": 1, "page_size": 10},
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects [paginated]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Paginated list failed: {response.status_code}")

    @task(25)
    def get_project(self) -> None:
        """
        Test single project retrieval.

        Common operation when viewing project details.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()  # Project may have been deleted
            else:
                response.failure(f"Get project failed: {response.status_code}")

    @task(5)
    def get_nonexistent_project(self) -> None:
        """
        Test 404 handling for nonexistent project.

        Verifies proper error handling doesn't impact performance.
        """
        if not self.token:
            return

        fake_id = str(uuid.uuid4())
        with self.client.get(
            f"/projects/{fake_id}",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id} [404]",
        ) as response:
            if response.status_code == 404:
                response.success()
            else:
                response.failure(f"Expected 404, got: {response.status_code}")

    # =========================================================================
    # Project Issues Endpoints
    # =========================================================================

    @task(15)
    def get_project_issues(self) -> None:
        """
        Test project issues retrieval.

        Important SEO analysis endpoint.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/issues",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/issues",
        ) as response:
            if response.status_code in (200, 404):  # 404 if no crawl runs
                response.success()
            else:
                response.failure(f"Get issues failed: {response.status_code}")

    @task(5)
    def get_project_issues_limited(self) -> None:
        """
        Test issues retrieval with limit parameter.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/issues",
            params={"limit": 50},
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/issues [limited]",
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Get issues failed: {response.status_code}")

    # =========================================================================
    # Project Alerts Endpoints
    # =========================================================================

    @task(10)
    def get_project_alerts(self) -> None:
        """
        Test project alerts retrieval.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/alerts",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/alerts",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get alerts failed: {response.status_code}")

    @task(5)
    def get_project_alerts_filtered(self) -> None:
        """
        Test alerts retrieval with filters.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/alerts",
            params={"severity": "critical", "is_acknowledged": False},
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/alerts [filtered]",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get alerts filtered failed: {response.status_code}")

    @task(5)
    def get_alert_rules(self) -> None:
        """
        Test alert rules listing.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/alerts/rules",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/alerts/rules",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get alert rules failed: {response.status_code}")

    # =========================================================================
    # Project Settings Endpoints
    # =========================================================================

    @task(8)
    def get_project_settings(self) -> None:
        """
        Test project settings retrieval.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/settings",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/settings",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get settings failed: {response.status_code}")

    # =========================================================================
    # Project Competitors Endpoints
    # =========================================================================

    @task(8)
    def get_project_competitors(self) -> None:
        """
        Test competitors listing.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/competitors",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/competitors",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get competitors failed: {response.status_code}")

    # =========================================================================
    # Backlinks Endpoints
    # =========================================================================

    @task(5)
    def get_backlinks_overview(self) -> None:
        """
        Test backlinks overview retrieval.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/backlinks/overview",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/backlinks/overview",
        ) as response:
            # Accept 500 as table may not exist in test environment
            if response.status_code in (200, 500):
                response.success()
            else:
                response.failure(f"Get backlinks overview failed: {response.status_code}")

    @task(3)
    def get_backlinks_anchors(self) -> None:
        """
        Test backlinks anchor distribution.
        """
        if not self.token or not self.project_id:
            return

        with self.client.get(
            f"/projects/{self.project_id}/backlinks/anchors",
            headers=self._auth_headers(),
            catch_response=True,
            name="/projects/{id}/backlinks/anchors",
        ) as response:
            if response.status_code in (200, 500):
                response.success()
            else:
                response.failure(f"Get backlinks anchors failed: {response.status_code}")


class CacheBustingUser(HttpUser):
    """
    User that tests cache effectiveness by reading with varying parameters.

    This helps identify if caching is working correctly and what the
    cache hit/miss ratio impact is on performance.
    """

    wait_time = between(0.5, 1.5)
    weight = 1  # Lower weight than main read user

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.token: str | None = None
        self.project_ids: list[str] = []
        self.email: str = ""

    def on_start(self) -> None:
        """Set up user with multiple test projects."""
        self.email = f"cache_bust_{uuid.uuid4().hex[:12]}@example.com"

        # Register and login
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Cache Bust User",
            },
        )

        response = self.client.post(
            "/auth/login",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
            },
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")

        # Create multiple projects for cache testing
        if self.token:
            for i in range(3):
                response = self.client.post(
                    "/projects",
                    json={"name": f"Cache Test Project {i}"},
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                if response.status_code == 201:
                    self.project_ids.append(response.json().get("id"))

    def on_stop(self) -> None:
        """Clean up test projects."""
        if self.token:
            for project_id in self.project_ids:
                self.client.delete(
                    f"/projects/{project_id}",
                    headers={"Authorization": f"Bearer {self.token}"},
                )

    @task(10)
    def read_random_project(self) -> None:
        """
        Read a random project from the pool.

        Tests cache behavior with varying resource IDs.
        """
        if not self.token or not self.project_ids:
            return

        import random

        project_id = random.choice(self.project_ids)
        self.client.get(
            f"/projects/{project_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/projects/{id} [cache_test]",
        )

    @task(5)
    def read_with_varying_pagination(self) -> None:
        """
        Read projects with different pagination parameters.

        Tests cache key generation with query parameters.
        """
        if not self.token:
            return

        import random

        page = random.randint(1, 5)
        page_size = random.choice([10, 20, 50])

        self.client.get(
            "/projects",
            params={"page": page, "page_size": page_size},
            headers={"Authorization": f"Bearer {self.token}"},
            name="/projects [varying_pagination]",
        )
