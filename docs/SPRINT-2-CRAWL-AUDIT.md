# Sprint 2: Hybrid Crawl & Site Audit

**Duration:** 3-4 weeks
**Dependencies:** Sprint 0 (Foundation)
**Status:** Not Started

This sprint implements the core crawling engine with hybrid HTML+JS support, rules-based issue detection, impact scoring, and visibility alerting.

---

## Objectives

1. Build crawl orchestration state machine
2. Implement HTML-first crawler with frontier management
3. Add Playwright fallback with budget enforcement
4. Create hybrid heuristics for JS rendering decisions
5. Develop rules engine with issue taxonomy
6. Compute impact scores from canonical facts
7. Build diff engine for crawl comparisons
8. Implement alert engine for visibility changes

---

## Epic 2.1: Crawl Infrastructure

### Task 2.1.1: Create crawl_runs table migration

**Description:** Add database tables for tracking crawl jobs.

**Schema (crawl_runs):**
```sql
CREATE TABLE crawl_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    -- queued, running, html_complete, selecting_js, rendering_js, analyzing, completed, failed
    config_snapshot JSONB NOT NULL,  -- ProjectSettings at time of crawl
    started_at TIMESTAMPTZ,
    html_completed_at TIMESTAMPTZ,
    js_completed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    stats JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_crawl_runs_project ON crawl_runs(project_id);
CREATE INDEX idx_crawl_runs_status ON crawl_runs(status);
CREATE INDEX idx_crawl_runs_created ON crawl_runs(created_at DESC);
```

**Stats JSONB Example:**
```json
{
  "pages_crawled": 1500,
  "pages_rendered": 45,
  "pages_failed": 12,
  "links_discovered": 8500,
  "issues_found": 234,
  "duration_seconds": 340
}
```

**Acceptance Criteria:**
- [ ] Migration creates table with all columns
- [ ] config_snapshot stores settings at crawl time
- [ ] Status enum supports full lifecycle
- [ ] Stats JSONB tracks key metrics

---

### Task 2.1.2: Create crawl_pages table migration

**Description:** Store per-page crawl results.

**Schema (crawl_pages):**
```sql
CREATE TABLE crawl_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_run_id UUID REFERENCES crawl_runs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    final_url TEXT,  -- after redirects
    status_code INTEGER,
    content_type TEXT,
    response_time_ms INTEGER,
    render_mode TEXT,  -- 'html', 'js'

    -- Extracted fields
    title TEXT,
    meta_description TEXT,
    canonical_url TEXT,
    meta_robots TEXT,
    h1_count INTEGER,
    first_h1 TEXT,
    word_count INTEGER,
    text_length INTEGER,

    -- Hashes for change detection
    html_hash TEXT,
    rendered_hash TEXT,
    content_hash TEXT,

    -- Artifacts
    html_artifact_key TEXT,  -- MinIO key for raw HTML
    rendered_artifact_key TEXT,  -- MinIO key for rendered HTML

    -- Flags
    was_rendered BOOLEAN DEFAULT false,
    render_trigger TEXT,  -- which heuristic triggered render

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_crawl_pages_run ON crawl_pages(crawl_run_id);
CREATE INDEX idx_crawl_pages_url ON crawl_pages(crawl_run_id, url);
CREATE INDEX idx_crawl_pages_status ON crawl_pages(crawl_run_id, status_code);
```

**Acceptance Criteria:**
- [ ] Migration creates table with all columns
- [ ] Indexes support common query patterns
- [ ] Artifact keys reference MinIO storage

---

### Task 2.1.3: Create link_edges table migration

**Description:** Store internal link graph from crawl.

**Schema (link_edges):**
```sql
CREATE TABLE link_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_run_id UUID REFERENCES crawl_runs(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    anchor_text TEXT,
    is_internal BOOLEAN NOT NULL,
    link_type TEXT,  -- 'a', 'canonical', 'redirect', 'img', 'script', etc.
    rel_flags TEXT[],
    is_broken BOOLEAN DEFAULT false,
    target_status_code INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_link_edges_run ON link_edges(crawl_run_id);
CREATE INDEX idx_link_edges_source ON link_edges(crawl_run_id, source_url);
CREATE INDEX idx_link_edges_target ON link_edges(crawl_run_id, target_url);
CREATE INDEX idx_link_edges_broken ON link_edges(crawl_run_id, is_broken) WHERE is_broken;
```

