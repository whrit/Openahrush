# Sprint 1: Integrations (GSC/GA4/BWT)

**Duration:** 2-3 weeks
**Dependencies:** Sprint 0 (Foundation)
**Status:** Complete (2025-12-28)

This sprint implements the "truth-first" integrations: OAuth flows, data synchronization, and normalization for Google Search Console, Google Analytics 4, and Bing Webmaster Tools.

---

## Objectives

1. Implement OAuth 2.0 flows for Google and Bing
2. Securely store and refresh access tokens
3. Discover and map provider properties to projects
4. Create daily sync scheduler with backfill support
5. Normalize data into canonical fact tables
6. Build provider adapters with pluggable architecture

---

## Epic 1.1: Integration Infrastructure

### Task 1.1.1: Create integration_accounts table migration

**Description:** Add database tables for storing integration account data.

**Schema (integration_accounts):**
```sql
CREATE TABLE integration_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,  -- 'google_search_console', 'ga4', 'bing_webmaster'
    external_account_id TEXT,  -- provider's account/email identifier
    status TEXT NOT NULL DEFAULT 'connected',  -- connected, degraded, disconnected
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_integration_accounts_user ON integration_accounts(user_id);
CREATE INDEX idx_integration_accounts_provider ON integration_accounts(provider);
```

**Schema (integration_tokens):**
```sql
CREATE TABLE integration_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_account_id UUID REFERENCES integration_accounts(id) ON DELETE CASCADE,
    access_token_encrypted BYTEA NOT NULL,
    refresh_token_encrypted BYTEA,
    token_type TEXT DEFAULT 'Bearer',
    expires_at TIMESTAMPTZ,
    scopes TEXT[],
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX idx_integration_tokens_account ON integration_tokens(integration_account_id);
```

**Acceptance Criteria:**
- [x] Migration creates both tables
- [x] Encrypted token columns use BYTEA
- [x] Proper indexes for common queries
- [x] Foreign key cascades work correctly

---

### Task 1.1.2: Implement token encryption utilities

**Description:** Create utilities for encrypting/decrypting OAuth tokens at rest.

**Acceptance Criteria:**
- [x] `libs/core/src/semrush_core/security/encryption.py` created
- [x] Uses Fernet symmetric encryption (or AWS KMS for production)
- [x] Encryption key loaded from environment variable
- [x] `encrypt_token(plaintext: str) -> bytes` function
- [x] `decrypt_token(ciphertext: bytes) -> str` function
- [x] Key rotation support (optional for MVP)

**Implementation Notes:**
```python
from cryptography.fernet import Fernet

class TokenEncryption:
    def __init__(self, key: bytes):
        self.fernet = Fernet(key)

    def encrypt(self, token: str) -> bytes:
        return self.fernet.encrypt(token.encode())

    def decrypt(self, encrypted: bytes) -> str:
        return self.fernet.decrypt(encrypted).decode()
```

---

### Task 1.1.3: Create integration_properties table migration

**Description:** Store discovered provider properties and their mapping to projects.

**Schema (integration_properties):**
```sql
CREATE TABLE integration_properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_account_id UUID REFERENCES integration_accounts(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    property_id TEXT NOT NULL,  -- provider's property identifier
    display_name TEXT,
    property_type TEXT,  -- 'domain', 'url_prefix', 'property', etc.
    metadata JSONB DEFAULT '{}',
    discovered_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(integration_account_id, provider, property_id)
);
```

**Schema (integration_mappings):**
```sql
CREATE TABLE integration_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    integration_property_id UUID REFERENCES integration_properties(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, integration_property_id)
);
```

**Acceptance Criteria:**
- [x] Migration creates both tables
- [x] Unique constraints prevent duplicate mappings
- [x] Cascading deletes work correctly

---

### Task 1.1.4: Create sync_runs table migration

**Description:** Track integration sync job status and history.

**Schema (sync_runs):**
```sql
CREATE TABLE sync_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_mapping_id UUID REFERENCES integration_mappings(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    property_id TEXT NOT NULL,
    mode TEXT NOT NULL,  -- 'backfill', 'incremental'
    status TEXT NOT NULL DEFAULT 'queued',  -- queued, running, completed, failed
    date_range_start DATE,
    date_range_end DATE,
    records_written INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_sync_runs_mapping ON sync_runs(integration_mapping_id);
CREATE INDEX idx_sync_runs_status ON sync_runs(status);
```

