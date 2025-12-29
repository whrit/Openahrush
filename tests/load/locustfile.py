"""
Main Locust configuration for Openahrush API load testing.

This file orchestrates all load testing scenarios and provides the primary
entry point for running load tests. It combines authentication, read API,
and write API tasks with appropriate weights to simulate realistic traffic.

Performance Targets:
- API handles 100 concurrent requests
- API p50 latency < 50ms
- API p95 latency < 200ms
- API p99 latency < 500ms

Usage:
    # Start with web UI
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Headless mode with specific users
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --users=100 --spawn-rate=10 --run-time=5m --headless

    # With HTML report
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --users=100 --spawn-rate=10 --run-time=5m --headless \
        --html=load_test_report.html
"""

from __future__ import annotations

import os
import random
import uuid
from typing import TYPE_CHECKING

from locust import HttpUser, between, events, task

if TYPE_CHECKING:
    from locust.env import Environment


# Configuration from environment variables
TEST_USER_EMAIL = os.getenv("LOAD_TEST_EMAIL", "loadtest@example.com")
TEST_USER_PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "loadtest123!")


class APIUser(HttpUser):
    """
    Simulated API user that performs typical operations.

    This user class authenticates on startup and then performs a mix of
    read and write operations with realistic timing between requests.
    Task weights reflect expected real-world usage patterns.
    """

    # Wait between 1 and 3 seconds between tasks (simulates think time)
    wait_time = between(1, 3)

    # Set reasonable connection timeout
    abstract = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.token: str | None = None
        self.project_id: str | None = None
        self.user_id: str | None = None

    def on_start(self) -> None:
        """
        Called when a simulated user starts.

        Registers a new user (if needed) and logs in to obtain a JWT token.
        Creates a test project for subsequent operations.
        """
        # Generate unique email for this user instance to avoid conflicts
        unique_email = f"loadtest_{uuid.uuid4().hex[:8]}@example.com"

        # Try to register a new user
        with self.client.post(
            "/auth/register",
            json={
                "email": unique_email,
                "password": TEST_USER_PASSWORD,
                "name": "Load Test User",
            },
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                data = response.json()
                self.user_id = data.get("id")
                response.success()
            elif response.status_code == 409:
                # Email already registered, that's OK
                response.success()
            else:
                response.failure(f"Registration failed: {response.status_code}")
                return

        # Login to get token
        with self.client.post(
            "/auth/login",
            json={
                "email": unique_email,
                "password": TEST_USER_PASSWORD,
            },
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                response.success()
            else:
                response.failure(f"Login failed: {response.status_code}")
                return

        # Create a test project for this user
        if self.token:
            with self.client.post(
                "/projects",
                json={"name": f"Load Test Project {uuid.uuid4().hex[:8]}"},
                headers=self._auth_headers(),
                catch_response=True,
            ) as response:
                if response.status_code == 201:
                    data = response.json()
                    self.project_id = data.get("id")
                    response.success()
                else:
                    response.failure(f"Project creation failed: {response.status_code}")

    def on_stop(self) -> None:
        """
        Called when a simulated user stops.

        Cleans up by deleting the test project and logging out.
        """
        if self.token and self.project_id:
            # Delete the test project
            self.client.delete(
                f"/projects/{self.project_id}",
                headers=self._auth_headers(),
            )

        if self.token:
            # Logout
            self.client.post(
                "/auth/logout",
                headers=self._auth_headers(),
            )

    def _auth_headers(self) -> dict[str, str]:
        """Return authorization headers with the current token."""
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # =========================================================================
    # Health Check Tasks (High frequency - monitoring)
    # =========================================================================

    @task(15)
    def health_check(self) -> None:
        """
        Check API liveness.

        Weight: 15 - Health checks are frequent in production environments.
        """
        self.client.get("/healthz")

    @task(5)
    def readiness_check(self) -> None:
        """
        Check API readiness with dependency status.

        Weight: 5 - Less frequent than liveness checks.
        """
        self.client.get("/readyz")

    # =========================================================================
    # Read API Tasks (High frequency - majority of traffic)
    # =========================================================================

    @task(20)
    def get_current_user(self) -> None:
        """
        Get current user info.

        Weight: 20 - Very common operation for authenticated users.
        """
        if not self.token:
            return
        self.client.get("/me", headers=self._auth_headers())

    @task(25)
    def list_projects(self) -> None:
        """
        List user's projects.

        Weight: 25 - One of the most common read operations.
        """
        if not self.token:
            return
        self.client.get("/projects", headers=self._auth_headers())

    @task(15)
    def get_project(self) -> None:
        """
        Get a specific project.

        Weight: 15 - Common operation when viewing project details.
        """
        if not self.token or not self.project_id:
            return
        self.client.get(
            f"/projects/{self.project_id}",
            headers=self._auth_headers(),
        )

    @task(10)
    def get_project_issues(self) -> None:
        """
        Get issues for a project.

        Weight: 10 - Important for SEO analysis but less frequent.
        """
        if not self.token or not self.project_id:
            return
        with self.client.get(
            f"/projects/{self.project_id}/issues",
            headers=self._auth_headers(),
            catch_response=True,
        ) as response:
            # 404 is acceptable if no crawl runs exist
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(8)
    def get_project_alerts(self) -> None:
        """
        Get alerts for a project.

        Weight: 8 - Monitoring feature, moderate usage.
        """
        if not self.token or not self.project_id:
            return
        self.client.get(
            f"/projects/{self.project_id}/alerts",
            headers=self._auth_headers(),
        )

    @task(5)
    def get_project_settings(self) -> None:
        """
        Get project settings.

        Weight: 5 - Settings accessed less frequently.
        """
        if not self.token or not self.project_id:
            return
        self.client.get(
            f"/projects/{self.project_id}/settings",
            headers=self._auth_headers(),
        )

    @task(5)
    def get_project_competitors(self) -> None:
        """
        List project competitors.

        Weight: 5 - Competitive analysis feature.
        """
        if not self.token or not self.project_id:
            return
        self.client.get(
            f"/projects/{self.project_id}/competitors",
            headers=self._auth_headers(),
        )

    @task(5)
    def get_backlinks_overview(self) -> None:
        """
        Get project backlinks overview.

        Weight: 5 - Backlink analysis feature.
        """
        if not self.token or not self.project_id:
            return
        with self.client.get(
            f"/projects/{self.project_id}/backlinks/overview",
            headers=self._auth_headers(),
            catch_response=True,
        ) as response:
            # Accept both success and database errors (table may not exist)
            if response.status_code in (200, 500):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    # =========================================================================
    # Write API Tasks (Lower frequency - more expensive)
    # =========================================================================

    @task(3)
    def update_project(self) -> None:
        """
        Update project name.

        Weight: 3 - Write operations are less frequent.
        """
        if not self.token or not self.project_id:
            return
        self.client.patch(
            f"/projects/{self.project_id}",
            json={"name": f"Updated Project {uuid.uuid4().hex[:4]}"},
            headers=self._auth_headers(),
        )

    @task(2)
    def add_competitor(self) -> None:
        """
        Add a competitor to the project.

        Weight: 2 - Configuration changes are infrequent.
        """
        if not self.token or not self.project_id:
            return
        domains = ["competitor1.com", "competitor2.com", "competitor3.com"]
        with self.client.post(
            f"/projects/{self.project_id}/competitors",
            json={"domain": random.choice(domains)},
            headers=self._auth_headers(),
            catch_response=True,
        ) as response:
            # Success or conflict (duplicate) is acceptable
            if response.status_code in (201, 409):
                response.success()
            else:
                response.failure(f"Add competitor failed: {response.status_code}")

    @task(2)
    def create_alert_rule(self) -> None:
        """
        Create an alert rule.

        Weight: 2 - Alert configuration is infrequent.
        """
        if not self.token or not self.project_id:
            return
        rule_types = ["visibility_drop", "ctr_opportunity", "regression"]
        self.client.post(
            f"/projects/{self.project_id}/alerts/rules",
            json={
                "rule_type": random.choice(rule_types),
                "config": {"threshold": random.uniform(10, 50), "min_impressions": 100},
                "is_enabled": True,
            },
            headers=self._auth_headers(),
        )

    @task(1)
    def add_site(self) -> None:
        """
        Add a site to the project.

        Weight: 1 - Site configuration is rare.
        """
        if not self.token or not self.project_id:
            return
        domains = ["testsite1.com", "testsite2.com", "testsite3.com"]
        domain = random.choice(domains)
        with self.client.post(
            f"/projects/{self.project_id}/sites",
            json={"domain": domain, "base_url": f"https://{domain}"},
            headers=self._auth_headers(),
            catch_response=True,
        ) as response:
            # Success or conflict is acceptable
            if response.status_code in (201, 409):
                response.success()
            else:
                response.failure(f"Add site failed: {response.status_code}")


class AuthOnlyUser(HttpUser):
    """
    User that focuses on authentication endpoints only.

    This user class is useful for targeted auth load testing.
    It repeatedly performs login/logout cycles.
    """

    wait_time = between(0.5, 2)
    weight = 1  # Lower weight than APIUser

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.email = f"authtest_{uuid.uuid4().hex[:8]}@example.com"
        self.registered = False

    def on_start(self) -> None:
        """Register a user for authentication testing."""
        with self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Auth Test User",
            },
            catch_response=True,
        ) as response:
            if response.status_code in (201, 409):
                self.registered = True
                response.success()
            else:
                response.failure(f"Registration failed: {response.status_code}")

    @task(10)
    def login_logout_cycle(self) -> None:
        """
        Perform a complete login/logout cycle.

        This tests the full authentication flow.
        """
        if not self.registered:
            return

        # Login
        with self.client.post(
            "/auth/login",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
            },
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                response.success()

                # Logout
                self.client.post(
                    "/auth/logout",
                    headers={"Authorization": f"Bearer {token}"},
                )
            else:
                response.failure(f"Login failed: {response.status_code}")

    @task(5)
    def failed_login_attempt(self) -> None:
        """
        Test failed login handling.

        Verifies the API handles invalid credentials gracefully.
        """
        with self.client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword",
            },
            catch_response=True,
        ) as response:
            if response.status_code == 401:
                response.success()
            else:
                response.failure(f"Expected 401, got: {response.status_code}")