**Acceptance Criteria:**
- [ ] Migration creates table
- [ ] Broken link index for fast queries
- [ ] Supports multiple link types

---

### Task 2.1.4: Create issue tables migration

**Description:** Store issue types and instances.

**Schema (issue_types):**
```sql
CREATE TABLE issue_types (
    id TEXT PRIMARY KEY,  -- e.g., 'missing_title', 'broken_internal_link'
    category TEXT NOT NULL,  -- 'content', 'technical', 'links', 'indexability'
    severity INTEGER NOT NULL,  -- 1 (low) to 5 (critical)
    name TEXT NOT NULL,
    description TEXT,
    recommendation TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Schema (issue_instances):**
```sql
CREATE TABLE issue_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crawl_run_id UUID REFERENCES crawl_runs(id) ON DELETE CASCADE,
    crawl_page_id UUID REFERENCES crawl_pages(id) ON DELETE SET NULL,
    issue_type_id TEXT REFERENCES issue_types(id),
    affected_url TEXT NOT NULL,
    confidence NUMERIC(4,3) NOT NULL,  -- 0.000 to 1.000
    impact_score NUMERIC(10,2),
    evidence JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_issue_instances_run ON issue_instances(crawl_run_id);
CREATE INDEX idx_issue_instances_type ON issue_instances(crawl_run_id, issue_type_id);
CREATE INDEX idx_issue_instances_impact ON issue_instances(crawl_run_id, impact_score DESC NULLS LAST);
CREATE INDEX idx_issue_instances_url ON issue_instances(affected_url);
```

**Acceptance Criteria:**
- [ ] issue_types seeded with MVP rules
- [ ] issue_instances tracks per-page issues
- [ ] impact_score index for sorted queries
- [ ] Evidence JSONB stores rule-specific data

---

## Epic 2.2: HTML Crawler

### Task 2.2.1: Create URL frontier manager

**Description:** Implement priority queue for crawl URLs.

**Acceptance Criteria:**
- [ ] `apps/workers/src/semrush_workers/crawl/frontier.py` created
- [ ] Priority queue with depth-based ordering
- [ ] URL normalization (trailing slashes, case, sorting params)
- [ ] Deduplication via seen set
- [ ] Respects max_depth from settings
- [ ] Respects max_pages budget

**Implementation:**
```python
class Frontier:
    def __init__(self, settings: ProjectSettings):
        self.max_pages = settings.max_pages
        self.max_depth = settings.max_depth
        self.queue: PriorityQueue = PriorityQueue()
        self.seen: set[str] = set()

    def add(self, url: str, depth: int) -> bool:
        normalized = normalize_url(url)
        if normalized in self.seen or depth > self.max_depth:
            return False
        self.seen.add(normalized)
        self.queue.put((depth, normalized))
        return True

    def pop(self) -> tuple[int, str] | None:
        if len(self.seen) >= self.max_pages:
            return None
        return self.queue.get_nowait() if not self.queue.empty() else None
```

---

### Task 2.2.2: Implement robots.txt parser

**Description:** Parse and respect robots.txt directives.

**Acceptance Criteria:**
- [ ] `libs/seo/src/semrush_seo/robots.py` created
- [ ] Fetches and caches robots.txt per domain
- [ ] Parses Allow/Disallow rules
- [ ] Matches User-Agent correctly
- [ ] Extracts Sitemap URLs
- [ ] Respects crawl-delay if present
- [ ] Bypass if respect_robots=false in settings

---

### Task 2.2.3: Implement sitemap parser

**Description:** Parse sitemap.xml and add URLs to frontier.

**Acceptance Criteria:**
- [ ] `libs/seo/src/semrush_seo/sitemap.py` created
- [ ] Parses sitemap.xml and sitemap index files
- [ ] Handles gzip-compressed sitemaps
- [ ] Extracts URLs and optional lastmod/priority
- [ ] Adds URLs to frontier with low depth
- [ ] Respects use_sitemaps setting

---

### Task 2.2.4: Implement HTTP fetcher

**Description:** Create async HTTP client for fetching pages.

**Acceptance Criteria:**
- [ ] `apps/workers/src/semrush_workers/crawl/fetcher.py` created
- [ ] Uses httpx with async support
- [ ] Follows redirects (configurable limit)
- [ ] Captures response time
- [ ] Sets User-Agent from settings
- [ ] Respects politeness_delay_ms
- [ ] Handles timeouts gracefully
- [ ] Connection pooling per host
- [ ] Concurrency limited to concurrency_html

**Implementation:**
```python
class Fetcher:
    def __init__(self, settings: ProjectSettings):
        self.user_agent = settings.user_agent
        self.delay_ms = settings.politeness_delay_ms
        self.semaphore = asyncio.Semaphore(settings.concurrency_html)

    async def fetch(self, url: str) -> FetchResult:
        async with self.semaphore:
            start = time.monotonic()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                    timeout=30.0
                )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if self.delay_ms:
                await asyncio.sleep(self.delay_ms / 1000)
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                body=response.text,
                response_time_ms=elapsed_ms
            )