**Acceptance Criteria:**
- [x] Migration creates table with all columns
- [x] Status tracking supports full lifecycle
- [x] Date range captured for audit

---

## Epic 1.2: OAuth Flows

### Task 1.2.1: Implement Google OAuth connect flow

**Description:** Create OAuth 2.0 authorization flow for Google (GSC + GA4).

**Acceptance Criteria:**
- [x] `POST /integrations/google_search_console/connect` returns auth URL
- [x] Auth URL includes correct scopes for Search Console
- [x] State parameter generated and stored for CSRF protection
- [x] Redirect URI configurable via environment
- [x] Same endpoint pattern works for `ga4` provider

**Scopes Required:**
- GSC: `https://www.googleapis.com/auth/webmasters.readonly`
- GA4: `https://www.googleapis.com/auth/analytics.readonly`

**Router:** `apps/api/src/semrush_api/routers/integrations.py`

---

### Task 1.2.2: Implement Google OAuth callback handler

**Description:** Handle OAuth callback and exchange code for tokens.

**Acceptance Criteria:**
- [x] `POST /integrations/google_search_console/callback` exchanges code for tokens
- [x] Validates state parameter matches
- [x] Creates integration_account record
- [x] Encrypts and stores access_token and refresh_token
- [x] Returns IntegrationAccount response
- [x] Handles error cases (denied, expired, invalid)

**Implementation Flow:**
1. Validate state matches stored state
2. Exchange authorization code for tokens
3. Fetch user info to get external_account_id
4. Create or update integration_account
5. Encrypt and store tokens
6. Return success response

---

### Task 1.2.3: Implement Bing OAuth connect/callback

**Description:** Create OAuth flow for Bing Webmaster Tools.

**Acceptance Criteria:**
- [x] `POST /integrations/bing_webmaster/connect` returns auth URL
- [x] `POST /integrations/bing_webmaster/callback` handles callback
- [x] Uses Microsoft identity platform endpoints
- [x] Correct scopes for Bing Webmaster API

**Scopes Required:**
- `https://ssl.bing.com/webmaster/api/.default`
- `offline_access`

---

### Task 1.2.4: Implement token refresh logic

**Description:** Automatically refresh expired tokens before API calls.

**Acceptance Criteria:**
- [x] `libs/core/src/semrush_core/security/oauth.py` with refresh logic
- [x] Checks token expiry before each API call
- [x] Uses refresh_token to get new access_token
- [x] Updates stored tokens after refresh
- [x] Marks account as `degraded` if refresh fails
- [x] Retries with exponential backoff

**Implementation:**
```python
async def get_valid_token(account_id: UUID) -> str:
    token = await get_token(account_id)
    if token.is_expired():
        try:
            new_token = await refresh_token(token.refresh_token)
            await store_token(account_id, new_token)
            return new_token.access_token
        except RefreshError:
            await mark_account_degraded(account_id)
            raise
    return token.access_token
```

---

### Task 1.2.5: Implement integration accounts management

**Description:** Create endpoints for listing and disconnecting accounts.

**Acceptance Criteria:**
- [x] `GET /integrations/accounts` lists user's integration accounts
- [x] Returns account status, provider, created_at
- [x] `POST /integrations/accounts/{id}/disconnect` revokes tokens
- [x] Revokes token with provider (if supported)
- [x] Deletes account and cascades to tokens/properties

---

## Epic 1.3: Property Discovery & Mapping

### Task 1.3.1: Implement GSC property discovery

**Description:** Fetch available Search Console properties for an account.

**Acceptance Criteria:**
- [x] `GET /integrations/google_search_console/properties` lists properties
- [x] Requires `integration_account_id` query parameter
- [x] Returns property_id, display_name, property_type
- [x] Stores discovered properties in integration_properties
- [x] Handles domain vs URL-prefix properties

**API Call:** `GET https://www.googleapis.com/webmasters/v3/sites`

---

### Task 1.3.2: Implement GA4 property discovery

**Description:** Fetch available GA4 properties for an account.

**Acceptance Criteria:**
- [x] `GET /integrations/ga4/properties` lists properties
- [x] Returns property_id (e.g., `properties/123456`), display_name
- [x] Stores discovered properties in integration_properties
- [x] Handles account → property hierarchy

