"""
Crawl trigger and write API load testing scenarios.

This module provides targeted load testing for write-heavy API endpoints:
- POST /projects - Create project
- PATCH /projects/{id} - Update project
- DELETE /projects/{id} - Delete project
- POST /projects/{id}/sites - Add site
- POST /projects/{id}/competitors - Add competitor
- POST /projects/{id}/alerts/rules - Create alert rule
- PUT /projects/{id}/settings - Update settings

Note: Actual crawl triggering endpoints would be added when the crawl
worker integration is complete.

Usage:
    locust -f tests/load/scenarios/crawl_load.py --host=http://localhost:8000
"""

from __future__ import annotations

import os
import random
import uuid

from locust import HttpUser, between, task

# Configuration from environment variables
TEST_USER_PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "loadtest123!")


class WriteAPIUser(HttpUser):
    """
    User focused on write API endpoint load testing.

    This user class tests the throughput and latency of write operations
    including project CRUD, settings updates, and resource creation.
    """

    wait_time = between(1, 3)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.token: str | None = None
        self.project_ids: list[str] = []
        self.email: str = ""

    def on_start(self) -> None:
        """Set up user with authentication."""
        self.email = f"write_api_{uuid.uuid4().hex[:12]}@example.com"

        # Register
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Write API Test User",
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

    def on_stop(self) -> None:
        """Clean up all created projects."""
        if self.token:
            for project_id in self.project_ids:
                self.client.delete(
                    f"/projects/{project_id}",
                    headers=self._auth_headers(),
                )

    def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers."""
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # =========================================================================
    # Project CRUD Operations
    # =========================================================================

    @task(20)
    def create_project(self) -> None:
        """
        Test project creation.

        This is a common write operation for new users.
        """
        if not self.token:
            return

        with self.client.post(
            "/projects",
            json={"name": f"Load Test Project {uuid.uuid4().hex[:8]}"},
            headers=self._auth_headers(),
            catch_response=True,
            name="POST /projects",
        ) as response:
            if response.status_code == 201:
                project_id = response.json().get("id")
                if project_id:
                    self.project_ids.append(project_id)
                response.success()
            else:
                response.failure(f"Create project failed: {response.status_code}")

    @task(15)
    def update_project(self) -> None:
        """
        Test project update.

        Updates name of a random existing project.
        """
        if not self.token or not self.project_ids:
            return

        project_id = random.choice(self.project_ids)
        with self.client.patch(
            f"/projects/{project_id}",
            json={"name": f"Updated Project {uuid.uuid4().hex[:4]}"},
            headers=self._auth_headers(),
            catch_response=True,
            name="PATCH /projects/{id}",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Project may have been deleted by another task
                response.success()
            else:
                response.failure(f"Update project failed: {response.status_code}")

    @task(5)
    def delete_project(self) -> None:
        """
        Test project deletion.

        Deletes a random project if we have more than 2.
        """
        if not self.token or len(self.project_ids) < 3:
            return

        project_id = self.project_ids.pop()
        with self.client.delete(
            f"/projects/{project_id}",
            headers=self._auth_headers(),
            catch_response=True,
            name="DELETE /projects/{id}",
        ) as response:
            if response.status_code == 204:
                response.success()
            elif response.status_code == 404:
                response.success()  # Already deleted
            else:
                response.failure(f"Delete project failed: {response.status_code}")

    # =========================================================================
    # Site Management
    # =========================================================================

    @task(10)
    def add_site(self) -> None:
        """
        Test adding a site to a project.
        """
        if not self.token or not self.project_ids:
            return

        project_id = random.choice(self.project_ids)
        domain = f"site{uuid.uuid4().hex[:6]}.com"

        with self.client.post(
            f"/projects/{project_id}/sites",
            json={"domain": domain, "base_url": f"https://{domain}"},
            headers=self._auth_headers(),
            catch_response=True,
            name="POST /projects/{id}/sites",
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code in (404, 409):
                response.success()  # Project deleted or duplicate
            else:
                response.failure(f"Add site failed: {response.status_code}")

    # =========================================================================
    # Competitor Management
    # =========================================================================

    @task(10)
    def add_competitor(self) -> None:
        """
        Test adding a competitor to a project.
        """
        if not self.token or not self.project_ids:
            return

        project_id = random.choice(self.project_ids)
        domain = f"competitor{uuid.uuid4().hex[:6]}.com"

        with self.client.post(
            f"/projects/{project_id}/competitors",
            json={"domain": domain},
            headers=self._auth_headers(),
            catch_response=True,
            name="POST /projects/{id}/competitors",
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code in (404, 409):
                response.success()  # Project deleted or duplicate
            else:
                response.failure(f"Add competitor failed: {response.status_code}")

    # =========================================================================
    # Alert Rules
    # =========================================================================

    @task(8)
    def create_alert_rule(self) -> None:
        """
        Test creating an alert rule.
        """
        if not self.token or not self.project_ids:
            return

        project_id = random.choice(self.project_ids)
        rule_types = ["visibility_drop", "ctr_opportunity", "regression"]

        with self.client.post(
            f"/projects/{project_id}/alerts/rules",
            json={
                "rule_type": random.choice(rule_types),
                "config": {
                    "threshold": round(random.uniform(10, 50), 1),
                    "min_impressions": random.randint(50, 500),
                },
                "is_enabled": True,
            },
            headers=self._auth_headers(),
            catch_response=True,
            name="POST /projects/{id}/alerts/rules",
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code in (400, 404):
                response.success()  # Invalid rule type or project deleted
            else:
                response.failure(f"Create alert rule failed: {response.status_code}")

    # =========================================================================
    # Settings Management
    # =========================================================================

    @task(8)
    def update_settings(self) -> None:
        """
        Test updating project settings.
        """
        if not self.token or not self.project_ids:
            return

        project_id = random.choice(self.project_ids)

        with self.client.put(
            f"/projects/{project_id}/settings",
            json={
                "crawl_depth": random.randint(1, 5),
                "max_pages": random.randint(100, 1000),
                "respect_robots_txt": True,
                "user_agent": "LoadTestBot/1.0",
            },
            headers=self._auth_headers(),
            catch_response=True,
            name="PUT /projects/{id}/settings",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in (404, 422):
                response.success()  # Project deleted or validation error
            else:
                response.failure(f"Update settings failed: {response.status_code}")


class BurstWriteUser(HttpUser):
    """
    User that generates burst write traffic.

    Use this to test how the system handles sudden spikes in write operations.
    """

    wait_time = between(0.2, 0.8)  # Short wait time for burst testing
    weight = 1  # Low weight by default

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.token: str | None = None
        self.project_ids: list[str] = []
        self.email: str = ""

    def on_start(self) -> None:
        """Set up user for burst testing."""
        self.email = f"burst_{uuid.uuid4().hex[:12]}@example.com"

        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Burst Test User",
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

    def on_stop(self) -> None:
        """Clean up burst test resources."""
        if self.token:
            for project_id in self.project_ids:
                self.client.delete(
                    f"/projects/{project_id}",
                    headers={"Authorization": f"Bearer {self.token}"},
                )

    @task
    def rapid_project_creation(self) -> None:
        """
        Rapidly create projects to test write throughput.

        Warning: This generates high database load.
        """
        if not self.token:
            return

        with self.client.post(
            "/projects",
            json={"name": f"Burst Project {uuid.uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name="POST /projects [burst]",
        ) as response:
            if response.status_code == 201:
                project_id = response.json().get("id")
                if project_id:
                    self.project_ids.append(project_id)
                response.success()
            elif response.status_code == 429:
                # Rate limited - expected under burst
                response.success()
            else:
                response.failure(f"Burst create failed: {response.status_code}")


class MixedWorkloadUser(HttpUser):
    """
    User that performs a realistic mix of read and write operations.

    This simulates real-world usage patterns with appropriate read/write ratios.
    """

    wait_time = between(1, 4)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.token: str | None = None
        self.project_id: str | None = None
        self.email: str = ""

    def on_start(self) -> None:
        """Set up user with authentication and a test project."""
        self.email = f"mixed_{uuid.uuid4().hex[:12]}@example.com"

        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Mixed Workload User",
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

        if self.token:
            response = self.client.post(
                "/projects",
                json={"name": "Mixed Test Project"},
                headers={"Authorization": f"Bearer {self.token}"},
            )
            if response.status_code == 201:
                self.project_id = response.json().get("id")

    def on_stop(self) -> None:
        """Clean up test resources."""
        if self.token and self.project_id:
            self.client.delete(
                f"/projects/{self.project_id}",
                headers={"Authorization": f"Bearer {self.token}"},
            )

    def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers."""
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # Read operations (80% of traffic)
    @task(40)
    def list_projects(self) -> None:
        """List projects (read)."""
        if self.token:
            self.client.get("/projects", headers=self._auth_headers())

    @task(20)
    def get_project(self) -> None:
        """Get project details (read)."""
        if self.token and self.project_id:
            self.client.get(
                f"/projects/{self.project_id}",
                headers=self._auth_headers(),
            )

    @task(10)
    def get_issues(self) -> None:
        """Get project issues (read)."""
        if self.token and self.project_id:
            with self.client.get(
                f"/projects/{self.project_id}/issues",
                headers=self._auth_headers(),
                catch_response=True,
            ) as response:
                if response.status_code in (200, 404):
                    response.success()

    @task(10)
    def get_alerts(self) -> None:
        """Get project alerts (read)."""
        if self.token and self.project_id:
            self.client.get(
                f"/projects/{self.project_id}/alerts",
                headers=self._auth_headers(),
            )

    # Write operations (20% of traffic)
    @task(5)
    def update_project(self) -> None:
        """Update project (write)."""
        if self.token and self.project_id:
            self.client.patch(
                f"/projects/{self.project_id}",
                json={"name": f"Updated {uuid.uuid4().hex[:4]}"},
                headers=self._auth_headers(),
            )

    @task(3)
    def add_competitor(self) -> None:
        """Add competitor (write)."""
        if self.token and self.project_id:
            domain = f"comp{uuid.uuid4().hex[:6]}.com"
            with self.client.post(
                f"/projects/{self.project_id}/competitors",
                json={"domain": domain},
                headers=self._auth_headers(),
                catch_response=True,
            ) as response:
                if response.status_code in (201, 404, 409):
                    response.success()

    @task(2)
    def update_settings(self) -> None:
        """Update settings (write)."""
        if self.token and self.project_id:
            with self.client.put(
                f"/projects/{self.project_id}/settings",
                json={"crawl_depth": random.randint(1, 5), "max_pages": 500},
                headers=self._auth_headers(),
                catch_response=True,
            ) as response:
                if response.status_code in (200, 404, 422):
                    response.success()