```

---

### Task 2.2.5: Implement HTML extractor

**Description:** Extract SEO-relevant fields from HTML.

**Acceptance Criteria:**
- [ ] `libs/seo/src/semrush_seo/extraction.py` implemented
- [ ] Extracts: title, meta description, canonical, meta robots
- [ ] Extracts: H1 count, first H1 text
- [ ] Counts words and text length
- [ ] Extracts all internal/external links
- [ ] Identifies broken link patterns
- [ ] Uses lxml or selectolax for performance

**Extracted Fields:**
```python
@dataclass
class PageData:
    title: str | None
    meta_description: str | None
    canonical_url: str | None
    meta_robots: str | None
    h1_count: int
    first_h1: str | None
    word_count: int
    text_length: int
    internal_links: list[Link]
    external_links: list[Link]
    scripts: list[str]
    html_hash: str
```

---

### Task 2.2.6: Build crawl orchestrator

**Description:** Main crawl loop orchestrating fetch, extract, store.

**Acceptance Criteria:**
- [ ] `apps/workers/src/semrush_workers/crawl/orchestrator.py` created
- [ ] Initializes frontier with seed_url + sitemap URLs
- [ ] Runs async fetch loop with concurrency
- [ ] Extracts and stores page data
- [ ] Builds link edges
- [ ] Tracks crawl stats
- [ ] Updates crawl_run status
- [ ] Emits `crawl.page_fetched` events

**Orchestration Flow:**
1. Load project settings
2. Create crawl_run with config_snapshot
3. Initialize frontier with seed + sitemap URLs
4. Run fetch loop until budget exhausted
5. Store pages and edges
6. Update status to `html_complete`
7. Trigger JS candidate selection

---

## Epic 2.3: Hybrid JS Rendering

### Task 2.3.1: Implement thin DOM heuristic

**Description:** Detect pages that need JS rendering due to thin content.

**Acceptance Criteria:**
- [ ] `apps/workers/src/semrush_workers/crawl/heuristics.py` created
- [ ] Returns true if: text < min_text_chars (default 200)
- [ ] Returns true if: word_count < min_word_count (default 50)
- [ ] Returns true if: body mostly scripts/styles

**Implementation:**
```python
def needs_js_thin_dom(page: PageData, settings: ProjectSettings) -> bool:
    min_chars = settings.get("min_text_chars", 200)
    min_words = settings.get("min_word_count", 50)
    return page.text_length < min_chars or page.word_count < min_words
```

---

### Task 2.3.2: Implement SPA shell heuristic

**Description:** Detect SPA framework shells that need rendering.

**Acceptance Criteria:**
- [ ] Detects single root div (#root, #app, #__next)
- [ ] Detects framework bundles (app.*.js, chunk.*.js, main.*.js)
- [ ] Detects React/Vue/Angular markers
- [ ] Low false positive rate

**Implementation:**
```python
SPA_ROOT_IDS = ["root", "app", "__next", "__nuxt", "svelte"]
SPA_BUNDLE_PATTERNS = [r"app\.[a-f0-9]+\.js", r"main\.[a-f0-9]+\.js", r"chunk\."]