**API Call:** `GET https://analyticsadmin.googleapis.com/v1beta/accountSummaries`

---

### Task 1.3.3: Implement BWT property discovery

**Description:** Fetch available Bing Webmaster sites for an account.

**Acceptance Criteria:**
- [x] `GET /integrations/bing_webmaster/properties` lists sites
- [x] Returns property_id (site URL), display_name
- [x] Stores discovered properties in integration_properties

**API Call:** `GET https://ssl.bing.com/webmaster/api.svc/json/GetUserSites`

---

### Task 1.3.4: Implement property → project mapping

**Description:** Map a provider property to a project/site.

**Acceptance Criteria:**
- [x] `POST /projects/{id}/integrations/map` creates mapping
- [x] Validates property exists for user's account
- [x] Validates site belongs to project
- [x] Creates integration_mapping record
- [x] Supports multiple properties per project (GSC + GA4)
- [x] Returns success response

**Request Body:**
```json
{
  "integration_account_id": "uuid",
  "provider": "google_search_console",
  "property_id": "sc-domain:example.com",
  "site_id": "uuid"
}
```

---

## Epic 1.4: Canonical Fact Tables

### Task 1.4.1: Create search_fact_daily table migration

**Description:** Create normalized table for search performance data.

**Schema:**
```sql
CREATE TABLE search_fact_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    engine TEXT NOT NULL,  -- 'google', 'bing'
    date DATE NOT NULL,
    query TEXT,
    page_url TEXT,
    country TEXT,
    device TEXT,  -- 'desktop', 'mobile', 'tablet'
    search_type TEXT,  -- 'web', 'image', 'video', etc.
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    ctr NUMERIC(6,4),  -- 0.0000 to 1.0000
    avg_position NUMERIC(6,2),
    data_quality_flags JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_search_fact_project_date ON search_fact_daily(project_id, date);
CREATE INDEX idx_search_fact_query ON search_fact_daily(project_id, query);
CREATE INDEX idx_search_fact_page ON search_fact_daily(project_id, page_url);
CREATE UNIQUE INDEX idx_search_fact_unique ON search_fact_daily(
    project_id, engine, date,
    COALESCE(query, ''), COALESCE(page_url, ''),
    COALESCE(country, ''), COALESCE(device, '')
);
```

**Acceptance Criteria:**
- [x] Migration creates table with all columns
- [x] Unique index prevents duplicate rows
- [x] Query/page indexes for fast lookups
- [x] data_quality_flags stores sampling info

---

### Task 1.4.2: Create analytics_fact_daily table migration

**Description:** Create normalized table for analytics data.

**Schema:**
```sql
CREATE TABLE analytics_fact_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    date DATE NOT NULL,
    page_url TEXT,
    country TEXT,
    device TEXT,
    source_medium TEXT,
    campaign TEXT,
    sessions INTEGER NOT NULL DEFAULT 0,
    users INTEGER DEFAULT 0,
    engagement_rate NUMERIC(6,4),
    conversions INTEGER DEFAULT 0,
    revenue NUMERIC(12,2),
    data_quality_flags JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_analytics_fact_project_date ON analytics_fact_daily(project_id, date);
CREATE INDEX idx_analytics_fact_page ON analytics_fact_daily(project_id, page_url);
CREATE UNIQUE INDEX idx_analytics_fact_unique ON analytics_fact_daily(
    project_id, date,
    COALESCE(page_url, ''), COALESCE(country, ''),
    COALESCE(device, ''), COALESCE(source_medium, '')
);
```

**Acceptance Criteria:**
- [x] Migration creates table with all columns
- [x] Unique index prevents duplicate rows
- [x] Supports nullable dimensions

---

### Task 1.4.3: Create link_facts table migration

**Description:** Create table for provider-sourced link data.

**Schema:**
```sql
CREATE TABLE link_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    source TEXT NOT NULL,  -- 'gsc', 'bwt', 'import', 'crawl', 'commoncrawl'
    source_url TEXT NOT NULL,
    source_domain TEXT NOT NULL,
    target_url TEXT NOT NULL,
    target_domain TEXT NOT NULL,
    anchor TEXT,
    rel_flags TEXT[],  -- ['nofollow', 'ugc', 'sponsored']
    first_seen DATE,
    last_seen DATE,
    snapshot_id TEXT,  -- for commoncrawl/import sources
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_link_facts_project ON link_facts(project_id);
CREATE INDEX idx_link_facts_target_domain ON link_facts(target_domain);
CREATE INDEX idx_link_facts_source_domain ON link_facts(source_domain);
CREATE INDEX idx_link_facts_source ON link_facts(source);
```

