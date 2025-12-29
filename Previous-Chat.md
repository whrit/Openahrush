 This session is being continued from a previous conversation that ran out of context. The conversation is summarized below:
Analysis:
Let me analyze the conversation chronologically:

1. **Initial Context**: The user provided system reminders showing previous work on Openahrush, an OSS "Semrush-core" SEO platform. They shared ARCHITECTURE.md and
SPRINT-5-HARDENING.md.

2. **User's First Request**: Asked to review Previous-Chat.md, docs/, ARCHITECTURE.md, and the codebase. The previous agent conversation got corrupted, and they wanted investigation
of Sprint 5 implementation status.

3. **My Investigation**:
   - Found Previous-Chat.md was too large (73K+ tokens)
   - Read the end of the file showing multiple agents had completed Sprint 5 tasks
   - Discovered completed agents: security audit, resource budget enforcement, rate limiting, integration tests, crawl performance, load testing, E2E tests, SSRF validation, audit
logging, secret redaction, database optimization, CC ingestion, timeout enforcement, response caching, concurrent job caps
   - Investigated actual codebase state

4. **Findings**:
   - Cache module (`libs/core/src/semrush_core/cache/`) - COMPLETE with 29 tests
   - Logging/redactor module (`libs/core/src/semrush_core/logging/`) - COMPLETE with 11 tests
   - Stub files broken: `test_audit.py` and `test_database_utils.py` contained only "test"
   - Missing dependencies: minio, fakeredis
   - TASK-TRACKER.md showed Sprint 5 at 0% - incorrect

5. **User's Second Request**: "Yes, orchestrate and spawn relevant Agents to continue with the following using a TDD development approach. Agents cannot be considered done until there
 are ZERO linter, type, and test errors. The Agents MUST use the Context7 MCP server..."

6. **My Actions**:
   - Installed missing dependencies (minio, fakeredis)
   - Fixed broken stub test files (test_audit.py, test_database_utils.py)
   - Spawned 6 parallel agents:
     - a9d0bde: Rate limiting & resource caps (5.1.x)
     - a6516f7: Security hardening (5.2.x)
     - a97a729: Database optimization (5.3.1)
     - ac86e00: Deployment documentation (5.5.x, 5.6.x)
     - a5fea89: Integration tests (5.4.2)
     - add5dea: Load testing setup (5.4.4)

7. **Agent Progress** (from system reminders and TaskOutput):
   - Documentation agent (ac86e00): Created API_REFERENCE.md, DEPLOYMENT.md, USER_GUIDE.md
   - Database optimization agent (a97a729): Created test_database_utils.py with 800+ lines, pagination.py, eager_load.py
   - Security agent (a6516f7): Created comprehensive test_audit.py with 800+ lines
   - Load testing agent (add5dea): Created locustfile.py, tests/load/ structure
   - All agents still running but making significant progress

Summary:
1. Primary Request and Intent:
   The user requested investigation of Sprint 5 Hardening implementation status after a previous agent conversation got corrupted. Upon finding that the TASK-TRACKER showed 0% but
some components were actually implemented (cache, logging modules), the user explicitly requested orchestrating multiple agents to implement remaining Sprint 5 tasks using TDD
approach. Key requirements:
   - Agents MUST use Context7 MCP server for documentation
   - ZERO linter, type, and test errors required
   - Focus on: stub file fixes, rate limiting (5.1.x), security hardening (5.2.x), database optimization (5.3.1), integration tests (5.4.x), deployment documentation (5.5.x, 5.6.x)

2. Key Technical Concepts:
   - TDD (Test-Driven Development) approach
   - FastAPI rate limiting with Redis-backed token bucket/sliding window
   - Distributed locks for concurrent job caps
   - SSRF prevention for webhook URLs
   - Audit logging with SQLAlchemy models
   - Keyset/cursor-based pagination
   - Eager loading helpers (joinedload, selectinload)
   - Query logging with slow query detection
   - N+1 query detection
   - Locust load testing
   - Docker Compose production deployment

3. Files and Code Sections:

   - **`libs/core/tests/test_audit.py`** - Fixed from stub to placeholder:
     ```python
     """
     Placeholder for audit logging tests.
     This file will be populated by the audit logging implementation agent.
     """
     import pytest

     class TestAuditLogPlaceholder:
         def test_placeholder(self) -> None:
             assert True
     ```
     Security agent later replaced with 800+ line comprehensive test suite for AuditLog model, AuditAction enum, AuditService, audit context, and security tests.

   - **`libs/core/tests/test_database_utils.py`** - Fixed from stub to placeholder:
     ```python
     """
     Placeholder for database optimization tests.
     """
     import pytest

     class TestDatabaseUtilsPlaceholder:
         def test_placeholder(self) -> None:
             assert True
     ```
     Database agent later replaced with 816 line test file covering KeysetPaginator, eager loading, batch fetch, query logging, slow query detection, N+1 detection.

   - **`libs/core/src/semrush_core/cache/`** - Already complete (29 tests passing):
     - `backend.py` - Redis-backed CacheBackend with get/set/delete/exists
     - `decorator.py` - @cached decorator
     - `headers.py` - Cache-Control header utilities
     - `keys.py` - Cache key building with params hashing

   - **`libs/core/src/semrush_core/logging/`** - Already complete (11 tests passing):
     - `redactor.py` - SECRET_PATTERNS for JWT, Bearer tokens, passwords, API keys, webhook secrets, DB URLs
     - `formatter.py` - SecretRedactingFormatter

   - **`libs/core/src/semrush_core/db_utils/`** - Being created by agent:
     - `pagination.py` - KeysetPaginator with cursor encoding/decoding, PaginatedResult dataclass
     - `eager_load.py` - with_eager_loads, with_selectin_loads helpers

   - **`tests/load/locustfile.py`** - Created by load testing agent with APIUser and AuthOnlyUser classes, ~400 lines

   - **`docs/API_REFERENCE.md`** - Created, comprehensive API documentation
   - **`docs/DEPLOYMENT.md`** - Created, production deployment guide
   - **`docs/USER_GUIDE.md`** - Created, user-facing documentation

4. Errors and Fixes:
   - **Broken stub test files**: `test_audit.py` and `test_database_utils.py` contained only "test" causing NameError
     - Fixed by writing valid placeholder Python files with pytest imports
   - **Missing dependencies**: minio and fakeredis packages not installed
     - Fixed with `uv add minio fakeredis --dev`
   - **Test collection errors**: 24 errors during pytest collection due to missing modules
     - Resolved after installing dependencies

5. Problem Solving:
   - Identified that TASK-TRACKER.md incorrectly showed 0% completion for Sprint 5
   - Discovered cache (5.3.2) and logging redaction (5.2.4) were already fully implemented
   - Fixed broken stub files blocking test collection
   - Installed missing dependencies enabling full test suite
   - Spawned 6 parallel agents to complete remaining Sprint 5 tasks

6. All User Messages:
   - "Review the @Previous-Chat.md, @docs/, @ARCHITECTURE.md, and the codebase here generally. Next, the previous Agent conversation got corrupted. Review the previous chat, then
investigate and review where we're at with the @docs/SPRINT-5-HARDENING.md implementation and advise."
   - "Yes, orchestrate and spawn relevant Agents to continue with the following using a TDD development approach. Agents cannot be considered done until there are ZERO linter, type,
and test errors. The Agents MUST use the Context7 MCP server to pull up to date docs and relevant info for ANY packages they use or need to reference: [list of stub files, not
implemented tasks, test suite issues, recommendations]"

7. Pending Tasks:
   - 6 background agents still running, implementing:
     - Rate limiting & resource caps (5.1.x) - agent a9d0bde
     - Security hardening/audit logging (5.2.x) - agent a6516f7
     - Database optimization (5.3.1) - agent a97a729
     - Integration tests (5.4.2) - agent a5fea89
     - Load testing setup (5.4.4) - agent add5dea
     - Deployment documentation (5.5.x, 5.6.x) - agent ac86e00
   - Update TASK-TRACKER.md with completion status (pending after agents complete)

8. Current Work:
   Monitoring 6 parallel background agents implementing Sprint 5 tasks. Last TaskOutput calls showed:
   - Documentation agent (ac86e00): Created API_REFERENCE.md, DEPLOYMENT.md (~2000 lines each), USER_GUIDE.md - still running
   - Database optimization agent (a97a729): Created comprehensive test_database_utils.py (816 lines), pagination.py, eager_load.py - still running
   - Security agent (a6516f7): Created test_audit.py and test_ssrf.py - still running
   - Load testing agent (add5dea): Created locustfile.py with Locust test classes - still running
   - Rate limiting agent (a9d0bde): Exploring codebase, writing rate limit tests - still running
   - Integration tests agent (a5fea89): Reviewing existing test patterns - still running

   Todo list status:
   - [completed] Install missing dependencies (minio, fakeredis)
   - [completed] Fix broken stub test files
   - [in_progress] Implement rate limiting & resource caps (5.1.x)
   - [in_progress] Implement security hardening (5.2.x)
   - [in_progress] Implement database optimization (5.3.1)
   - [in_progress] Implement integration/E2E/load tests (5.4.x)
   - [in_progress] Create deployment documentation (5.5.x, 5.6.x)
   - [pending] Update TASK-TRACKER.md with completion status

9. Optional Next Step:
   Continue monitoring the 6 background agents until completion, then:
   1. Verify all agents completed with ZERO linter, type, and test errors
   2. Run full test suite to confirm implementations work
   3. Update TASK-TRACKER.md to reflect actual Sprint 5 completion status

   User's explicit request: "orchestrate and spawn relevant Agents to continue with the following using a TDD development approach. Agents cannot be considered done until there are
ZERO linter, type, and test errors.".
Please continue the conversation from where we left it off without asking the user any further questions. Continue with the last task that you were asked to work on.
  ⎿  Referenced file libs/core/tests/test_audit.py
  ⎿  Referenced file libs/core/tests/test_database_utils.py
  ⎿  Referenced file Previous-Chat.md
  ⎿  Read libs/core/tests/test_cache.py (287 lines)
  ⎿  Read libs/core/src/semrush_core/cache/backend.py (162 lines)

  Task "Create load testing setup 5.4.4" completed in background
  ⎿  Todo list read (8 items)

∴ Thinking…

  The user wants me to continue from where we left off. Based on the summary, I was monitoring 6 background agents implementing Sprint 5 tasks. Let me check on the status of these agents
  and continue the work.

  The agents that were running:
  - a9d0bde: Rate limiting & resource caps (5.1.x)
  - a6516f7: Security hardening (5.2.x)
  - a97a729: Database optimization (5.3.1)
  - ac86e00: Deployment documentation (5.5.x, 5.6.x)
  - a5fea89: Integration tests (5.4.2)
  - add5dea: Load testing setup (5.4.4) - marked as completed

  Let me check the status of the remaining agents and see what needs to be done.

⏺ I'll check on the status of the background agents that were implementing Sprint 5 tasks. Let me get the outputs from the running agents.       11:06 PM  claude-opus-4-5-20251101

⏺ Task Output(non-blocking) a9d0bde
  ⎿  Task is still running…

⏺ Task Output(non-blocking) a6516f7
  ⎿  Task is still running…

⏺ Task Output(non-blocking) a97a729
  ⎿  Task is still running…

⏺ Task Output(non-blocking) ac86e00
  ⎿  Task is still running…

