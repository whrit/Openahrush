"""
Authentication endpoint load testing scenarios.

This module provides targeted load testing for authentication endpoints:
- POST /auth/register - User registration
- POST /auth/login - User authentication
- POST /auth/logout - Session termination
- GET /me - Current user info

Usage:
    locust -f tests/load/scenarios/auth_load.py --host=http://localhost:8000
"""

from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, task

# Configuration from environment variables
TEST_USER_PASSWORD = os.getenv("LOAD_TEST_PASSWORD", "loadtest123!")


class AuthLoadUser(HttpUser):
    """
    User focused on authentication endpoint load testing.

    This user class performs intensive testing of auth endpoints to verify:
    - Registration throughput and handling of duplicate emails
    - Login latency and JWT token generation
    - Logout handling (stateless acknowledgment)
    - Current user info retrieval
    """

    wait_time = between(0.5, 2)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.email: str = ""
        self.token: str | None = None
        self.user_id: str | None = None

    def on_start(self) -> None:
        """Generate unique credentials for this user instance."""
        self.email = f"auth_load_{uuid.uuid4().hex[:12]}@example.com"

    @task(5)
    def register_new_user(self) -> None:
        """
        Test user registration endpoint.

        Each call uses a new unique email to test registration throughput.
        """
        unique_email = f"reg_{uuid.uuid4().hex[:12]}@example.com"
        with self.client.post(
            "/auth/register",
            json={
                "email": unique_email,
                "password": TEST_USER_PASSWORD,
                "name": "Load Test User",
            },
            catch_response=True,
            name="/auth/register",
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 409:
                # Duplicate email (unlikely with UUID but possible)
                response.success()
            elif response.status_code == 422:
                # Validation error
                response.failure(f"Validation error: {response.text}")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def register_duplicate_email(self) -> None:
        """
        Test registration with duplicate email (conflict handling).

        Verifies the API correctly returns 409 for duplicate registrations.
        """
        # First, ensure the user exists
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Load Test User",
            },
            name="/auth/register [setup]",
        )

        # Then try to register again
        with self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Load Test User",
            },
            catch_response=True,
            name="/auth/register [duplicate]",
        ) as response:
            if response.status_code == 409:
                response.success()
            else:
                response.failure(f"Expected 409, got: {response.status_code}")

    @task(20)
    def login_success(self) -> None:
        """
        Test successful login flow.

        This is the most common auth operation and should be highly optimized.
        """
        # Ensure user exists
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Load Test User",
            },
            name="/auth/register [setup]",
        )

        # Login
        with self.client.post(
            "/auth/login",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
            },
            catch_response=True,
            name="/auth/login",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                if not self.token:
                    response.failure("No access_token in response")
                else:
                    response.success()
            else:
                response.failure(f"Login failed: {response.status_code}")

    @task(5)
    def login_invalid_credentials(self) -> None:
        """
        Test login with invalid credentials.

        Verifies the API correctly handles invalid login attempts.
        """
        with self.client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword",
            },
            catch_response=True,
            name="/auth/login [invalid]",
        ) as response:
            if response.status_code == 401:
                response.success()
            else:
                response.failure(f"Expected 401, got: {response.status_code}")

    @task(3)
    def login_wrong_password(self) -> None:
        """
        Test login with correct email but wrong password.

        Verifies password validation is working correctly.
        """
        # Ensure user exists
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Load Test User",
            },
            name="/auth/register [setup]",
        )

        with self.client.post(
            "/auth/login",
            json={
                "email": self.email,
                "password": "definitely_wrong_password",
            },
            catch_response=True,
            name="/auth/login [wrong_password]",
        ) as response:
            if response.status_code == 401:
                response.success()
            else:
                response.failure(f"Expected 401, got: {response.status_code}")

    @task(10)
    def get_current_user(self) -> None:
        """
        Test current user info retrieval.

        Requires a valid token. Tests the /me endpoint performance.
        """
        if not self.token:
            # Need to login first
            self.client.post(
                "/auth/register",
                json={
                    "email": self.email,
                    "password": TEST_USER_PASSWORD,
                    "name": "Load Test User",
                },
                name="/auth/register [setup]",
            )
            response = self.client.post(
                "/auth/login",
                json={
                    "email": self.email,
                    "password": TEST_USER_PASSWORD,
                },
                name="/auth/login [setup]",
            )
            if response.status_code == 200:
                self.token = response.json().get("access_token")

        if self.token:
            with self.client.get(
                "/me",
                headers={"Authorization": f"Bearer {self.token}"},
                catch_response=True,
                name="/me",
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Get user failed: {response.status_code}")

    @task(3)
    def get_current_user_invalid_token(self) -> None:
        """
        Test /me endpoint with invalid token.

        Verifies proper 401 handling for invalid tokens.
        """
        with self.client.get(
            "/me",
            headers={"Authorization": "Bearer invalid_token_12345"},
            catch_response=True,
            name="/me [invalid_token]",
        ) as response:
            if response.status_code == 401:
                response.success()
            else:
                response.failure(f"Expected 401, got: {response.status_code}")

    @task(8)
    def logout(self) -> None:
        """
        Test logout endpoint.

        Logout is stateless (JWT-based) so this tests the acknowledgment flow.
        """
        if not self.token:
            # Need to login first
            self.client.post(
                "/auth/register",
                json={
                    "email": self.email,
                    "password": TEST_USER_PASSWORD,
                    "name": "Load Test User",
                },
                name="/auth/register [setup]",
            )
            response = self.client.post(
                "/auth/login",
                json={
                    "email": self.email,
                    "password": TEST_USER_PASSWORD,
                },
                name="/auth/login [setup]",
            )
            if response.status_code == 200:
                self.token = response.json().get("access_token")

        if self.token:
            with self.client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {self.token}"},
                catch_response=True,
                name="/auth/logout",
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Logout failed: {response.status_code}")

    @task(10)
    def full_auth_cycle(self) -> None:
        """
        Test complete authentication cycle.

        Performs: register -> login -> get user -> logout
        This tests the full flow that a real user would experience.
        """
        cycle_email = f"cycle_{uuid.uuid4().hex[:12]}@example.com"

        # Register
        reg_response = self.client.post(
            "/auth/register",
            json={
                "email": cycle_email,
                "password": TEST_USER_PASSWORD,
                "name": "Cycle Test User",
            },
            name="/auth/register [cycle]",
        )
        if reg_response.status_code not in (201, 409):
            return

        # Login
        login_response = self.client.post(
            "/auth/login",
            json={
                "email": cycle_email,
                "password": TEST_USER_PASSWORD,
            },
            name="/auth/login [cycle]",
        )
        if login_response.status_code != 200:
            return

        token = login_response.json().get("access_token")
        if not token:
            return

        headers = {"Authorization": f"Bearer {token}"}

        # Get current user
        self.client.get("/me", headers=headers, name="/me [cycle]")

        # Logout
        self.client.post("/auth/logout", headers=headers, name="/auth/logout [cycle]")


class AuthSpikeUser(HttpUser):
    """
    User that generates spike traffic on auth endpoints.

    Use this to test how the system handles sudden bursts of auth requests.
    """

    wait_time = between(0.1, 0.5)  # Very short wait time for spike testing
    weight = 1  # Low weight by default

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.email = f"spike_{uuid.uuid4().hex[:8]}@example.com"

    @task
    def rapid_login(self) -> None:
        """
        Rapidly attempt logins to generate spike load.

        Warning: This generates high load - use with caution.
        """
        # Ensure user exists
        self.client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
                "name": "Spike Test User",
            },
            name="/auth/register [spike]",
        )

        # Rapid login attempts
        with self.client.post(
            "/auth/login",
            json={
                "email": self.email,
                "password": TEST_USER_PASSWORD,
            },
            catch_response=True,
            name="/auth/login [spike]",
        ) as response:
            if response.status_code in (200, 429):  # 429 = rate limited
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