**Acceptance Criteria:**
- [x] Migration creates table with all columns
- [x] Indexes support common query patterns
- [x] Source field tracks data provenance

---

## Epic 1.5: Provider Adapters

### Task 1.5.1: Define SearchAdapter protocol

**Description:** Create abstract base class for search data adapters.

**Acceptance Criteria:**
- [x] `apps/integrations/src/semrush_integrations/adapters/base.py` created
- [x] Abstract methods defined:
  - `list_properties(account_id) -> List[Property]`
  - `fetch_search_performance(property_id, date_range, dimensions) -> DataFrame`
  - `fetch_links(property_id) -> List[Link]` (optional)
- [x] Uses Python Protocol or ABC

**Interface:**
```python
from typing import Protocol

class SearchAdapter(Protocol):
    async def list_properties(self, account_id: UUID) -> list[IntegrationProperty]: ...
    async def fetch_search_performance(
        self,
        property_id: str,
        start_date: date,
        end_date: date,
        dimensions: list[str]
    ) -> list[SearchFactRow]: ...
    async def fetch_links(self, property_id: str) -> list[LinkFact] | None: ...
```

---

### Task 1.5.2: Implement GSC adapter

**Description:** Implement Search Console data adapter.

**Acceptance Criteria:**
- [x] `apps/integrations/src/semrush_integrations/adapters/gsc.py` created
- [x] Implements SearchAdapter protocol
- [x] Fetches search performance via Search Console API
- [x] Handles API pagination (up to 25k rows per request)
- [x] Normalizes response to SearchFactRow
- [x] Respects rate limits (1200 queries/min)
- [x] Fetches links via Links API (if available)

**API Endpoint:** `POST https://www.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query`

---

### Task 1.5.3: Implement GA4 adapter

**Description:** Implement Google Analytics 4 data adapter.

**Acceptance Criteria:**
- [x] `apps/integrations/src/semrush_integrations/adapters/ga4.py` created
- [x] Implements AnalyticsAdapter protocol
- [x] Fetches page-level metrics via Data API
- [x] Handles API quotas
- [x] Normalizes response to AnalyticsFactRow
- [x] Supports dimension filters

**API Endpoint:** `POST https://analyticsdata.googleapis.com/v1beta/properties/{property}/runReport`

---

### Task 1.5.4: Implement BWT adapter

**Description:** Implement Bing Webmaster Tools data adapter.

**Acceptance Criteria:**
- [x] `apps/integrations/src/semrush_integrations/adapters/bwt.py` created
- [x] Implements SearchAdapter protocol
- [x] Fetches search performance via BWT API
- [x] Normalizes to SearchFactRow with engine='bing'
- [x] Handles API rate limits

**API Endpoint:** `GET https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats`

---

## Epic 1.6: Sync Scheduler

### Task 1.6.1: Create sync job infrastructure

**Description:** Set up Redis queue and worker for sync jobs.

**Acceptance Criteria:**
- [x] Redis queue named `integration.sync` created
- [x] Job schema defined: mapping_id, mode, date_range
- [x] Worker consumes and processes jobs
- [x] Job status tracked in sync_runs table
- [x] Retry logic with exponential backoff

**Job Payload:**
```json
{
  "event_type": "integration.sync_requested",
  "event_id": "uuid",
  "payload": {
    "mapping_id": "uuid",
    "mode": "incremental",
    "start_date": "2024-01-01",
    "end_date": "2024-01-07"
  }
}
```

---

### Task 1.6.2: Implement incremental sync logic

**Description:** Fetch and store data for recent date range.

**Acceptance Criteria:**
- [x] Incremental sync fetches last 3-7 days by default
- [x] Avoids re-fetching unchanged data
- [x] Upserts into fact tables (prevents duplicates)
- [x] Updates sync_run status on completion
- [x] Emits `integration.sync_completed` event

**Flow:**
1. Load mapping and get property/adapter
2. Calculate date range (last N days)
3. Fetch data via adapter
4. Transform to canonical schema
5. Upsert into fact table
6. Update sync_run record

---

### Task 1.6.3: Implement backfill sync logic