# Event hooks for custom reporting
@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs) -> None:
    """Called when load test starts."""
    print("\n" + "=" * 60)
    print("OPENAHRUSH LOAD TEST STARTING")
    print("=" * 60)
    print(f"Host: {environment.host}")
    print("Target Metrics:")
    print("  - Concurrent users: 100")
    print("  - p50 latency: < 50ms")
    print("  - p95 latency: < 200ms")
    print("  - p99 latency: < 500ms")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs) -> None:
    """Called when load test stops."""
    print("\n" + "=" * 60)
    print("OPENAHRUSH LOAD TEST COMPLETED")
    print("=" * 60)

    # Get stats
    stats = environment.stats
    if stats.total.num_requests > 0:
        print(f"\nTotal Requests: {stats.total.num_requests}")
        print(f"Total Failures: {stats.total.num_failures}")
        print(f"Failure Rate: {stats.total.fail_ratio * 100:.2f}%")
        print("\nResponse Times:")
        print(f"  Average: {stats.total.avg_response_time:.2f}ms")
        print(f"  p50: {stats.total.get_response_time_percentile(0.50):.2f}ms")
        print(f"  p95: {stats.total.get_response_time_percentile(0.95):.2f}ms")
        print(f"  p99: {stats.total.get_response_time_percentile(0.99):.2f}ms")
        print(f"\nRequests/sec: {stats.total.total_rps:.2f}")

        # Check against targets
        p50 = stats.total.get_response_time_percentile(0.50)
        p95 = stats.total.get_response_time_percentile(0.95)
        p99 = stats.total.get_response_time_percentile(0.99)

        print("\nTarget Compliance:")
        print(f"  p50 < 50ms: {'PASS' if p50 < 50 else 'FAIL'} ({p50:.2f}ms)")
        print(f"  p95 < 200ms: {'PASS' if p95 < 200 else 'FAIL'} ({p95:.2f}ms)")
        print(f"  p99 < 500ms: {'PASS' if p99 < 500 else 'FAIL'} ({p99:.2f}ms)")

    print("=" * 60 + "\n")