def needs_js_spa_shell(page: PageData, html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    body = soup.body
    if not body:
        return False
    # Check for single root element with SPA ID
    direct_children = [c for c in body.children if c.name]
    if len(direct_children) == 1:
        child = direct_children[0]
        if child.get("id") in SPA_ROOT_IDS:
            return True
    # Check for SPA bundle scripts
    for script in page.scripts:
        for pattern in SPA_BUNDLE_PATTERNS:
            if re.search(pattern, script):
                return True
    return False
```

---

### Task 2.3.3: Implement required selectors heuristic

**Description:** Check if user-specified selectors are missing.

**Acceptance Criteria:**
- [ ] Reads required_selectors from project settings
- [ ] Returns true if any selector not found in HTML
- [ ] Supports CSS selector syntax
- [ ] Default selectors: none (user configurable)

**Implementation:**
```python
def needs_js_missing_selectors(html: str, settings: ProjectSettings) -> bool:
    selectors = settings.get("required_selectors", [])
    if not selectors:
        return False
    soup = BeautifulSoup(html, "lxml")
    for selector in selectors:
        if not soup.select_one(selector):
            return True
    return False
```

---

### Task 2.3.4: Implement client-side redirect heuristic

**Description:** Detect JS-based redirects.

**Acceptance Criteria:**
- [ ] Detects window.location assignments
- [ ] Detects meta refresh with low delay
- [ ] Returns true if likely redirect

**Patterns:**
```python
REDIRECT_PATTERNS = [
    r"window\.location\s*=",
    r"window\.location\.href\s*=",
    r"window\.location\.replace\s*\(",
    r'<meta[^>]+http-equiv=["\']refresh["\']',
]
```

---

### Task 2.3.5: Build JS candidate selector

**Description:** Apply heuristics to select pages for rendering.

**Acceptance Criteria:**
- [ ] Queries crawl_pages with was_rendered=false
- [ ] Applies all heuristics in order
- [ ] Respects max_rendered_pages budget
- [ ] Records which heuristic triggered selection
- [ ] Updates crawl_run status to `selecting_js`
- [ ] Emits `crawl.js_candidates_selected` event

**Priority Order:**
1. Required selectors missing (highest priority)
2. Thin DOM / empty content
3. SPA shell detected
4. Client-side redirect detected

---

### Task 2.3.6: Implement Playwright renderer

**Description:** Render pages with Playwright under budget constraints.

**Acceptance Criteria:**
- [ ] `apps/workers/src/semrush_workers/crawl/renderer.py` created
- [ ] Uses playwright-python with Chromium
- [ ] Respects max_render_time_ms per page
- [ ] Respects concurrency_js (separate from HTML)
- [ ] Captures rendered HTML
- [ ] Re-extracts page data from rendered HTML
- [ ] Stores rendered_hash and rendered_artifact_key
- [ ] Updates was_rendered and render_trigger

**Implementation:**
```python
class Renderer:
    def __init__(self, settings: ProjectSettings):
        self.timeout_ms = settings.max_render_time_ms
        self.semaphore = asyncio.Semaphore(settings.concurrency_js)

    async def render(self, url: str) -> RenderedResult:
        async with self.semaphore:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=self.timeout_ms)
                    await page.wait_for_load_state("networkidle", timeout=5000)
                    html = await page.content()
                    return RenderedResult(url=url, html=html, success=True)
                except Exception as e:
                    return RenderedResult(url=url, error=str(e), success=False)
                finally:
                    await browser.close()
```

---

### Task 2.3.7: Build render orchestrator

**Description:** Process JS candidates through Playwright.

**Acceptance Criteria:**
- [ ] Loads candidate pages up to budget
- [ ] Renders pages concurrently (bounded)
- [ ] Re-extracts and updates crawl_page records
- [ ] Stores rendered HTML to MinIO
- [ ] Updates crawl_run status to `rendering_js`
- [ ] Emits `crawl.page_rendered` for each page
- [ ] Updates status to `analyzing` when complete

---

## Epic 2.4: Rules Engine

### Task 2.4.1: Seed issue types

**Description:** Create migration to seed issue taxonomy.

**Issue Types (MVP):**

**Critical (severity=5):**
- `server_error_5xx` - 5xx status code
- `redirect_loop` - Redirect loop detected
- `redirect_chain_long` - Redirect chain > 3 hops
- `broken_internal_link` - Internal link to 4xx/5xx

**High (severity=4):**
- `internal_4xx` - Page returns 4xx status
- `missing_title` - No title tag
- `duplicate_title` - Exact duplicate title
- `canonical_wrong_domain` - Canonical points to different domain
- `missing_self_canonical` - Missing canonical or not self-referencing

**Medium (severity=3):**
- `title_too_long` - Title > 60 chars
- `title_too_short` - Title < 30 chars
- `meta_description_too_long` - > 160 chars
- `meta_description_too_short` - < 50 chars
- `missing_meta_description` - No meta description
- `missing_h1` - No H1 tag
- `multiple_h1` - More than one H1
- `non_https` - HTTP URL (if project is HTTPS)
- `mixed_content` - HTTPS page with HTTP resources

**Low (severity=2):**
- `thin_content` - Word count < threshold
- `orphan_page` - In sitemap but not internally linked

**Acceptance Criteria:**
- [ ] Migration seeds all issue types
- [ ] Each has category, severity, name, description, recommendation
- [ ] Idempotent (can re-run without duplicates)

---

### Task 2.4.2: Implement rule evaluators

**Description:** Create rule functions for each issue type.

**Acceptance Criteria:**
- [ ] `apps/workers/src/semrush_workers/rules/evaluators.py` created
- [ ] Each rule returns (applies: bool, confidence: float, evidence: dict)
- [ ] Rules are pure functions (no side effects)
- [ ] Evidence includes relevant data for debugging

**Example Rule:**
```python
def rule_missing_title(page: CrawlPage) -> RuleResult:
    if not page.title or not page.title.strip():
        return RuleResult(
            applies=True,
            confidence=1.0,
            evidence={"expected": "non-empty title tag", "found": None}
        )
    return RuleResult(applies=False)