**Description:** Fetch historical data for initial setup.

**Acceptance Criteria:**
- [x] Backfill supports configurable date range
- [x] Chunks large ranges into smaller requests
- [x] Respects API rate limits
- [x] Progress tracked in sync_run
- [x] Can be resumed if interrupted

**Implementation Notes:**
- GSC provides up to 16 months of history
- GA4 provides configurable retention
- BWT provides ~6 months

---

### Task 1.6.4: Create daily sync scheduler

**Description:** Schedule daily incremental syncs for all active mappings.

**Acceptance Criteria:**
- [x] Scheduler runs daily (configurable time)
- [x] Queries all active integration_mappings
- [x] Enqueues sync job for each mapping
- [x] Respects project integration_sync_frequency setting
- [x] Logs scheduled jobs

---

### Task 1.6.5: Implement manual sync trigger

**Description:** Allow manual sync via API endpoint.

**Acceptance Criteria:**
- [x] `POST /projects/{id}/integrations/sync` triggers sync
- [x] Supports optional provider/property filter
- [x] Supports optional mode (backfill/incremental)
- [x] Returns 202 Accepted with job info
- [x] Rate limited to prevent abuse

---

## Epic 1.7: Data Quality & Status

### Task 1.7.1: Implement data quality flags

**Description:** Track data quality issues during sync.

**Acceptance Criteria:**
- [x] Flags stored in data_quality_flags JSONB column
- [x] Tracks: sampled (bool), sampling_rate, missing_dimensions
- [x] GSC adapter sets sampled flag when applicable
- [x] GA4 adapter tracks sampling info
- [x] Flags queryable in API responses

**Flag Examples:**
```json
{
  "sampled": true,
  "sampling_rate": 0.85,
  "missing_dimensions": ["country"],
  "api_row_limit_hit": true
}
```

---

### Task 1.7.2: Implement sync status endpoints

**Description:** API endpoints for viewing sync status.

**Acceptance Criteria:**
- [x] Sync history queryable per project
- [x] Returns last successful sync time
- [x] Returns error details for failed syncs
- [x] Supports filtering by provider/status

---

### Task 1.7.3: Implement integration health monitoring

**Description:** Track and report integration account health.

**Acceptance Criteria:**
- [x] Account status updated based on sync results
- [x] Consecutive failures → `degraded` status
- [x] Token refresh failure → `degraded` status
- [x] Manual reconnect resets to `connected`
- [x] Health visible in account listing

---

## Verification Checklist

### OAuth Flows
- [x] Google OAuth connect returns valid auth URL
- [x] Google OAuth callback exchanges code successfully
- [x] Tokens encrypted and stored in database
- [x] Token refresh works before expiry
- [x] Bing OAuth connect/callback works
- [x] Disconnect revokes and cleans up

### Property Discovery
- [x] GSC properties discovered and listed
- [x] GA4 properties discovered and listed
- [x] BWT sites discovered and listed
- [x] Properties can be mapped to projects
- [x] Duplicate mappings prevented

### Data Sync
- [x] GSC incremental sync populates search_fact_daily
- [x] GA4 incremental sync populates analytics_fact_daily
- [x] BWT sync populates search_fact_daily with engine='bing'
- [x] Backfill retrieves historical data
- [x] Daily scheduler runs syncs automatically
- [x] Manual sync trigger works

### Data Quality
- [x] Sync runs tracked with status
- [x] Failed syncs have error messages
- [x] Data quality flags captured
- [x] Account health reflects sync status

---

## Notes

### API Rate Limits
- **GSC:** 1,200 queries/minute per project
- **GA4:** 10 concurrent requests, 10,000 tokens/day
- **BWT:** Limited documentation; implement conservative limits

### Security Considerations
- Tokens encrypted at rest with Fernet/KMS
- OAuth state validated to prevent CSRF
- Tokens never logged or exposed in API responses
- Scopes follow least-privilege principle

### Performance Considerations
- Batch inserts for fact tables
- Async API calls where possible
- Connection pooling for database
- Job timeout for long-running syncs

### Next Sprint Dependencies
This sprint provides:
- Canonical fact tables with search/analytics data
- Integration infrastructure for OAuth
- Provider adapter pattern

Required by:
- Sprint 2: Impact scoring uses fact data
- Sprint 4: Reports export fact data
- Sprint 2b: Alerts query fact trends