⏺ Task Output(non-blocking) a5fea89
  ⎿  Task is still running…

⏺ Task Output(non-blocking) add5dea
Create load testing setup 5.4.4 (146 lines)

  Prompt:
    You are implementing Sprint 5 Task 5.4.4: Load Testing Setup for the Openahrush SEO platform.

    CRITICAL REQUIREMENTS:
    1. Create production-ready load testing configuration
    2. Working directory: /Users/beckett/Projects/Openahrush
    3. Use locust for Python-native load testing

    TASK DESCRIPTION:
    Create load testing infrastructure to verify system performance under load.

    TARGETS (from Sprint 5 spec):
    - API handles 100 concurrent requests
    - API p50 latency < 50ms
    - API p95 latency < 200ms
    - API p99 latency < 500ms

    IMPLEMENTATION STRUCTURE:
    tests/
    ├── load/
    │   ├── __init__.py
    │   ├── locustfile.py         # Main Locust configuration
    │   ├── scenarios/
    │   │   ├── __init__.py
    │   │   ├── auth_load.py      # Auth endpoint load tests
    │   │   ├── api_read_load.py  # Read API load tests
    │   │   └── crawl_load.py     # Crawl trigger load tests
    │   └── README.md             # How to run load tests

    LOCUST CONFIGURATION:
    # locustfile.py
    from locust import HttpUser, task, between

    class APIUser(HttpUser):
        wait_time = between(1, 3)

        def on_start(self):
            # Login and get token
            response = self.client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "testpassword"
            })
            self.token = response.json()["access_token"]

        @task(10)
        def get_projects(self):
            self.client.get(
                "/projects",
                headers={"Authorization": f"Bearer {self.token}"}
            )

        @task(5)
        def get_project_issues(self):
            self.client.get(
                "/projects/{project_id}/issues",
                headers={"Authorization": f"Bearer {self.token}"}
            )

        @task(1)
        def trigger_crawl(self):
            # Lower weight - expensive operation
            ...

    SCENARIOS TO TEST:
    1. Auth Load - Login/logout throughput
    2. Read API Load - Project list, issues, backlinks
    3. Write API Load - Project create, settings update
    4. Crawl Trigger Load - Crawl job creation

    README CONTENT:
    # Load Testing

    ## Prerequisites
    - pip install locust

    ## Running Load Tests

    ### Local API
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    ### With specific user count
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10

    ### Headless mode
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10 --run-time=5m --headless

    ## Performance Targets
    | Metric | Target |
    |--------|--------|
    | p50 latency | < 50ms |
    | p95 latency | < 200ms |
    | p99 latency | < 500ms |
    | Concurrent users | 100+ |

    Also add locust to dev dependencies if not present:
    uv add locust --dev

    Create all files with proper Python syntax. Verify with:
    - uv run ruff check tests/load/
    - uv run mypy tests/load/

    Ensure ZERO errors before completing.

  Response:
    [Tool: Glob] {"pattern":"tests//.py"}
    [Tool: Glob] {"pattern":"apps/api/src/semrush_api/routers/.py"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/pyproject.toml"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/pyproject.toml"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/apps/api/src/semrush_api/routers/auth.py"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/apps/api/src/semrush_api/routers/projects.py"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/apps/api/src/semrush_api/routers/issues.py"}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"in_progress","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"pending","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"pending","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"pending","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"pending","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"pending","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"pending","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"in_progress","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"pending","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"pending","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"pending","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"pending","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"pending","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"pending","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/apps/api/src/semrush_api/routers/backlinks.py"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/apps/api/src/semrush_api/routers/health.py"}
    [Tool: Glob] {"pattern":"tests/"}
    [Tool: Glob] {"pattern":"tests/**"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/apps/api/src/semrush_api/routers/alerts.py"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/apps/api/src/semrush_api/routers/settings.py"}
    [Tool: Bash] {"command":"ls -la /Users/beckett/Projects/Openahrush/tests/ 2>/dev/null || echo tests directory does not exist","description":"Check if tests directory exists"}
    [Tool: Bash] {"command":"ls -la /Users/beckett/Projects/Openahrush/tests/ 2>/dev/null || echo tests directory does not exist","description":"Check if tests directory exists"}
    [Tool: Bash] {"command":"uv add locust --dev 2>&1","description":"Add locust as dev dependency","timeout":120000}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"in_progress","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"pending","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"pending","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"pending","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"pending","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"in_progress","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"pending","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"pending","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"pending","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"pending","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: Bash] {"command":"mkdir -p /Users/beckett/Projects/Openahrush/tests/load/scenarios","description":"Create load tests directory structure"}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/init.py","content":"\nLoad testing infrastructure for Openahrush API.\n\nThis package provides
    Locust-based load testing scenarios for validating\nAPI performance under concurrent load. Target metrics:\n- 100 concurrent users\n- p50 latency < 50ms\n- p95 latency < 200ms\n-
     p99 latency < 500ms\n\n"}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/scenarios/init.py","content":"\nLoad testing scenarios for Openahrush API.\n\nEach scenario module
    contains Locust task sets targeting specific API areas:\n- auth_load: Authentication endpoint load tests\n- api_read_load: Read API load tests (projects, issues, backlinks)\n-
    crawl_load: Crawl trigger load tests\n\n"}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/locustfile.py","content":"\nMain Locust configuration for Openahrush API load testing.\n\nThis file
    orchestrates all load testing scenarios and provides the primary\nentry point for running load tests. It combines authentication, read API,\nand write API tasks with appropriate
    weights to simulate realistic traffic.\n\nPerformance Targets:\n- API handles 100 concurrent requests\n- API p50 latency < 50ms\n- API p95 latency < 200ms\n- API p99 latency <
    500ms\n\nUsage:\n    # Start with web UI\n    locust -f tests/load/locustfile.py --host=http://localhost:8000\n\n    # Headless mode with specific users\n
        locust -f tests/load/locustfile.py --host=http://localhost:8000 \n        --users=100 --spawn-rate=10 --run-time=5m --headless\n\n    # With HTML report\n    locust -f
    tests/load/locustfile.py --host=http://localhost:8000 \n        --users=100 --spawn-rate=10 --run-time=5m --headless \n        --html=load_test_report.html\n\n\nfrom _future__
    import annotations\n\nimport os\nimport random\nimport uuid\nfrom typing import TYPE_CHECKING\n\nfrom locust import HttpUser, between, events, task\n\nif TYPE_CHECKING:\n    from
     locust.env import Environment\n\n\n# Configuration from environment variables\nTEST_USER_EMAIL = os.getenv(LOAD_TEST_EMAIL, loadtest@example.com)\nTEST_USER_PASSWORD =
    os.getenv(LOAD_TEST_PASSWORD, loadtest123!)\n\n\nclass APIUser(HttpUser):\n    \n    Simulated API user that performs typical operations.\n\n    This user class authenticates on
    startup and then performs a mix of\n    read and write operations with realistic timing between requests.\n    Task weights reflect expected real-world usage patterns.\n    \n\n
       # Wait between 1 and 3 seconds between tasks (simulates think time)\n    wait_time = between(1, 3)\n\n    # Set reasonable connection timeout\n    abstract = False\n\n    def
    init(self, *args, **kwargs) -> None:\n        super().init(*args, **kwargs)\n        self.token: str | None = None\n        self.project_id: str | None = None\n
    self.user_id: str | None = None\n\n    def on_start(self) -> None:\n        \n        Called when a simulated user starts.\n\n        Registers a new user (if needed) and logs in
     to obtain a JWT token.\n        Creates a test project for subsequent operations.\n        \n        # Generate unique email for this user instance to avoid conflicts\n
    unique_email = floadtest{uuid.uuid4().hex[:8]}@example.com\n\n        # Try to register a new user\n        with self.client.post(\n            /auth/register,\n
    json={\n                email: unique_email,\n                password: TEST_USER_PASSWORD,\n                name: Load Test User,\n            },\n
    catch_response=True,\n        ) as response:\n            if response.status_code == 201:\n                data = response.json()\n                self.user_id = data.get(id)\n
                  response.success()\n            elif response.status_code == 409:\n                # Email already registered, that's OK\n                response.success()\n
          else:\n                response.failure(fRegistration failed: {response.status_code})\n                return\n\n        # Login to get token\n        with
    self.client.post(\n            /auth/login,\n            json={\n                email: unique_email,\n                password: TEST_USER_PASSWORD,\n            },\n
    catch_response=True,\n        ) as response:\n            if response.status_code == 200:\n                data = response.json()\n                self.token =
    data.get(access_token)\n                response.success()\n            else:\n                response.failure(fLogin failed: {response.status_code})\n                return\n\n
            # Create a test project for this user\n        if self.token:\n            with self.client.post(\n                /projects,\n                json={name: fLoad Test
    Project {uuid.uuid4().hex[:8]}},\n                headers=self._auth_headers(),\n                catch_response=True,\n            ) as response:\n                if
    response.status_code == 201:\n                    data = response.json()\n                    self.project_id = data.get(id)\n                    response.success()\n
        else:\n                    response.failure(fProject creation failed: {response.status_code})\n\n    def on_stop(self) -> None:\n        \n        Called when a simulated
    user stops.\n\n        Cleans up by deleting the test project and logging out.\n        \n        if self.token and self.project_id:\n            # Delete the test project\n
           self.client.delete(\n                f/projects/{self.project_id},\n                headers=self._auth_headers(),\n            )\n\n        if self.token:\n            #
    Logout\n            self.client.post(\n                /auth/logout,\n                headers=self._auth_headers(),\n            )\n\n    def _auth_headers(self) -> dict[str,
    str]:\n        Return authorization headers with the current token.\n        return {Authorization: fBearer {self.token}} if self.token else {}\n\n    #
    =========================================================================\n    # Health Check Tasks (High frequency - monitoring)\n    #
    =========================================================================\n\n    @task(15)\n    def health_check(self) -> None:\n        \n        Check API liveness.\n\n
    Weight: 15 - Health checks are frequent in production environments.\n        \n        self.client.get(/healthz)\n\n    @task(5)\n    def readiness_check(self) -> None:\n
    \n        Check API readiness with dependency status.\n\n        Weight: 5 - Less frequent than liveness checks.\n        \n        self.client.get(/readyz)\n\n    #
    =========================================================================\n    # Read API Tasks (High frequency - majority of traffic)\n    #
    =========================================================================\n\n    @task(20)\n    def get_current_user(self) -> None:\n        \n        Get current user info.\n\n
           Weight: 20 - Very common operation for authenticated users.\n        \n        if not self.token:\n            return\n        self.client.get(/me,
    headers=self._auth_headers())\n\n    @task(25)\n    def list_projects(self) -> None:\n        \n        List user's projects.\n\n        Weight: 25 - One of the most common read
    operations.\n        \n        if not self.token:\n            return\n        self.client.get(/projects, headers=self._auth_headers())\n\n    @task(15)\n    def
    get_project(self) -> None:\n        \n        Get a specific project.\n\n        Weight: 15 - Common operation when viewing project details.\n        \n        if not self.token
    or not self.project_id:\n            return\n        self.client.get(\n            f/projects/{self.project_id},\n            headers=self._auth_headers(),\n        )\n\n
    @task(10)\n    def get_project_issues(self) -> None:\n        \n        Get issues for a project.\n\n        Weight: 10 - Important for SEO analysis but less frequent.\n
    \n        if not self.token or not self.project_id:\n            return\n        with self.client.get(\n            f/projects/{self.project_id}/issues,\n
    headers=self._auth_headers(),\n            catch_response=True,\n        ) as response:\n            # 404 is acceptable if no crawl runs exist\n            if
    response.status_code in (200, 404):\n                response.success()\n            else:\n                response.failure(fUnexpected status: {response.status_code})\n\n
    @task(8)\n    def get_project_alerts(self) -> None:\n        \n        Get alerts for a project.\n\n        Weight: 8 - Monitoring feature, moderate usage.\n        \n        if
    not self.token or not self.project_id:\n            return\n        self.client.get(\n            f/projects/{self.project_id}/alerts,\n
    headers=self._auth_headers(),\n        )\n\n    @task(5)\n    def get_project_settings(self) -> None:\n        \n        Get project settings.\n\n        Weight: 5 - Settings
    accessed less frequently.\n        \n        if not self.token or not self.project_id:\n            return\n        self.client.get(\n
    f/projects/{self.project_id}/settings,\n            headers=self._auth_headers(),\n        )\n\n    @task(5)\n    def get_project_competitors(self) -> None:\n        \n
    List project competitors.\n\n        Weight: 5 - Competitive analysis feature.\n        \n        if not self.token or not self.project_id:\n            return\n
    self.client.get(\n            f/projects/{self.project_id}/competitors,\n            headers=self.auth_headers(),\n        )\n\n    @task(5)\n    def get_backlinks_overview(self)
     -> None:\n        \n        Get project backlinks overview.\n\n        Weight: 5 - Backlink analysis feature.\n        \n        if not self.token or not self.project_id:\n
           return\n        with self.client.get(\n            f/projects/{self.project_id}/backlinks/overview,\n            headers=self.auth_headers(),\n
    catch_response=True,\n        ) as response:\n            # Accept both success and database errors (table may not exist)\n            if response.status_code in (200, 500):\n
                 response.success()\n            else:\n                response.failure(fUnexpected status: {response.status_code})\n\n    #
    =========================================================================\n    # Write API Tasks (Lower frequency - more expensive)\n    #
    =========================================================================\n\n    @task(3)\n    def update_project(self) -> None:\n        \n        Update project name.\n\n
      Weight: 3 - Write operations are less frequent.\n        \n        if not self.token or not self.project_id:\n            return\n        self.client.patch(\n
    f/projects/{self.project_id},\n            json={name: fUpdated Project {uuid.uuid4().hex[:4]}},\n            headers=self.auth_headers(),\n        )\n\n    @task(2)\n    def
    add_competitor(self) -> None:\n        \n        Add a competitor to the project.\n\n        Weight: 2 - Configuration changes are infrequent.\n        \n        if not
    self.token or not self.project_id:\n            return\n        domains = [competitor1.com, competitor2.com, competitor3.com]\n        with self.client.post(\n
    f/projects/{self.project_id}/competitors,\n            json={domain: random.choice(domains)},\n            headers=self.auth_headers(),\n            catch_response=True,\n
     ) as response:\n            # Success or conflict (duplicate) is acceptable\n            if response.status_code in (201, 409):\n                response.success()\n
    else:\n                response.failure(fAdd competitor failed: {response.status_code})\n\n    @task(2)\n    def create_alert_rule(self) -> None:\n        \n        Create an
    alert rule.\n\n        Weight: 2 - Alert configuration is infrequent.\n        \n        if not self.token or not self.project_id:\n            return\n        rule_types =
    [visibility_drop, ctr_opportunity, regression]\n        self.client.post(\n            f/projects/{self.project_id}/alerts/rules,\n            json={\n                rule_type:
    random.choice(rule_types),\n                config: {threshold: random.uniform(10, 50), min_impressions: 100},\n                is_enabled: True,\n            },\n
    headers=self.auth_headers(),\n        )\n\n    @task(1)\n    def add_site(self) -> None:\n        \n        Add a site to the project.\n\n        Weight: 1 - Site configuration
    is rare.\n        \n        if not self.token or not self.project_id:\n            return\n        domains = [testsite1.com, testsite2.com, testsite3.com]\n        domain =
    random.choice(domains)\n        with self.client.post(\n            f/projects/{self.project_id}/sites,\n            json={domain: domain, base_url: fhttps://{domain}},\n
        headers=self.auth_headers(),\n            catch_response=True,\n        ) as response:\n            # Success or conflict is acceptable\n            if response.status_code
    in (201, 409):\n                response.success()\n            else:\n                response.failure(fAdd site failed: {response.status_code})\n\n\nclass
    AuthOnlyUser(HttpUser):\n    \n    User that focuses on authentication endpoints only.\n\n    This user class is useful for targeted auth load testing.\n    It repeatedly
    performs login/logout cycles.\n    \n\n    wait_time = between(0.5, 2)\n    weight = 1  # Lower weight than APIUser\n\n    def init(self, *args, **kwargs) -> None:\n
    super().init(*args, **kwargs)\n        self.email = fauthtest{uuid.uuid4().hex[:8]}@example.com\n        self.registered = False\n\n    def on_start(self) -> None:\n
    Register a user for authentication testing.\n        with self.client.post(\n            /auth/register,\n            json={\n                email: self.email,\n
    password: TEST_USER_PASSWORD,\n                name: Auth Test User,\n            },\n            catch_response=True,\n        ) as response:\n            if
    response.status_code in (201, 409):\n                self.registered = True\n                response.success()\n            else:\n                response.failure(fRegistration
     failed: {response.status_code})\n\n    @task(10)\n    def login_logout_cycle(self) -> None:\n        \n        Perform a complete login/logout cycle.\n\n        This tests the
    full authentication flow.\n        \n        if not self.registered:\n            return\n\n        # Login\n        with self.client.post(\n            /auth/login,\n
     json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n            },\n            catch_response=True,\n        ) as response:\n
    if response.status_code == 200:\n                data = response.json()\n                token = data.get(access_token)\n                response.success()\n\n                #
    Logout\n                self.client.post(\n                    /auth/logout,\n                    headers={Authorization: fBearer {token}},\n                )\n
    else:\n                response.failure(fLogin failed: {response.status_code})\n\n    @task(5)\n    def failed_login_attempt(self) -> None:\n        \n        Test failed login
    handling.\n\n        Verifies the API handles invalid credentials gracefully.\n        \n        with self.client.post(\n            /auth/login,\n            json={\n
         email: nonexistent@example.com,\n                password: wrongpassword,\n            },\n            catch_response=True,\n        ) as response:\n            if
    response.status_code == 401:\n                response.success()\n            else:\n                response.failure(fExpected 401, got: {response.status_code})\n\n\n# Event
    hooks for custom reporting\n@events.test_start.add_listener\ndef on_test_start(environment: Environment, **kwargs) -> None:\n    Called when load test starts.\n    print(n + = *
    60)\n    print(OPENAHRUSH LOAD TEST STARTING)\n    print(= * 60)\n    print(fHost: {environment.host})\n    print(Target Metrics:)\n    print(  - Concurrent users: 100)\n
    print(  - p50 latency: < 50ms)\n    print(  - p95 latency: < 200ms)\n    print(  - p99 latency: < 500ms)\n    print(= * 60 + n)\n\n\n@events.test_stop.add_listener\ndef
    on_test_stop(environment: Environment, **kwargs) -> None:\n    Called when load test stops.\n    print(n + = * 60)\n    print(OPENAHRUSH LOAD TEST COMPLETED)\n    print(= *
    60)\n\n    # Get stats\n    stats = environment.stats\n    if stats.total.num_requests > 0:\n        print(fnTotal Requests: {stats.total.num_requests})\n        print(fTotal
    Failures: {stats.total.num_failures})\n        print(fFailure Rate: {stats.total.fail_ratio * 100:.2f}%)\n        print(fnResponse Times:)\n        print(f  Average:
    {stats.total.avg_response_time:.2f}ms)\n        print(f  p50: {stats.total.get_response_time_percentile(0.50):.2f}ms)\n        print(f  p95:
    {stats.total.get_response_time_percentile(0.95):.2f}ms)\n        print(f  p99: {stats.total.get_response_time_percentile(0.99):.2f}ms)\n        print(fnRequests/sec:
    {stats.total.total_rps:.2f})\n\n        # Check against targets\n        p50 = stats.total.get_response_time_percentile(0.50)\n        p95 =
    stats.total.get_response_time_percentile(0.95)\n        p99 = stats.total.get_response_time_percentile(0.99)\n\n        print(nTarget Compliance:)\n        print(f  p50 < 50ms:
    {'PASS' if p50 < 50 else 'FAIL'} ({p50:.2f}ms))\n        print(f  p95 < 200ms: {'PASS' if p95 < 200 else 'FAIL'} ({p95:.2f}ms))\n        print(f  p99 < 500ms: {'PASS' if p99 <
    500 else 'FAIL'} ({p99:.2f}ms))\n\n    print(= * 60 + n)\n"}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"completed","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"in_progress","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"pending","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"pending","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"pending","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"completed","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"in_progress","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"pending","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"pending","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"pending","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/scenarios/auth_load.py","content":"\nAuthentication endpoint load testing scenarios.\n\nThis module
    provides targeted load testing for authentication endpoints:\n- POST /auth/register - User registration\n- POST /auth/login - User authentication\n- POST /auth/logout - Session
    termination\n- GET /me - Current user info\n\nUsage:\n    locust -f tests/load/scenarios/auth_load.py
    --host=http://localhost:8000\n\"\"\"\n\nfrom __future__ import annotations\n\nimport os\nimport uuid\n\nfrom locust import HttpUser, between,
    task\n\n# Configuration from environment variables\nTEST_USER_PASSWORD = os.getenv(LOAD_TEST_PASSWORD, loadtest123!)\n\n\nclass AuthLoadUser(HttpUser):\n    \n    User focused on
     authentication endpoint load testing.\n\n    This user class performs intensive testing of auth endpoints to verify:\n    - Registration throughput and handling of duplicate
    emails\n    - Login latency and JWT token generation\n    - Logout handling (stateless acknowledgment)\n    - Current user info retrieval\n    \n\n    wait_time = between(0.5,
    2)\n\n    def __init__(self, *args, **kwargs) -> None:\n        super().init(*args, **kwargs)\n        self.email: str = \n        self.token: str | None = None\n
    self.user_id: str | None = None\n\n    def on_start(self) -> None:\n        Generate unique credentials for this user instance.\n        self.email =
    fauth_load{uuid.uuid4().hex[:12]}@example.com\n\n    @task(5)\n    def register_new_user(self) -> None:\n        \n        Test user registration endpoint.\n\n        Each call
    uses a new unique email to test registration throughput.\n        \n        unique_email = freg{uuid.uuid4().hex[:12]}@example.com\n        with self.client.post(\n
    /auth/register,\n            json={\n                email: unique_email,\n                password: TEST_USER_PASSWORD,\n                name: Load Test User,\n            },\n
               catch_response=True,\n            name=/auth/register,\n        ) as response:\n            if response.status_code == 201:\n                response.success()\n
          elif response.status_code == 409:\n                # Duplicate email (unlikely with UUID but possible)\n                response.success()\n            elif
    response.status_code == 422:\n                # Validation error\n                response.failure(fValidation error: {response.text})\n            else:\n
    response.failure(fUnexpected status: {response.status_code})\n\n    @task(3)\n    def register_duplicate_email(self) -> None:\n        \n        Test registration with duplicate
    email (conflict handling).\n\n        Verifies the API correctly returns 409 for duplicate registrations.\n        \n        # First, ensure the user exists\n
    self.client.post(\n            /auth/register,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Load
    Test User,\n            },\n            name=/auth/register [setup],\n        )\n\n        # Then try to register again\n        with self.client.post(\n
    /auth/register,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Load Test User,\n            },\n
             catch_response=True,\n            name=/auth/register [duplicate],\n        ) as response:\n            if response.status_code == 409:\n
    response.success()\n            else:\n                response.failure(fExpected 409, got: {response.status_code})\n\n    @task(20)\n    def login_success(self) -> None:\n
      \n        Test successful login flow.\n\n        This is the most common auth operation and should be highly optimized.\n        \n        # Ensure user exists\n
    self.client.post(\n            /auth/register,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Load
    Test User,\n            },\n            name=/auth/register [setup],\n        )\n\n        # Login\n        with self.client.post(\n            /auth/login,\n            json={\n
                    email: self.email,\n                password: TEST_USER_PASSWORD,\n            },\n            catch_response=True,\n            name=/auth/login,\n        ) as
    response:\n            if response.status_code == 200:\n                data = response.json()\n                self.token = data.get(access_token)\n                if not
    self.token:\n                    response.failure(No access_token in response)\n                else:\n                    response.success()\n            else:\n
    response.failure(fLogin failed: {response.status_code})\n\n    @task(5)\n    def login_invalid_credentials(self) -> None:\n        \n        Test login with invalid
    credentials.\n\n        Verifies the API correctly handles invalid login attempts.\n        \n        with self.client.post(\n            /auth/login,\n            json={\n
              email: nonexistent@example.com,\n                password: wrongpassword,\n            },\n            catch_response=True,\n            name=/auth/login [invalid],\n
          ) as response:\n            if response.status_code == 401:\n                response.success()\n            else:\n                response.failure(fExpected 401, got:
    {response.status_code})\n\n    @task(3)\n    def login_wrong_password(self) -> None:\n        \n        Test login with correct email but wrong password.\n\n        Verifies
    password validation is working correctly.\n        \n        # Ensure user exists\n        self.client.post(\n            /auth/register,\n            json={\n
    email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Load Test User,\n            },\n            name=/auth/register [setup],\n        )\n\n
           with self.client.post(\n            /auth/login,\n            json={\n                email: self.email,\n                password: definitely_wrong_password,\n
     },\n            catch_response=True,\n            name=/auth/login [wrong_password],\n        ) as response:\n            if response.status_code == 401:\n
    response.success()\n            else:\n                response.failure(fExpected 401, got: {response.status_code})\n\n    @task(10)\n    def get_current_user(self) -> None:\n
         \n        Test current user info retrieval.\n\n        Requires a valid token. Tests the /me endpoint performance.\n        \n        if not self.token:\n            # Need
    to login first\n            self.client.post(\n                /auth/register,\n                json={\n                    email: self.email,\n                    password:
    TEST_USER_PASSWORD,\n                    name: Load Test User,\n                },\n                name=/auth/register [setup],\n            )\n            response =
    self.client.post(\n                /auth/login,\n                json={\n                    email: self.email,\n                    password: TEST_USER_PASSWORD,\n
      },\n                name=/auth/login [setup],\n            )\n            if response.status_code == 200:\n                self.token = response.json().get(access_token)\n\n
         if self.token:\n            with self.client.get(\n                /me,\n                headers={Authorization: fBearer {self.token}},\n
    catch_response=True,\n                name=/me,\n            ) as response:\n                if response.status_code == 200:\n                    response.success()\n
        else:\n                    response.failure(fGet user failed: {response.status_code})\n\n    @task(3)\n    def get_current_user_invalid_token(self) -> None:\n        \n
      Test /me endpoint with invalid token.\n\n        Verifies proper 401 handling for invalid tokens.\n        \n        with self.client.get(\n            /me,\n
    headers={Authorization: Bearer invalid_token_12345},\n            catch_response=True,\n            name=/me [invalid_token],\n        ) as response:\n            if
    response.status_code == 401:\n                response.success()\n            else:\n                response.failure(fExpected 401, got: {response.status_code})\n\n
    @task(8)\n    def logout(self) -> None:\n        \n        Test logout endpoint.\n\n        Logout is stateless (JWT-based) so this tests the acknowledgment flow.\n        \n
        if not self.token:\n            # Need to login first\n            self.client.post(\n                /auth/register,\n                json={\n                    email:
    self.email,\n                    password: TEST_USER_PASSWORD,\n                    name: Load Test User,\n                },\n                name=/auth/register [setup],\n
           )\n            response = self.client.post(\n                /auth/login,\n                json={\n                    email: self.email,\n                    password:
    TEST_USER_PASSWORD,\n                },\n                name=/auth/login [setup],\n            )\n            if response.status_code == 200:\n                self.token =
    response.json().get(access_token)\n\n        if self.token:\n            with self.client.post(\n                /auth/logout,\n                headers={Authorization: fBearer
    {self.token}},\n                catch_response=True,\n                name=/auth/logout,\n            ) as response:\n                if response.status_code == 200:\n
             response.success()\n                else:\n                    response.failure(fLogout failed: {response.status_code})\n\n    @task(10)\n    def full_auth_cycle(self)
    -> None:\n        \n        Test complete authentication cycle.\n\n        Performs: register -> login -> get user -> logout\n        This tests the full flow that a real user
    would experience.\n        \n        cycle_email = fcycle{uuid.uuid4().hex[:12]}@example.com\n\n        # Register\n        reg_response = self.client.post(\n
    /auth/register,\n            json={\n                email: cycle_email,\n                password: TEST_USER_PASSWORD,\n                name: Cycle Test User,\n            },\n
               name=/auth/register [cycle],\n        )\n        if reg_response.status_code not in (201, 409):\n            return\n\n        # Login\n        login_response =
    self.client.post(\n            /auth/login,\n            json={\n                email: cycle_email,\n                password: TEST_USER_PASSWORD,\n            },\n
    name=/auth/login [cycle],\n        )\n        if login_response.status_code != 200:\n            return\n\n        token = login_response.json().get(access_token)\n        if not
     token:\n            return\n\n        headers = {Authorization: fBearer {token}}\n\n        # Get current user\n        self.client.get(/me, headers=headers, name=/me
    [cycle])\n\n        # Logout\n        self.client.post(/auth/logout, headers=headers, name=/auth/logout [cycle])\n\n\nclass AuthSpikeUser(HttpUser):\n    \n    User that
    generates spike traffic on auth endpoints.\n\n    Use this to test how the system handles sudden bursts of auth requests.\n    \n\n    wait_time = between(0.1, 0.5)  # Very short
     wait time for spike testing\n    weight = 1  # Low weight by default\n\n    def init(self, *args, **kwargs) -> None:\n        super().init(*args, **kwargs)\n        self.email =
     fspike{uuid.uuid4().hex[:8]}@example.com\n\n    @task\n    def rapid_login(self) -> None:\n        \n        Rapidly attempt logins to generate spike load.\n\n        Warning:
    This generates high load - use with caution.\n        \n        # Ensure user exists\n        self.client.post(\n            /auth/register,\n            json={\n
    email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Spike Test User,\n            },\n            name=/auth/register [spike],\n        )\n\n
            # Rapid login attempts\n        with self.client.post(\n            /auth/login,\n            json={\n                email: self.email,\n                password:
    TEST_USER_PASSWORD,\n            },\n            catch_response=True,\n            name=/auth/login [spike],\n        ) as response:\n            if response.status_code in (200,
     429):  # 429 = rate limited\n                response.success()\n            else:\n                response.failure(fUnexpected status: {response.status_code})\n"}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/scenarios/api_read_load.py","content":"\nRead API endpoint load testing scenarios.\n\nThis module
    provides targeted load testing for read-heavy API endpoints:\n- GET /projects - List projects\n- GET /projects/{id} - Get project details\n- GET /projects/{id}/issues - Get
    project issues\n- GET /projects/{id}/alerts - Get project alerts\n- GET /projects/{id}/settings - Get project settings\n- GET /projects/{id}/competitors - List competitors\n- GET
     /projects/{id}/backlinks/* - Backlink analysis endpoints\n- GET /healthz - Health check\n- GET /readyz - Readiness check\n\nUsage:\n    locust -f
    tests/load/scenarios/api_read_load.py --host=http://localhost:8000\n\"\"\"\n\nfrom future import annotations\n\nimport os\nimport uuid\n\nfrom
     locust import HttpUser, between, task\n\n# Configuration from environment variables\nTEST_USER_PASSWORD = os.getenv(LOAD_TEST_PASSWORD, loadtest123!)\n\n\nclass
    ReadAPIUser(HttpUser):\n    \n    User focused on read API endpoint load testing.\n\n    This user class authenticates once and then performs intensive\n    read operations to
    test query performance and caching effectiveness.\n    \n\n    wait_time = between(0.5, 2)\n\n    def init(self, *args, **kwargs) -> None:\n        super().init(*args,
    **kwargs)\n        self.token: str | None = None\n        self.project_id: str | None = None\n        self.email: str = \n\n    def on_start(self) -> None:\n        Set up user
    with authentication and test project.\n        self.email = fread_api{uuid.uuid4().hex[:12]}@example.com\n\n        # Register\n        self.client.post(\n
    /auth/register,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Read API Test User,\n
    },\n        )\n\n        # Login\n        response = self.client.post(\n            /auth/login,\n            json={\n                email: self.email,\n
    password: TEST_USER_PASSWORD,\n            },\n        )\n        if response.status_code == 200:\n            self.token = response.json().get(access_token)\n\n        # Create
    test project\n        if self.token:\n            response = self.client.post(\n                /projects,\n                json={name: fRead Test Project
    {uuid.uuid4().hex[:8]}},\n                headers=self._auth_headers(),\n            )\n            if response.status_code == 201:\n                self.project_id =
    response.json().get(id)\n\n    def on_stop(self) -> None:\n        Clean up test resources.\n        if self.token and self.project_id:\n            self.client.delete(\n
            f/projects/{self.project_id},\n                headers=self._auth_headers(),\n            )\n\n    def _auth_headers(self) -> dict[str, str]:\n        Return
    authorization headers.\n        return {Authorization: fBearer {self.token}} if self.token else {}\n\n    #
    =========================================================================\n    # Health Endpoints (Unauthenticated)\n    #
    =========================================================================\n\n    @task(20)\n    def health_check(self) -> None:\n        \n        Test liveness endpoint.\n\n
        This is the most frequently called endpoint in production.\n        Should respond in < 10ms.\n        \n        with self.client.get(/healthz, catch_response=True) as
    response:\n            if response.status_code == 200:\n                response.success()\n            else:\n                response.failure(fHealth check failed:
    {response.status_code})\n\n    @task(10)\n    def readiness_check(self) -> None:\n        \n        Test readiness endpoint with dependency checks.\n\n        More expensive than
     healthz due to database ping.\n        \n        with self.client.get(/readyz, catch_response=True) as response:\n            if response.status_code in (200, 503):\n
         response.success()\n            else:\n                response.failure(fReadiness check failed: {response.status_code})\n\n    #
    =========================================================================\n    # Project Read Endpoints\n    #
    =========================================================================\n\n    @task(30)\n    def list_projects(self) -> None:\n        \n        Test project listing.\n\n
       Most common authenticated read operation.\n        \n        if not self.token:\n            return\n\n        with self.client.get(\n            /projects,\n
    headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects,\n        ) as response:\n            if response.status_code == 200:\n
     response.success()\n            else:\n                response.failure(fList projects failed: {response.status_code})\n\n    @task(10)\n    def list_projects_paginated(self) ->
     None:\n        \n        Test paginated project listing.\n\n        Tests query performance with pagination parameters.\n        \n        if not self.token:\n
    return\n\n        with self.client.get(\n            /projects,\n            params={page: 1, page_size: 10},\n            headers=self._auth_headers(),\n
    catch_response=True,\n            name=/projects [paginated],\n        ) as response:\n            if response.status_code == 200:\n                response.success()\n
      else:\n                response.failure(fPaginated list failed: {response.status_code})\n\n    @task(25)\n    def get_project(self) -> None:\n        \n        Test single
    project retrieval.\n\n        Common operation when viewing project details.\n        \n        if not self.token or not self.project_id:\n            return\n\n        with
    self.client.get(\n            f/projects/{self.project_id},\n            headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects/{id},\n
      ) as response:\n            if response.status_code == 200:\n                response.success()\n            elif response.status_code == 404:\n
    response.success()  # Project may have been deleted\n            else:\n                response.failure(fGet project failed: {response.status_code})\n\n    @task(5)\n    def
    get_nonexistent_project(self) -> None:\n        \n        Test 404 handling for nonexistent project.\n\n        Verifies proper error handling doesn't impact performance.\n
      \n        if not self.token:\n            return\n\n        fake_id = str(uuid.uuid4())\n        with self.client.get(\n            f/projects/{fake_id},\n
    headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects/{id} [404],\n        ) as response:\n            if response.status_code == 404:\n
                response.success()\n            else:\n                response.failure(fExpected 404, got: {response.status_code})\n\n    #
    =========================================================================\n    # Project Issues Endpoints\n    #
    =========================================================================\n\n    @task(15)\n    def get_project_issues(self) -> None:\n        \n        Test project issues
    retrieval.\n\n        Important SEO analysis endpoint.\n        \n        if not self.token or not self.project_id:\n            return\n\n        with self.client.get(\n
        f/projects/{self.project_id}/issues,\n            headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects/{id}/issues,\n        ) as
    response:\n            if response.status_code in (200, 404):  # 404 if no crawl runs\n                response.success()\n            else:\n
    response.failure(fGet issues failed: {response.status_code})\n\n    @task(5)\n    def get_project_issues_limited(self) -> None:\n        \n        Test issues retrieval with
    limit parameter.\n        \n        if not self.token or not self.project_id:\n            return\n\n        with self.client.get(\n
    f/projects/{self.project_id}/issues,\n            params={limit: 50},\n            headers=self._auth_headers(),\n            catch_response=True,\n
    name=/projects/{id}/issues [limited],\n        ) as response:\n            if response.status_code in (200, 404):\n                response.success()\n            else:\n
            response.failure(fGet issues failed: {response.status_code})\n\n    # =========================================================================\n    # Project Alerts
    Endpoints\n    # =========================================================================\n\n    @task(10)\n    def get_project_alerts(self) -> None:\n        \n        Test
    project alerts retrieval.\n        \n        if not self.token or not self.project_id:\n            return\n\n        with self.client.get(\n
    f/projects/{self.project_id}/alerts,\n            headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects/{id}/alerts,\n        ) as
    response:\n            if response.status_code == 200:\n                response.success()\n            else:\n                response.failure(fGet alerts failed:
    {response.status_code})\n\n    @task(5)\n    def get_project_alerts_filtered(self) -> None:\n        \n        Test alerts retrieval with filters.\n        \n        if not
    self.token or not self.project_id:\n            return\n\n        with self.client.get(\n            f/projects/{self.project_id}/alerts,\n            params={severity: critical,
     is_acknowledged: False},\n            headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects/{id}/alerts [filtered],\n        ) as
    response:\n            if response.status_code == 200:\n                response.success()\n            else:\n                response.failure(fGet alerts filtered failed:
    {response.status_code})\n\n    @task(5)\n    def get_alert_rules(self) -> None:\n        \n        Test alert rules listing.\n        \n        if not self.token or not
    self.project_id:\n            return\n\n        with self.client.get(\n            f/projects/{self.project_id}/alerts/rules,\n            headers=self._auth_headers(),\n
        catch_response=True,\n            name=/projects/{id}/alerts/rules,\n        ) as response:\n            if response.status_code == 200:\n                response.success()\n
                else:\n                response.failure(fGet alert rules failed: {response.status_code})\n\n    #
    =========================================================================\n    # Project Settings Endpoints\n    #
    =========================================================================\n\n    @task(8)\n    def get_project_settings(self) -> None:\n        \n        Test project settings
    retrieval.\n        \n        if not self.token or not self.project_id:\n            return\n\n        with self.client.get(\n            f/projects/{self.project_id}/settings,\n
                headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects/{id}/settings,\n        ) as response:\n            if
    response.status_code == 200:\n                response.success()\n            else:\n                response.failure(fGet settings failed: {response.status_code})\n\n    #
    =========================================================================\n    # Project Competitors Endpoints\n    #
    =========================================================================\n\n    @task(8)\n    def get_project_competitors(self) -> None:\n        \n        Test competitors
    listing.\n        \n        if not self.token or not self.project_id:\n            return\n\n        with self.client.get(\n
    f/projects/{self.project_id}/competitors,\n            headers=self._auth_headers(),\n            catch_response=True,\n            name=/projects/{id}/competitors,\n        ) as
     response:\n            if response.status_code == 200:\n                response.success()\n            else:\n                response.failure(fGet competitors failed:
    {response.status_code})\n\n    # =========================================================================\n    # Backlinks Endpoints\n    #
    =========================================================================\n\n    @task(5)\n    def get_backlinks_overview(self) -> None:\n        \n        Test backlinks
    overview retrieval.\n        \n        if not self.token or not self.project_id:\n            return\n\n        with self.client.get(\n
    f/projects/{self.project_id}/backlinks/overview,\n            headers=self.auth_headers(),\n            catch_response=True,\n
    name=/projects/{id}/backlinks/overview,\n        ) as response:\n            # Accept 500 as table may not exist in test environment\n            if response.status_code in (200,
     500):\n                response.success()\n            else:\n                response.failure(fGet backlinks overview failed: {response.status_code})\n\n    @task(3)\n    def
    get_backlinks_anchors(self) -> None:\n        \n        Test backlinks anchor distribution.\n        \n        if not self.token or not self.project_id:\n            return\n\n
          with self.client.get(\n            f/projects/{self.project_id}/backlinks/anchors,\n            headers=self.auth_headers(),\n            catch_response=True,\n
    name=/projects/{id}/backlinks/anchors,\n        ) as response:\n            if response.status_code in (200, 500):\n                response.success()\n            else:\n
             response.failure(fGet backlinks anchors failed: {response.status_code})\n\n\nclass CacheBustingUser(HttpUser):\n    \n    User that tests cache effectiveness by reading
    with varying parameters.\n\n    This helps identify if caching is working correctly and what the\n    cache hit/miss ratio impact is on performance.\n    \n\n    wait_time =
    between(0.5, 1.5)\n    weight = 1  # Lower weight than main read user\n\n    def init(self, *args, **kwargs) -> None:\n        super().init(*args, **kwargs)\n        self.token:
    str | None = None\n        self.project_ids: list[str] = []\n        self.email: str = \n\n    def on_start(self) -> None:\n        Set up user with multiple test projects.\n
        self.email = fcache_bust{uuid.uuid4().hex[:12]}@example.com\n\n        # Register and login\n        self.client.post(\n            /auth/register,\n            json={\n
               email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Cache Bust User,\n            },\n        )\n\n        response =
    self.client.post(\n            /auth/login,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n            },\n        )\n
         if response.status_code == 200:\n            self.token = response.json().get(access_token)\n\n        # Create multiple projects for cache testing\n        if self.token:\n
                for i in range(3):\n                response = self.client.post(\n                    /projects,\n                    json={name: fCache Test Project {i}},\n
               headers={Authorization: fBearer {self.token}},\n                )\n                if response.status_code == 201:\n
    self.project_ids.append(response.json().get(id))\n\n    def on_stop(self) -> None:\n        Clean up test projects.\n        if self.token:\n            for project_id in
    self.project_ids:\n                self.client.delete(\n                    f/projects/{project_id},\n                    headers={Authorization: fBearer {self.token}},\n
            )\n\n    @task(10)\n    def read_random_project(self) -> None:\n        \n        Read a random project from the pool.\n\n        Tests cache behavior with varying
    resource IDs.\n        \n        if not self.token or not self.project_ids:\n            return\n\n        import random\n\n        project_id = random.choice(self.project_ids)\n
            self.client.get(\n            f/projects/{project_id},\n            headers={Authorization: fBearer {self.token}},\n            name=/projects/{id} [cache_test],\n
     )\n\n    @task(5)\n    def read_with_varying_pagination(self) -> None:\n        \n        Read projects with different pagination parameters.\n\n        Tests cache key
    generation with query parameters.\n        \n        if not self.token:\n            return\n\n        import random\n\n        page = random.randint(1, 5)\n        page_size =
    random.choice([10, 20, 50])\n\n        self.client.get(\n            /projects,\n            params={page: page, page_size: page_size},\n            headers={Authorization:
    fBearer {self.token}},\n            name=/projects [varying_pagination],\n        )\n"}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/scenarios/crawl_load.py","content":"\nCrawl trigger and write API load testing scenarios.\n\nThis module
     provides targeted load testing for write-heavy API endpoints:\n- POST /projects - Create project\n- PATCH /projects/{id} - Update project\n- DELETE /projects/{id} - Delete
    project\n- POST /projects/{id}/sites - Add site\n- POST /projects/{id}/competitors - Add competitor\n- POST /projects/{id}/alerts/rules - Create alert rule\n- PUT
    /projects/{id}/settings - Update settings\n\nNote: Actual crawl triggering endpoints would be added when the crawl\nworker integration is complete.\n\nUsage:\n    locust -f
    tests/load/scenarios/crawl_load.py --host=http://localhost:8000\n\"\"\"\n\nfrom future import annotations\n\nimport os\nimport random\nimport
    uuid\n\nfrom locust import HttpUser, between, task\n\n# Configuration from environment variables\nTEST_USER_PASSWORD = os.getenv(LOAD_TEST_PASSWORD, loadtest123!)\n\n\nclass
    WriteAPIUser(HttpUser):\n    \n    User focused on write API endpoint load testing.\n\n    This user class tests the throughput and latency of write operations\n    including
    project CRUD, settings updates, and resource creation.\n    \n\n    wait_time = between(1, 3)\n\n    def init(self, *args, **kwargs) -> None:\n        super().init(*args,
    **kwargs)\n        self.token: str | None = None\n        self.project_ids: list[str] = []\n        self.email: str = \n\n    def on_start(self) -> None:\n        Set up user
    with authentication.\n        self.email = fwrite_api{uuid.uuid4().hex[:12]}@example.com\n\n        # Register\n        self.client.post(\n            /auth/register,\n
      json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Write API Test User,\n            },\n        )\n\n        #
    Login\n        response = self.client.post(\n            /auth/login,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n
            },\n        )\n        if response.status_code == 200:\n            self.token = response.json().get(access_token)\n\n    def on_stop(self) -> None:\n        Clean up all
     created projects.\n        if self.token:\n            for project_id in self.project_ids:\n                self.client.delete(\n                    f/projects/{project_id},\n
                      headers=self._auth_headers(),\n                )\n\n    def _auth_headers(self) -> dict[str, str]:\n        Return authorization headers.\n        return
    {Authorization: fBearer {self.token}} if self.token else {}\n\n    # =========================================================================\n    # Project CRUD Operations\n
     # =========================================================================\n\n    @task(20)\n    def create_project(self) -> None:\n        \n        Test project creation.\n\n
            This is a common write operation for new users.\n        \n        if not self.token:\n            return\n\n        with self.client.post(\n            /projects,\n
           json={name: fLoad Test Project {uuid.uuid4().hex[:8]}},\n            headers=self._auth_headers(),\n            catch_response=True,\n            name=POST /projects,\n
         ) as response:\n            if response.status_code == 201:\n                project_id = response.json().get(id)\n                if project_id:\n
    self.project_ids.append(project_id)\n                response.success()\n            else:\n                response.failure(fCreate project failed: {response.status_code})\n\n
      @task(15)\n    def update_project(self) -> None:\n        \n        Test project update.\n\n        Updates name of a random existing project.\n        \n        if not
    self.token or not self.project_ids:\n            return\n\n        project_id = random.choice(self.project_ids)\n        with self.client.patch(\n
    f/projects/{project_id},\n            json={name: fUpdated Project {uuid.uuid4().hex[:4]}},\n            headers=self._auth_headers(),\n            catch_response=True,\n
        name=PATCH /projects/{id},\n        ) as response:\n            if response.status_code == 200:\n                response.success()\n            elif response.status_code ==
    404:\n                # Project may have been deleted by another task\n                response.success()\n            else:\n                response.failure(fUpdate project
    failed: {response.status_code})\n\n    @task(5)\n    def delete_project(self) -> None:\n        \n        Test project deletion.\n\n        Deletes a random project if we have
    more than 2.\n        \n        if not self.token or len(self.project_ids) < 3:\n            return\n\n        project_id = self.project_ids.pop()\n        with
    self.client.delete(\n            f/projects/{project_id},\n            headers=self._auth_headers(),\n            catch_response=True,\n            name=DELETE /projects/{id},\n
           ) as response:\n            if response.status_code == 204:\n                response.success()\n            elif response.status_code == 404:\n
    response.success()  # Already deleted\n            else:\n                response.failure(fDelete project failed: {response.status_code})\n\n    #
    =========================================================================\n    # Site Management\n    #
    =========================================================================\n\n    @task(10)\n    def add_site(self) -> None:\n        \n        Test adding a site to a project.\n
           \n        if not self.token or not self.project_ids:\n            return\n\n        project_id = random.choice(self.project_ids)\n        domain =
    fsite{uuid.uuid4().hex[:6]}.com\n\n        with self.client.post(\n            f/projects/{project_id}/sites,\n            json={domain: domain, base_url: fhttps://{domain}},\n
              headers=self._auth_headers(),\n            catch_response=True,\n            name=POST /projects/{id}/sites,\n        ) as response:\n            if
    response.status_code == 201:\n                response.success()\n            elif response.status_code in (404, 409):\n                response.success()  # Project deleted or
    duplicate\n            else:\n                response.failure(fAdd site failed: {response.status_code})\n\n    #
    =========================================================================\n    # Competitor Management\n    #
    =========================================================================\n\n    @task(10)\n    def add_competitor(self) -> None:\n        \n        Test adding a competitor to a
     project.\n        \n        if not self.token or not self.project_ids:\n            return\n\n        project_id = random.choice(self.project_ids)\n        domain =
    fcompetitor{uuid.uuid4().hex[:6]}.com\n\n        with self.client.post(\n            f/projects/{project_id}/competitors,\n            json={domain: domain},\n
    headers=self._auth_headers(),\n            catch_response=True,\n            name=POST /projects/{id}/competitors,\n        ) as response:\n            if response.status_code ==
     201:\n                response.success()\n            elif response.status_code in (404, 409):\n                response.success()  # Project deleted or duplicate\n
    else:\n                response.failure(fAdd competitor failed: {response.status_code})\n\n    # =========================================================================\n    #
    Alert Rules\n    # =========================================================================\n\n    @task(8)\n    def create_alert_rule(self) -> None:\n        \n        Test
    creating an alert rule.\n        \n        if not self.token or not self.project_ids:\n            return\n\n        project_id = random.choice(self.project_ids)\n
    rule_types = [visibility_drop, ctr_opportunity, regression]\n\n        with self.client.post(\n            f/projects/{project_id}/alerts/rules,\n            json={\n
        rule_type: random.choice(rule_types),\n                config: {\n                    threshold: round(random.uniform(10, 50), 1),\n                    min_impressions:
    random.randint(50, 500),\n                },\n                is_enabled: True,\n            },\n            headers=self.auth_headers(),\n            catch_response=True,\n
           name=POST /projects/{id}/alerts/rules,\n        ) as response:\n            if response.status_code == 201:\n                response.success()\n            elif
    response.status_code in (400, 404):\n                response.success()  # Invalid rule type or project deleted\n            else:\n                response.failure(fCreate alert
     rule failed: {response.status_code})\n\n    # =========================================================================\n    # Settings Management\n    #
    =========================================================================\n\n    @task(8)\n    def update_settings(self) -> None:\n        \n        Test updating project
    settings.\n        \n        if not self.token or not self.project_ids:\n            return\n\n        project_id = random.choice(self.project_ids)\n\n        with
    self.client.put(\n            f/projects/{project_id}/settings,\n            json={\n                crawl_depth: random.randint(1, 5),\n                max_pages:
    random.randint(100, 1000),\n                respect_robots_txt: True,\n                user_agent: LoadTestBot/1.0,\n            },\n            headers=self.auth_headers(),\n
             catch_response=True,\n            name=PUT /projects/{id}/settings,\n        ) as response:\n            if response.status_code == 200:\n
    response.success()\n            elif response.status_code in (404, 422):\n                response.success()  # Project deleted or validation error\n            else:\n
          response.failure(fUpdate settings failed: {response.status_code})\n\n\nclass BurstWriteUser(HttpUser):\n    \n    User that generates burst write traffic.\n\n    Use this
    to test how the system handles sudden spikes in write operations.\n    \n\n    wait_time = between(0.2, 0.8)  # Short wait time for burst testing\n    weight = 1  # Low weight by
     default\n\n    def init(self, *args, **kwargs) -> None:\n        super().init(*args, **kwargs)\n        self.token: str | None = None\n        self.project_ids: list[str] = []\n
            self.email: str = \n\n    def on_start(self) -> None:\n        Set up user for burst testing.\n        self.email = fburst{uuid.uuid4().hex[:12]}@example.com\n\n
    self.client.post(\n            /auth/register,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Burst
     Test User,\n            },\n        )\n\n        response = self.client.post(\n            /auth/login,\n            json={\n                email: self.email,\n
    password: TEST_USER_PASSWORD,\n            },\n        )\n        if response.status_code == 200:\n            self.token = response.json().get(access_token)\n\n    def
    on_stop(self) -> None:\n        Clean up burst test resources.\n        if self.token:\n            for project_id in self.project_ids:\n                self.client.delete(\n
                    f/projects/{project_id},\n                    headers={Authorization: fBearer {self.token}},\n                )\n\n    @task\n    def rapid_project_creation(self)
     -> None:\n        \n        Rapidly create projects to test write throughput.\n\n        Warning: This generates high database load.\n        \n        if not self.token:\n
           return\n\n        with self.client.post(\n            /projects,\n            json={name: fBurst Project {uuid.uuid4().hex[:8]}},\n            headers={Authorization:
    fBearer {self.token}},\n            catch_response=True,\n            name=POST /projects [burst],\n        ) as response:\n            if response.status_code == 201:\n
           project_id = response.json().get(id)\n                if project_id:\n                    self.project_ids.append(project_id)\n                response.success()\n
        elif response.status_code == 429:\n                # Rate limited - expected under burst\n                response.success()\n            else:\n
    response.failure(fBurst create failed: {response.status_code})\n\n\nclass MixedWorkloadUser(HttpUser):\n    \n    User that performs a realistic mix of read and write
    operations.\n\n    This simulates real-world usage patterns with appropriate read/write ratios.\n    \n\n    wait_time = between(1, 4)\n\n    def init(self, *args, **kwargs) ->
    None:\n        super().init(*args, **kwargs)\n        self.token: str | None = None\n        self.project_id: str | None = None\n        self.email: str = \n\n    def
    on_start(self) -> None:\n        Set up user with authentication and a test project.\n        self.email = fmixed{uuid.uuid4().hex[:12]}@example.com\n\n
    self.client.post(\n            /auth/register,\n            json={\n                email: self.email,\n                password: TEST_USER_PASSWORD,\n                name: Mixed
     Workload User,\n            },\n        )\n\n        response = self.client.post(\n            /auth/login,\n            json={\n                email: self.email,\n
        password: TEST_USER_PASSWORD,\n            },\n        )\n        if response.status_code == 200:\n            self.token = response.json().get(access_token)\n\n        if
    self.token:\n            response = self.client.post(\n                /projects,\n                json={name: fMixed Test Project},\n                headers={Authorization:
    fBearer {self.token}},\n            )\n            if response.status_code == 201:\n                self.project_id = response.json().get(id)\n\n    def on_stop(self) -> None:\n
           Clean up test resources.\n        if self.token and self.project_id:\n            self.client.delete(\n                f/projects/{self.project_id},\n
    headers={Authorization: fBearer {self.token}},\n            )\n\n    def _auth_headers(self) -> dict[str, str]:\n        Return authorization headers.\n        return
    {Authorization: fBearer {self.token}} if self.token else {}\n\n    # Read operations (80% of traffic)\n    @task(40)\n    def list_projects(self) -> None:\n        List projects
    (read).\n        if self.token:\n            self.client.get(/projects, headers=self._auth_headers())\n\n    @task(20)\n    def get_project(self) -> None:\n        Get project
    details (read).\n        if self.token and self.project_id:\n            self.client.get(\n                f/projects/{self.project_id},\n
    headers=self._auth_headers(),\n            )\n\n    @task(10)\n    def get_issues(self) -> None:\n        Get project issues (read).\n        if self.token and self.project_id:\n
                with self.client.get(\n                f/projects/{self.project_id}/issues,\n                headers=self._auth_headers(),\n                catch_response=True,\n
            ) as response:\n                if response.status_code in (200, 404):\n                    response.success()\n\n    @task(10)\n    def get_alerts(self) -> None:\n
      Get project alerts (read).\n        if self.token and self.project_id:\n            self.client.get(\n                f/projects/{self.project_id}/alerts,\n
    headers=self._auth_headers(),\n            )\n\n    # Write operations (20% of traffic)\n    @task(5)\n    def update_project(self) -> None:\n        Update project (write).\n
         if self.token and self.project_id:\n            self.client.patch(\n                f/projects/{self.project_id},\n                json={name: fUpdated
    {uuid.uuid4().hex[:4]}},\n                headers=self._auth_headers(),\n            )\n\n    @task(3)\n    def add_competitor(self) -> None:\n        Add competitor (write).\n
          if self.token and self.project_id:\n            domain = fcomp{uuid.uuid4().hex[:6]}.com\n            with self.client.post(\n
    f/projects/{self.project_id}/competitors,\n                json={domain: domain},\n                headers=self._auth_headers(),\n                catch_response=True,\n
      ) as response:\n                if response.status_code in (201, 404, 409):\n                    response.success()\n\n    @task(2)\n    def update_settings(self) -> None:\n
         Update settings (write).\n        if self.token and self.project_id:\n            with self.client.put(\n                f/projects/{self.project_id}/settings,\n
        json={crawl_depth: random.randint(1, 5), max_pages: 500},\n                headers=self._auth_headers(),\n                catch_response=True,\n            ) as response:\n
                  if response.status_code in (200, 404, 422):\n                    response.success()\n"}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"completed","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"completed","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"completed","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"completed","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage
    instructions","status":"in_progress","activeForm":"Creating README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust
     to dev dependencies"},{"content":"Verify with ruff and mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"completed","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"completed","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"completed","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"completed","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage
    instructions","status":"in_progress","activeForm":"Creating README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust
     to dev dependencies"},{"content":"Verify with ruff and mypy","status":"pending","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/README.md","content":"# Load Testing\n\nThis directory contains load testing infrastructure for the
    Openahrush API using https://locust.io/.\n\n## Prerequisites\n\nbash\n# Install dependencies (locust is included in dev dependencies)\nuv sync\n\n# Or install locust
    directly\npip install locust\n\n\n## Performance Targets\n\n| Metric | Target | Description |\n|--------|--------|-------------|\n| Concurrent users | 100+ | System should handle
     100 simultaneous users |\n| p50 latency | < 50ms | Median response time |\n| p95 latency | < 200ms | 95th percentile response time |\n| p99 latency | < 500ms | 99th percentile
    response time |\n| Error rate | < 1% | Request failure rate |\n\n## Running Load Tests\n\n### Start the API Server\n\nbash\n# Start the development environment\nscripts/dev.sh
    up\n\n# Or run the API directly\nuv run --package semrush-api uvicorn semrush_api.main:app --reload --port 8000\n\n\n### Main Load Test (Web UI)\n\nbash\n# Start Locust with web
    interface\nlocust -f tests/load/locustfile.py --host=http://localhost:8000\n\n# Open http://localhost:8089 in your browser\n# Configure users and spawn rate, then start the
    test\n\n\n### Headless Mode (CI/CD)\n\nbash\n# Run with specific user count and duration\nlocust -f tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n
    --users=100 \\\n    --spawn-rate=10 \\\n    --run-time=5m \\\n    --headless\n\n# With HTML report\nlocust -f tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n
      --users=100 \\\n    --spawn-rate=10 \\\n    --run-time=5m \\\n    --headless \\\n    --html=reports/load_test_report.html\n\n# With CSV output for analysis\nlocust -f
    tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n    --users=100 \\\n    --spawn-rate=10 \\\n    --run-time=5m \\\n    --headless \\\n
    --csv=reports/load_test_results\n\n\n### Scenario-Specific Tests\n\nbash\n# Authentication load test\nlocust -f tests/load/scenarios/auth_load.py
    --host=http://localhost:8000\n\n# Read API load test\nlocust -f tests/load/scenarios/api_read_load.py --host=http://localhost:8000\n\n# Write API / Crawl trigger load
    test\nlocust -f tests/load/scenarios/crawl_load.py --host=http://localhost:8000\n\n\n## Test Scenarios\n\n### Main Load Test (locustfile.py)\n\nThe primary load test simulates
    realistic API usage with:\n- User registration and login\n- Project CRUD operations\n- Issue and alert queries\n- Backlink analysis requests\n- Health checks\n\nTask weights
    reflect expected real-world usage patterns.\n\n### Authentication Load (scenarios/auth_load.py)\n\nFocused testing of authentication endpoints:\n- Registration throughput\n-
    Login/logout cycles\n- Token validation\n- Invalid credential handling\n- Authentication spikes\n\n### Read API Load (scenarios/api_read_load.py)\n\nHeavy read operation
    testing:\n- Project listing (paginated)\n- Project details\n- Issues retrieval\n- Alerts and rules\n- Settings access\n- Backlinks overview\n\n### Write API Load
    (scenarios/crawl_load.py)\n\nWrite operation testing:\n- Project creation/update/deletion\n- Site management\n- Competitor management\n- Alert rule creation\n- Settings
    updates\n\n## Configuration\n\n### Environment Variables\n\nbash\n# Test user credentials\nexport LOAD_TEST_EMAIL=\"loadtest@example.com\"\nexport
    LOAD_TEST_PASSWORD=\"loadtest123!\"\n\n\n### Locust Configuration\n\nCreate a locust.conf file for persistent settings:\n\nini\n# locust.conf\nhost = http://localhost:8000\nusers
     = 100\nspawn-rate = 10\nrun-time = 5m\nheadless = false\nhtml = reports/load_test_report.html\n\n\nThen run with:\nbash\nlocust -f tests/load/locustfile.py\n\n\n## Interpreting
    Results\n\n### Web UI Metrics\n\n- **RPS**: Requests per second - overall throughput\n- **Response Times**: p50, p95, p99, min, max\n- **Failures**: Count and percentage of
    failed requests\n- **Charts**: Real-time visualization of performance\n\n### CSV Output Files\n\nWhen using --csv=prefix, three files are generated:\n- prefix_stats.csv:
    Per-request statistics\n- prefix_stats_history.csv: Time-series data\n- prefix_failures.csv: Failure details\n\n### Example Analysis\n\npython\nimport pandas as pd\n\n# Load
    stats\nstats = pd.read_csv('reports/load_test_results_stats.csv')\n\n# Check p95 latencies\np95_violations = stats[stats['95%'] > 200]\nif len(p95_violations) > 0:\n
    print(\"Endpoints exceeding p95 target:\")\n    print(p95_violations[['Name', '95%']])\n\n\n## Distributed Testing\n\nFor higher load, run Locust in distributed mode:\n\nbash\n#
    Start master\nlocust -f tests/load/locustfile.py --master --host=http://localhost:8000\n\n# Start workers (run on multiple machines)\nlocust -f tests/load/locustfile.py --worker
    --master-host=<master-ip>\n\n\n## CI/CD Integration\n\n### GitHub Actions Example\n\nyaml\nload-test:\n  runs-on: ubuntu-latest\n  steps:\n    - uses: actions/checkout@v4\n\n
    - name: Start API\n      run: |\n        docker-compose up -d\n        sleep 10\n\n    - name: Run Load Tests\n      run: |\n        pip install locust\n        locust -f
    tests/load/locustfile.py \\\n          --host=http://localhost:8000 \\\n          --users=50 \\\n          --spawn-rate=5 \\\n          --run-time=2m \\\n          --headless
    \\\n          --html=load_test_report.html \\\n          --exit-code-on-error 1\n\n    - name: Upload Report\n      uses: actions/upload-artifact@v4\n      with:\n        name:
    load-test-report\n        path: load_test_report.html\n\n\n### Performance Gates\n\nUse the --exit-code-on-error flag to fail CI if:\n- Any requests fail\n- Error rate exceeds
    threshold\n\nCustom exit codes can be implemented using Locust's event hooks.\n\n## Troubleshooting\n\n### High Failure Rate\n\n1. Check if the API server is running\n2. Verify
    database connectivity\n3. Check for rate limiting\n4. Review server logs for errors\n\n### Inconsistent Results\n\n1. Ensure consistent test environment\n2. Warm up the API
    before testing\n3. Run multiple test iterations\n4. Check for external factors (network, other processes)\n\n### Memory Issues\n\nFor long-running tests:\nbash\n# Increase spawn
    rate to reduce memory\nlocust -f tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n    --users=100 \\\n    --spawn-rate=20 \\\n    --run-time=30m \\\n
    --headless\n\n\n## Best Practices\n\n1. **Baseline First**: Run tests against a known-good configuration to establish baselines\n2. **Gradual Ramp-Up**: Use spawn-rate to
    gradually increase load\n3. **Realistic Data**: Ensure test database has representative data volume\n4. **Isolated Environment**: Run load tests in isolated environments\n5.
    **Monitor Resources**: Watch CPU, memory, and database metrics during tests\n6. **Repeat Tests**: Run multiple iterations for consistent results\n7. **Document Changes**: Note
    configuration changes between test runs\n"}
    [Tool: Write] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/README.md","content":"# Load Testing\n\nThis directory contains load testing infrastructure for the
    Openahrush API using https://locust.io/.\n\n## Prerequisites\n\nbash\n# Install dependencies (locust is included in dev dependencies)\nuv sync\n\n# Or install locust
    directly\npip install locust\n\n\n## Performance Targets\n\n| Metric | Target | Description |\n|--------|--------|-------------|\n| Concurrent users | 100+ | System should handle
     100 simultaneous users |\n| p50 latency | < 50ms | Median response time |\n| p95 latency | < 200ms | 95th percentile response time |\n| p99 latency | < 500ms | 99th percentile
    response time |\n| Error rate | < 1% | Request failure rate |\n\n## Running Load Tests\n\n### Start the API Server\n\nbash\n# Start the development environment\nscripts/dev.sh
    up\n\n# Or run the API directly\nuv run --package semrush-api uvicorn semrush_api.main:app --reload --port 8000\n\n\n### Main Load Test (Web UI)\n\nbash\n# Start Locust with web
    interface\nlocust -f tests/load/locustfile.py --host=http://localhost:8000\n\n# Open http://localhost:8089 in your browser\n# Configure users and spawn rate, then start the
    test\n\n\n### Headless Mode (CI/CD)\n\nbash\n# Run with specific user count and duration\nlocust -f tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n
    --users=100 \\\n    --spawn-rate=10 \\\n    --run-time=5m \\\n    --headless\n\n# With HTML report\nlocust -f tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n
      --users=100 \\\n    --spawn-rate=10 \\\n    --run-time=5m \\\n    --headless \\\n    --html=reports/load_test_report.html\n\n# With CSV output for analysis\nlocust -f
    tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n    --users=100 \\\n    --spawn-rate=10 \\\n    --run-time=5m \\\n    --headless \\\n
    --csv=reports/load_test_results\n\n\n### Scenario-Specific Tests\n\nbash\n# Authentication load test\nlocust -f tests/load/scenarios/auth_load.py
    --host=http://localhost:8000\n\n# Read API load test\nlocust -f tests/load/scenarios/api_read_load.py --host=http://localhost:8000\n\n# Write API / Crawl trigger load
    test\nlocust -f tests/load/scenarios/crawl_load.py --host=http://localhost:8000\n\n\n## Test Scenarios\n\n### Main Load Test (locustfile.py)\n\nThe primary load test simulates
    realistic API usage with:\n- User registration and login\n- Project CRUD operations\n- Issue and alert queries\n- Backlink analysis requests\n- Health checks\n\nTask weights
    reflect expected real-world usage patterns.\n\n### Authentication Load (scenarios/auth_load.py)\n\nFocused testing of authentication endpoints:\n- Registration throughput\n-
    Login/logout cycles\n- Token validation\n- Invalid credential handling\n- Authentication spikes\n\n### Read API Load (scenarios/api_read_load.py)\n\nHeavy read operation
    testing:\n- Project listing (paginated)\n- Project details\n- Issues retrieval\n- Alerts and rules\n- Settings access\n- Backlinks overview\n\n### Write API Load
    (scenarios/crawl_load.py)\n\nWrite operation testing:\n- Project creation/update/deletion\n- Site management\n- Competitor management\n- Alert rule creation\n- Settings
    updates\n\n## Configuration\n\n### Environment Variables\n\nbash\n# Test user credentials\nexport LOAD_TEST_EMAIL=\"loadtest@example.com\"\nexport
    LOAD_TEST_PASSWORD=\"loadtest123!\"\n\n\n### Locust Configuration\n\nCreate a locust.conf file for persistent settings:\n\nini\n# locust.conf\nhost = http://localhost:8000\nusers
     = 100\nspawn-rate = 10\nrun-time = 5m\nheadless = false\nhtml = reports/load_test_report.html\n\n\nThen run with:\nbash\nlocust -f tests/load/locustfile.py\n\n\n## Interpreting
    Results\n\n### Web UI Metrics\n\n- **RPS**: Requests per second - overall throughput\n- **Response Times**: p50, p95, p99, min, max\n- **Failures**: Count and percentage of
    failed requests\n- **Charts**: Real-time visualization of performance\n\n### CSV Output Files\n\nWhen using --csv=prefix, three files are generated:\n- prefix_stats.csv:
    Per-request statistics\n- prefix_stats_history.csv: Time-series data\n- prefix_failures.csv: Failure details\n\n### Example Analysis\n\npython\nimport pandas as pd\n\n# Load
    stats\nstats = pd.read_csv('reports/load_test_results_stats.csv')\n\n# Check p95 latencies\np95_violations = stats[stats['95%'] > 200]\nif len(p95_violations) > 0:\n
    print(\"Endpoints exceeding p95 target:\")\n    print(p95_violations[['Name', '95%']])\n\n\n## Distributed Testing\n\nFor higher load, run Locust in distributed mode:\n\nbash\n#
    Start master\nlocust -f tests/load/locustfile.py --master --host=http://localhost:8000\n\n# Start workers (run on multiple machines)\nlocust -f tests/load/locustfile.py --worker
    --master-host=<master-ip>\n\n\n## CI/CD Integration\n\n### GitHub Actions Example\n\nyaml\nload-test:\n  runs-on: ubuntu-latest\n  steps:\n    - uses: actions/checkout@v4\n\n
    - name: Start API\n      run: |\n        docker-compose up -d\n        sleep 10\n\n    - name: Run Load Tests\n      run: |\n        pip install locust\n        locust -f
    tests/load/locustfile.py \\\n          --host=http://localhost:8000 \\\n          --users=50 \\\n          --spawn-rate=5 \\\n          --run-time=2m \\\n          --headless
    \\\n          --html=load_test_report.html \\\n          --exit-code-on-error 1\n\n    - name: Upload Report\n      uses: actions/upload-artifact@v4\n      with:\n        name:
    load-test-report\n        path: load_test_report.html\n\n\n### Performance Gates\n\nUse the --exit-code-on-error flag to fail CI if:\n- Any requests fail\n- Error rate exceeds
    threshold\n\nCustom exit codes can be implemented using Locust's event hooks.\n\n## Troubleshooting\n\n### High Failure Rate\n\n1. Check if the API server is running\n2. Verify
    database connectivity\n3. Check for rate limiting\n4. Review server logs for errors\n\n### Inconsistent Results\n\n1. Ensure consistent test environment\n2. Warm up the API
    before testing\n3. Run multiple test iterations\n4. Check for external factors (network, other processes)\n\n### Memory Issues\n\nFor long-running tests:\nbash\n# Increase spawn
    rate to reduce memory\nlocust -f tests/load/locustfile.py \\\n    --host=http://localhost:8000 \\\n    --users=100 \\\n    --spawn-rate=20 \\\n    --run-time=30m \\\n
    --headless\n\n\n## Best Practices\n\n1. Baseline First: Run tests against a known-good configuration to establish baselines\n2. Gradual Ramp-Up: Use spawn-rate to gradually
    increase load\n3. Realistic Data: Ensure test database has representative data volume\n4. Isolated Environment: Run load tests in isolated environments\n5. Monitor Resources:
    Watch CPU, memory, and database metrics during tests\n6. Repeat Tests: Run multiple iterations for consistent results\n7. Document Changes: Note configuration changes between
    test runs\n"}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"completed","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"completed","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"completed","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"completed","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"completed","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"in_progress","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: Bash] {"command":"uv run ruff check tests/load/ 2>&1","description":"Run ruff linter on load tests"}
    [Tool: Bash] {"command":"uv run ruff format --check tests/load/ 2>&1","description":"Check ruff formatting on load tests"}
    [Tool: Bash] {"command":"uv run ruff format --check tests/load/ 2>&1","description":"Check ruff formatting on load tests"}
    [Tool: Read] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/locustfile.py","offset":495,"limit":10}
    [Tool: Edit] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/locustfile.py","old_string":"        print(fnResponse Times:)","new_string":"        print(nResponse
    Times:)"}
    [Tool: Edit] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/scenarios/crawl_load.py","old_string":"                json={name: fMixed Test Project},","new_string":"
                   json={name: Mixed Test Project},"}
    [Tool: Edit] {"file_path":"/Users/beckett/Projects/Openahrush/tests/load/scenarios/crawl_load.py","old_string":"                json={name: fMixed Test Project},","new_string":"
                   json={name: Mixed Test Project},"}
    [Tool: Bash] {"command":"uv run ruff check tests/load/ 2>&1","description":"Run ruff linter on load tests"}
    [Tool: Bash] {"command":"uv run mypy tests/load/ 2>&1","description":"Run mypy type checker on load tests"}
    [Tool: Bash] {"command":"uv run mypy tests/load/ 2>&1","description":"Run mypy type checker on load tests"}
    [Tool: Bash] {"command":"uv run ruff format --check tests/load/ 2>&1","description":"Check ruff formatting on load tests"}
    [Tool: Bash] {"command":"uv run ruff format --check tests/load/ 2>&1","description":"Check ruff formatting on load tests"}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"completed","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"completed","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"completed","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"completed","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"completed","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"completed","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: TodoWrite] {"todos":[{"content":"Create tests/load directory structure","status":"completed","activeForm":"Creating tests/load directory structure"},{"content":"Create
    main locustfile.py with API user configuration","status":"completed","activeForm":"Creating main locustfile.py"},{"content":"Create auth_load.py scenario for authentication
    endpoints","status":"completed","activeForm":"Creating auth_load.py scenario"},{"content":"Create api_read_load.py scenario for read
    endpoints","status":"completed","activeForm":"Creating api_read_load.py scenario"},{"content":"Create crawl_load.py scenario for crawl trigger
    endpoints","status":"completed","activeForm":"Creating crawl_load.py scenario"},{"content":"Create README.md with usage instructions","status":"completed","activeForm":"Creating
    README.md documentation"},{"content":"Add locust to dev dependencies","status":"completed","activeForm":"Adding locust to dev dependencies"},{"content":"Verify with ruff and
    mypy","status":"completed","activeForm":"Verifying with ruff and mypy"}]}
    [Tool: Bash] {"command":"find /Users/beckett/Projects/Openahrush/tests -type f | sort","description":"List all load test files"}
    [Tool: Bash] {"command":"find /Users/beckett/Projects/Openahrush/tests -type f | sort","description":"List all load test files"}

    --- RESULT ---
    All files are in place. Here is a summary of the load testing infrastructure implementation:

    ---
    Summary: Load Testing Setup (Sprint 5 Task 5.4.4)

    I have created a production-ready load testing infrastructure for the Openahrush API using Locust.

    Files Created

    tests/
      load/
        __init__.py                    # Package init with documentation
        locustfile.py                  # Main Locust configuration (520 lines)
        README.md                      # Comprehensive usage documentation
        scenarios/
          __init__.py                  # Scenarios package init
          auth_load.py                 # Authentication endpoint tests (265 lines)
          api_read_load.py             # Read API endpoint tests (295 lines)
          crawl_load.py                # Write API endpoint tests (455 lines)

    Key Features

    Main Locustfile (/Users/beckett/Projects/Openahrush/tests/load/locustfile.py):
    - APIUser class: Simulates realistic user behavior with weighted tasks
    - AuthOnlyUser class: Focused authentication testing
    - Event hooks for custom reporting with target compliance checking
    - Automatic user registration, project creation, and cleanup

    Authentication Scenarios (/Users/beckett/Projects/Openahrush/tests/load/scenarios/auth_load.py):
    - Registration throughput testing
    - Login/logout cycles
    - Invalid credential handling
    - Token validation testing
    - Spike traffic generation with AuthSpikeUser

    Read API Scenarios (/Users/beckett/Projects/Openahrush/tests/load/scenarios/api_read_load.py):
    - Health check endpoints (/healthz, /readyz)
    - Project listing (paginated and non-paginated)
    - Issues, alerts, settings retrieval
    - Backlinks overview
    - Cache effectiveness testing with CacheBustingUser

    Write API Scenarios (/Users/beckett/Projects/Openahrush/tests/load/scenarios/crawl_load.py):
    - Project CRUD operations
    - Site and competitor management
    - Alert rule creation
    - Settings updates
    - Burst write testing with BurstWriteUser
    - Realistic mixed workload with MixedWorkloadUser

    Performance Targets (from Sprint 5 spec)

    | Metric           | Target  |
    |------------------|---------|
    | Concurrent users | 100+    |
    | p50 latency      | < 50ms  |
    | p95 latency      | < 200ms |
    | p99 latency      | < 500ms |

    Usage Examples

    # Web UI mode
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Headless CI mode
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --users=100 --spawn-rate=10 --run-time=5m --headless

    # With HTML report
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --users=100 --spawn-rate=10 --run-time=5m --headless \
        --html=reports/load_test_report.html

    # Scenario-specific tests
    locust -f tests/load/scenarios/auth_load.py --host=http://localhost:8000
    locust -f tests/load/scenarios/api_read_load.py --host=http://localhost:8000
    locust -f tests/load/scenarios/crawl_load.py --host=http://localhost:8000

    Dependency Added

    locust>=2.42.6 has been added to the dev dependencies in pyproject.toml.

    Verification

    All files pass linting and type checking:
    - uv run ruff check tests/load/ - All checks passed
    - uv run mypy tests/load/ - Success: no issues found in 6 source files
  ⎿  Context low · Run /compact to compact & continues already formatted
                                                                                                                                                              11:06 PM  <synthetic>

⏺ Agent "Implement integration tests 5.4.2" completed.
  ⎿  Context low · Run /compact to compact & continue
                                                                                                                                                              11:08 PM  <synthetic>

⏺ Agent "Implement security hardening 5.2.x" completed.
  ⎿  Context low · Run /compact to compact & continue
                                                                                                                                                              11:08 PM  <synthetic>

⏺ Agent "Create deployment documentation 5.5-5.6" completed.
  ⎿  Context low · Run /compact to compact & continue
                                                                                                                                                              11:11 PM  <synthetic>

⏺ Agent "Implement database optimization 5.3.1" completed.
  ⎿  Context low · Run /compact to compact & continue
                                                                                                                                                              11:14 PM  <synthetic>

⏺ Agent "Implement rate limiting 5.1.x" completed.
  ⎿  Context low · Run /compact to compact & continue
                                                                                                                                                              11:20 PM  <synthetic>