def rule_title_too_long(page: CrawlPage) -> RuleResult:
    if page.title and len(page.title) > 60:
        return RuleResult(
            applies=True,
            confidence=0.9,
            evidence={"length": len(page.title), "max": 60, "title": page.title}
        )
    return RuleResult(applies=False)
```

---

### Task 2.4.3: Implement rules engine

**Description:** Run all rules against crawl pages and store issues.

**Acceptance Criteria:**
- [ ] `apps/workers/src/semrush_workers/rules/engine.py` created
- [ ] Loads all enabled rules
- [ ] Iterates all crawl_pages for the run
- [ ] Evaluates each rule against each page
- [ ] Creates issue_instances for positive results
- [ ] Batches database writes for performance
- [ ] Emits `rules.completed` event

**Implementation:**
```python
class RulesEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    async def analyze(self, crawl_run_id: UUID) -> AnalysisResult:
        pages = await load_crawl_pages(crawl_run_id)
        issues = []
        for page in pages:
            for rule in self.rules:
                result = rule.evaluate(page)
                if result.applies:
                    issues.append(IssueInstance(
                        crawl_run_id=crawl_run_id,
                        crawl_page_id=page.id,
                        issue_type_id=rule.issue_type_id,
                        affected_url=page.url,
                        confidence=result.confidence,
                        evidence=result.evidence
                    ))
        await batch_insert_issues(issues)
        return AnalysisResult(issues_found=len(issues))
```

---

### Task 2.4.4: Implement broken link detection

**Description:** Detect broken internal links from link edges.

**Acceptance Criteria:**
- [ ] Queries link_edges where is_internal=true
- [ ] Joins with crawl_pages to get target status
- [ ] Creates issues for 4xx/5xx targets
- [ ] Evidence includes source URL, target URL, status code
- [ ] Counts unique broken URLs, not duplicate edges

---

### Task 2.4.5: Implement orphan page detection

**Description:** Find pages only in sitemap (not internally linked).

**Acceptance Criteria:**
- [ ] Queries pages discovered via sitemap
- [ ] Checks if any internal link points to them
- [ ] Creates issues for orphan pages
- [ ] Low severity (informational)

---

## Epic 2.5: Impact Scoring

### Task 2.5.1: Implement traffic weight computation

**Description:** Calculate traffic weight from canonical facts.

**Acceptance Criteria:**
- [ ] Queries search_fact_daily and analytics_fact_daily
- [ ] Aggregates last 28 days by page_url
- [ ] Computes: impressions, clicks, sessions, conversions
- [ ] Returns normalized traffic_weight (0-1 scale)
- [ ] Falls back to 0.5 if no data

**Formula:**
```python
traffic_weight = normalize(
    impressions * 0.3 +
    clicks * 0.3 +
    sessions * 0.2 +
    conversions * 0.2
)
```

---

### Task 2.5.2: Compute and store impact scores

**Description:** Update issue_instances with impact scores.

**Acceptance Criteria:**
- [ ] `impact_score = severity * confidence * traffic_weight`
- [ ] Updates all issue_instances for crawl_run
- [ ] Handles pages without traffic data gracefully
- [ ] Runs after rules engine completes

**Implementation:**
```python
async def compute_impact_scores(crawl_run_id: UUID, project_id: UUID):
    # Build URL → traffic_weight map
    traffic = await get_traffic_weights(project_id, days=28)

    # Update issues
    issues = await get_issues(crawl_run_id)
    for issue in issues:
        weight = traffic.get(normalize_url(issue.affected_url), 0.5)
        issue.impact_score = issue.severity * issue.confidence * weight

    await batch_update_issues(issues)
```

---

### Task 2.5.3: Create issue API endpoints

**Description:** Implement issue listing and filtering.

**Acceptance Criteria:**
- [ ] `GET /crawls/{id}/issues` lists issues for a crawl
- [ ] Supports sort by impact, severity, category
- [ ] Supports filter by issue_type, severity
- [ ] Pagination with limit/offset
- [ ] Returns issue details with evidence

---

### Task 2.5.4: Create project issues endpoint

**Description:** Get latest issues for a project.

**Acceptance Criteria:**
- [ ] `GET /projects/{id}/issues` returns latest crawl issues
- [ ] Sorted by impact_score DESC by default
- [ ] Supports limit parameter
- [ ] Returns 404 if no crawl runs exist

---

## Epic 2.6: Diff Engine

### Task 2.6.1: Implement issue diff computation

**Description:** Compare issues between two crawl runs.

**Acceptance Criteria:**
- [ ] Finds new issues (in B, not in A)
- [ ] Finds resolved issues (in A, not in B)
- [ ] Finds changed issues (severity/confidence changed)
- [ ] Matches by (issue_type_id, affected_url)
- [ ] Stores diff results for API

**Implementation:**
```python
async def compute_diff(run_a: UUID, run_b: UUID) -> DiffResult:
    issues_a = {(i.issue_type_id, i.affected_url): i for i in await get_issues(run_a)}
    issues_b = {(i.issue_type_id, i.affected_url): i for i in await get_issues(run_b)}

    keys_a = set(issues_a.keys())
    keys_b = set(issues_b.keys())

    added = [issues_b[k] for k in (keys_b - keys_a)]
    resolved = [issues_a[k] for k in (keys_a - keys_b)]
    changed = []
    for k in (keys_a & keys_b):
        if issues_a[k].severity != issues_b[k].severity:
            changed.append(issues_b[k])

    return DiffResult(added=added, resolved=resolved, changed=changed)
```

---

### Task 2.6.2: Implement diff API endpoint

**Description:** Expose issue diff via API.

**Acceptance Criteria:**
- [ ] `GET /projects/{id}/issues/diffs?from_crawl_run_id=...&to_crawl_run_id=...`
- [ ] Returns added, resolved, changed arrays
- [ ] 400 if crawl runs not from same project
- [ ] 404 if crawl runs don't exist

---

### Task 2.6.3: Store diff snapshots

**Description:** Optionally persist diff results.

**Acceptance Criteria:**
- [ ] Create `issue_diffs` table (optional)
- [ ] Store diff after each crawl
- [ ] Enable historical diff queries
- [ ] Keep last N diffs per project (configurable)

---

## Epic 2.7: Visibility & Alerts

### Task 2.7.1: Create alerts table migration

**Description:** Store alert configuration and instances.

**Schema (alert_rules):**
```sql
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    rule_type TEXT NOT NULL,  -- 'visibility_drop', 'ctr_opportunity', 'regression'
    config JSONB NOT NULL DEFAULT '{}',
    is_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Schema (alerts):**
```sql
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    alert_rule_id UUID REFERENCES alert_rules(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- 'project', 'page', 'query'
    entity_key TEXT NOT NULL,
    severity TEXT NOT NULL,  -- 'info', 'warn', 'critical'
    payload JSONB DEFAULT '{}',
    is_acknowledged BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_alerts_project ON alerts(project_id, created_at DESC);
CREATE INDEX idx_alerts_severity ON alerts(project_id, severity);
```

**Acceptance Criteria:**
- [ ] Migration creates both tables
- [ ] Supports multiple alert types
- [ ] Payload stores type-specific data

---

### Task 2.7.2: Implement visibility drop detector

**Description:** Detect significant drops in search visibility.

**Acceptance Criteria:**
- [ ] Compares recent period to previous period
- [ ] Triggers if drop > threshold (default 30%)
- [ ] Works at query and page level
- [ ] Creates alert with severity based on magnitude

**Implementation:**
```python
async def detect_visibility_drops(project_id: UUID, threshold_pct: float = 30):
    # Compare last 7 days vs previous 7 days
    recent = await get_impressions(project_id, days=7)
    previous = await get_impressions(project_id, days=14, offset=7)

    alerts = []
    for entity_key, recent_val in recent.items():
        prev_val = previous.get(entity_key, 0)
        if prev_val > 0:
            drop_pct = (prev_val - recent_val) / prev_val * 100
            if drop_pct >= threshold_pct:
                alerts.append(Alert(
                    kind="visibility_drop",
                    entity_key=entity_key,
                    severity="warn" if drop_pct < 50 else "critical",
                    payload={"drop_pct": drop_pct, "recent": recent_val, "previous": prev_val}
                ))
    return alerts
```

---

### Task 2.7.3: Implement CTR opportunity detector

**Description:** Find high-impression, low-CTR queries.

**Acceptance Criteria:**
- [ ] Queries search_fact_daily for high impressions
- [ ] Flags queries with CTR below expected curve
- [ ] Creates info-level alerts
- [ ] Includes suggested action in payload

**Expected CTR by Position:**
- Position 1: ~30%
- Position 2: ~15%
- Position 3: ~10%
- Position 4-10: ~5%

---

### Task 2.7.4: Implement regression detector

**Description:** Detect significant issue count increases.

**Acceptance Criteria:**
- [ ] Compares issue counts between crawls
- [ ] Triggers if new issues > threshold (default 10)
- [ ] Creates alert with list of new issue types
- [ ] Runs after crawl analysis completes

---

### Task 2.7.5: Build alert scheduler

**Description:** Run alert detection on schedule.

**Acceptance Criteria:**
- [ ] Runs daily after integration sync
- [ ] Runs after each crawl completes
- [ ] Queries active alert_rules per project
- [ ] Executes appropriate detector
- [ ] Stores alerts in database
- [ ] Emits `alert.fired` events

---

### Task 2.7.6: Create alert API endpoints

**Description:** Implement alert listing and management.

**Acceptance Criteria:**
- [ ] `GET /projects/{id}/alerts` lists alerts
- [ ] Supports filter by severity, kind
- [ ] Supports pagination
- [ ] `POST /projects/{id}/alerts/rules` creates/updates rules
- [ ] Returns alert details with payload

---

## Verification Checklist

### Crawl Engine
- [ ] Crawl starts from seed_url
- [ ] Sitemap URLs added to frontier
- [ ] robots.txt respected
- [ ] Pages fetched with correct User-Agent
- [ ] Politeness delay applied
- [ ] max_pages budget enforced
- [ ] max_depth limit enforced
- [ ] Page data extracted correctly
- [ ] Link edges captured

### Hybrid Rendering
- [ ] Thin DOM triggers rendering
- [ ] SPA shell triggers rendering
- [ ] Missing selectors trigger rendering
- [ ] max_rendered_pages budget enforced
- [ ] max_render_time_ms timeout works
- [ ] Rendered HTML re-extracted
- [ ] render_trigger recorded

### Rules & Issues
- [ ] All MVP rules implemented
- [ ] Issues created with evidence
- [ ] Impact scores computed
- [ ] Broken links detected
- [ ] Orphan pages detected
- [ ] API returns sorted issues

### Diffs & Alerts
- [ ] Diff shows added issues
- [ ] Diff shows resolved issues
- [ ] Visibility drop alerts fire
- [ ] CTR opportunity alerts fire
- [ ] Regression alerts fire
- [ ] Alert API returns data

---

## Notes

### Performance Considerations
- Use asyncio.gather for concurrent fetches
- Batch database inserts (100+ rows)
- Stream large crawl results
- Consider worker pool for CPU-bound extraction

### Resource Limits
- HTML concurrency: default 16, configurable
- JS concurrency: default 2-4 (Playwright is heavy)
- Memory: Monitor Playwright browser instances
- Timeout: Kill hung renders after max_render_time_ms

### Future: Rust Crawler
MVP uses Python crawler. For v1+, the Rust `crates/crawler` can be used for higher throughput. The Python orchestrator will call the Rust crawler as a subprocess and consume its output.
