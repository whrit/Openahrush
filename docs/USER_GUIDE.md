# User Guide

Welcome to Openahrush! This guide will help you get started with the platform, set up integrations, run audits, and generate reports.

## Table of Contents

- [Getting Started](#getting-started)
- [Project Setup](#project-setup)
- [Integration Setup](#integration-setup)
  - [Google Search Console](#google-search-console)
  - [Google Analytics 4](#google-analytics-4)
  - [Bing Webmaster Tools](#bing-webmaster-tools)
- [Site Audits](#site-audits)
- [Backlink Analysis](#backlink-analysis)
- [Exports and Reports](#exports-and-reports)
- [Webhooks](#webhooks)
- [Best Practices](#best-practices)

---

## Getting Started

### Creating an Account

1. Navigate to your Openahrush instance
2. Click "Register" or `POST /auth/register`
3. Provide your email and password
4. Verify your account (if email verification is enabled)

**API Example:**

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "password": "SecureP@ssw0rd",
    "name": "Your Name"
  }'
```

### Logging In

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "password": "SecureP@ssw0rd"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Save the `access_token` for subsequent API requests.

---

## Project Setup

### Creating Your First Project

A **Project** is the top-level container for your SEO work. Each project can have:
- Multiple sites (primary site + related properties)
- Competitor domains
- Integration mappings
- Custom settings

**Create a project:**

```bash
curl -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Website SEO"
  }'
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My Website SEO",
  "owner_id": "...",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Adding a Site

```bash
curl -X POST http://localhost:8000/projects/550e8400-e29b-41d4-a716-446655440000/sites \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "base_url": "https://example.com"
  }'
```

### Adding Competitors

Track competitor domains for backlink overlap and competitive analysis:

```bash
curl -X POST http://localhost:8000/projects/550e8400-e29b-41d4-a716-446655440000/competitors \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "competitor.com"
  }'
```

### Configuring Project Settings

Configure crawl behavior, budgets, and schedules:

```bash
curl -X PUT http://localhost:8000/projects/550e8400-e29b-41d4-a716-446655440000/settings \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "seed_url": "https://example.com",
    "include_subdomains": true,
    "max_pages": 10000,
    "max_depth": 5,
    "js_render_mode": "hybrid",
    "audit_frequency": "weekly",
    "exclude_regexes": ["/admin/.*", "/wp-admin/.*"]
  }'
```

**Key Settings:**

| Setting | Description | Default |
|---------|-------------|---------|
| `seed_url` | Starting URL for crawls | Required |
| `max_pages` | Maximum pages to crawl | 10,000 |
| `max_depth` | Maximum crawl depth | 5 |
| `js_render_mode` | `hybrid`, `off`, or `js_only` | `hybrid` |
| `audit_frequency` | `daily`, `weekly`, or `off` | `weekly` |
| `exclude_regexes` | URL patterns to skip | `[]` |

---

## Integration Setup

Openahrush integrates with major SEO platforms to pull in first-party data.

### Google Search Console

#### Prerequisites

1. **Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable **Google Search Console API**

2. **OAuth Credentials:**
   - Go to **APIs & Services > Credentials**
   - Create **OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Authorized redirect URI: `https://yourdomain.com/integrations/google/callback`
   - Save Client ID and Client Secret

3. **Configure Openahrush:**
   - Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in environment
   - Restart API service

#### Connecting Google Search Console

1. **Initiate OAuth flow:**

```bash
curl -X POST http://localhost:8000/integrations/google/connect \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...",
  "state": "random-state-token"
}
```

2. **Redirect user to `auth_url`** in browser
3. User authorizes Openahrush to access Google Search Console
4. Google redirects to callback URL
5. Openahrush exchanges code for access token

#### Mapping Properties

After connecting, list available properties:

```bash
curl -X GET "http://localhost:8000/integrations/google/properties?account_id=ACCOUNT_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "items": [
    {
      "property_id": "sc-domain:example.com",
      "property_name": "example.com",
      "property_type": "DOMAIN",
      "provider": "google_search_console"
    }
  ]
}
```

Map property to your project site:

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/integrations/map \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACCOUNT_ID",
    "property_id": "sc-domain:example.com",
    "site_id": "SITE_ID"
  }'
```

#### Data Sync

Openahrush automatically syncs:
- **Query performance:** Queries, impressions, clicks, position
- **Page performance:** URL-level metrics
- **Sitemaps** (if available)
- **Manual actions** (if any)

**Manual sync trigger:**

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/integrations/sync \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Sync frequency:** Daily by default (configurable in project settings)

---

### Google Analytics 4

#### Prerequisites

1. **Enable Google Analytics Data API:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable **Google Analytics Data API** for your project

2. **Grant access:**
   - Ensure the Google account has **Viewer** or higher role on GA4 property

#### Connecting GA4

Same OAuth flow as Google Search Console (shared Google account):

1. Connect Google account (if not already connected)
2. List GA4 properties:

```bash
curl -X GET "http://localhost:8000/integrations/google/properties?account_id=ACCOUNT_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

3. Map GA4 property to site:

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/integrations/map \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACCOUNT_ID",
    "property_id": "properties/123456789",
    "site_id": "SITE_ID"
  }'
```

#### Data Sync

Openahrush syncs:
- **Page metrics:** Sessions, users, engagement
- **Conversions:** Goal completions, revenue
- **Traffic sources:** Source/medium attribution

**Data enrichment:**
- Issues are scored by **impact** using GA4 session data
- Pages with high traffic but issues are prioritized

---

### Bing Webmaster Tools

#### Prerequisites

1. **Bing Webmaster Tools account:**
   - Sign up at [Bing Webmaster Tools](https://www.bing.com/webmasters)
   - Verify your website

2. **API key:**
   - Go to **Settings > API Access**
   - Generate API key

3. **Configure Openahrush:**
   - Set `BING_API_KEY` in environment
   - Restart API service

#### Connecting Bing Webmaster Tools

```bash
curl -X POST http://localhost:8000/integrations/bing/connect \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "YOUR_BING_API_KEY"
  }'
```

#### Data Sync

- **Query performance:** Similar to GSC
- **Crawl stats:** Crawl errors, blocked URLs
- **Backlinks:** Bing's link data (where available)

---

## Site Audits

### Triggering a Crawl

Start a site audit by triggering a crawl:

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/crawls \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "SITE_ID"
  }'
```

**Response:**
```json
{
  "crawl_run_id": "dd0e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Crawl Process

1. **Queued:** Crawl added to job queue
2. **Running:** Crawler fetches pages according to settings
3. **Hybrid rendering:** Pages identified as JS-heavy are rendered with Playwright
4. **Analysis:** Rules engine evaluates pages for issues
5. **Completed:** Results available

**Check crawl status:**

```bash
curl -X GET http://localhost:8000/crawls/dd0e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Understanding Issues

Issues are categorized by **severity:**

| Severity | Description | Examples |
|----------|-------------|----------|
| **Critical** | Blocks indexing or causes errors | 5xx errors, redirect loops |
| **High** | Significantly impacts SEO | Missing titles, 4xx pages, canonical issues |
| **Medium** | Best practice violations | Title too long, missing meta description |
| **Low** | Minor optimizations | Thin content, orphan pages |

**List issues:**

```bash
curl -X GET http://localhost:8000/projects/PROJECT_ID/issues?severity=critical \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "items": [
    {
      "id": "ee0e8400-e29b-41d4-a716-446655440000",
      "issue_type_code": "missing_title",
      "severity": "high",
      "page_url": "https://example.com/page1",
      "impact_score": 8.5,
      "evidence": {
        "expected": "Title tag present",
        "found": null
      },
      "created_at": "2025-01-15T11:00:00Z"
    }
  ],
  "total": 23
}
```

### Impact Scoring

Issues are scored based on:
- **Severity:** Critical (10), High (7), Medium (4), Low (2)
- **Confidence:** How certain we are this is an issue (0-1)
- **Traffic weight:** Based on impressions/sessions from integrations

**Formula:**
```
impact_score = severity × confidence × traffic_weight
```

**Example:**
- Severity: High (7)
- Confidence: 1.0 (certain)
- Traffic: 1500 impressions/month (weight = 1.2)
- **Impact score:** 7 × 1.0 × 1.2 = 8.4

This prioritizes fixing issues on high-traffic pages first.

### Comparing Crawls (Diffs)

See what changed between crawls:

```bash
curl -X GET http://localhost:8000/projects/PROJECT_ID/issues/diffs \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "base_crawl_id": "...",
  "compare_crawl_id": "...",
  "new_issues": 12,
  "resolved_issues": 8,
  "unchanged_issues": 145,
  "new_issues_list": [ /* issue objects */ ],
  "resolved_issues_list": [ /* issue objects */ ]
}
```

---

## Backlink Analysis

Openahrush provides backlink data from multiple sources:
- **Common Crawl:** Free, internet-wide link index
- **Provider links:** From GSC, BWT (where available)
- **CSV imports:** Upload your own link data
- **Crawl-discovered:** Internal links found during audits

### Exploring Backlinks for a Domain

#### Referring Domains

```bash
curl -X GET http://localhost:8000/links/domain/example.com/refdomains \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "domain": "example.com",
  "total_refdomains": 1250,
  "items": [
    {
      "source_domain": "news.example.org",
      "backlink_count": 45,
      "first_seen": "2024-12-01T00:00:00Z",
      "last_seen": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### Individual Backlinks

```bash
curl -X GET http://localhost:8000/links/domain/example.com/backlinks \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Anchor Text Distribution

```bash
curl -X GET http://localhost:8000/links/domain/example.com/anchors \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Competitive Analysis

#### Link Overlap

Find domains linking to both you and competitors:

```bash
curl -X GET "http://localhost:8000/links/domain/example.com/overlap?competitors=competitor1.com,competitor2.com" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Link Gap (Intersect)

Find domains linking to competitors but NOT to you (link building opportunities):

```bash
curl -X GET "http://localhost:8000/links/domain/example.com/intersect?competitors=competitor1.com,competitor2.com" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "domain": "example.com",
  "competitors": ["competitor1.com", "competitor2.com"],
  "gap_refdomains": [
    {
      "source_domain": "opportunity-site.com",
      "links_to_competitors": ["competitor1.com", "competitor2.com"],
      "backlink_count": 12
    }
  ]
}
```

Use this data for **link building outreach.**

### New and Lost Backlinks

Track changes between Common Crawl snapshots:

```bash
curl -X GET "http://localhost:8000/links/domain/example.com/new-lost?snapshot_a=CC-MAIN-2024-40&snapshot_b=CC-MAIN-2025-01" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Importing Backlinks

Upload your own link data (e.g., from other tools):

```bash
# Prepare CSV file with columns: source_url, target_url, anchor
# Example: backlinks.csv
# source_url,target_url,anchor
# https://blog.com/article,https://example.com/page1,great resource

curl -X POST http://localhost:8000/projects/PROJECT_ID/backlinks/import \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@backlinks.csv"
```

---

## Exports and Reports

### Generating Exports

Export issues, pages, or backlinks to CSV, JSON, or PDF:

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/exports \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "export_type": "pdf",
    "content_type": "issues",
    "filters": {
      "severity": ["critical", "high"]
    }
  }'
```

**Export types:**
- `csv` - Comma-separated values
- `json` - JSON format
- `pdf` - PDF report

**Content types:**
- `issues` - Issue list
- `pages` - Crawled pages
- `backlinks` - Backlink data
- `performance` - Search performance metrics

**Response:**
```json
{
  "export_id": "140e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Checking Export Status

```bash
curl -X GET http://localhost:8000/projects/PROJECT_ID/exports/140e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "id": "140e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "download_url": "https://storage.example.com/exports/report.pdf",
  "file_size_bytes": 2458624,
  "expires_at": "2025-01-22T10:31:00Z"
}
```

### Downloading Export

```bash
curl -L -o report.pdf "DOWNLOAD_URL"
```

### Scheduling Exports

Set up recurring exports (weekly reports, monthly summaries):

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/exports/schedules \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "export_type": "pdf",
    "content_type": "issues",
    "frequency": "weekly",
    "day_of_week": 1,
    "hour": 9,
    "enabled": true
  }'
```

**Frequencies:**
- `daily` - Every day at specified hour
- `weekly` - Every week on specified day
- `monthly` - First day of month at specified hour

**Exports are generated automatically and available via webhook or API.**

---

## Webhooks

Webhooks allow your application to receive real-time notifications when events occur.

### Setting Up Webhooks

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/webhooks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhooks/openahrush",
    "secret": "your-webhook-secret",
    "events": ["crawl.completed", "alert.fired", "export.completed"],
    "enabled": true
  }'
```

### Available Events

| Event | Description |
|-------|-------------|
| `crawl.completed` | Site audit crawl finished |
| `alert.fired` | Alert threshold triggered |
| `integration.sync_failed` | Integration sync error |
| `export.completed` | Export generation finished |
| `commoncrawl.ingest_completed` | Common Crawl ingestion complete |

### Webhook Payload

When an event occurs, Openahrush sends HTTP POST to your webhook URL:

```json
{
  "event_id": "170e8400-e29b-41d4-a716-446655440000",
  "event_type": "crawl.completed",
  "occurred_at": "2025-01-15T11:45:00Z",
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "delivery_id": "180e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "crawl_run_id": "dd0e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "pages_crawled": 1247,
    "issues_found": 156
  }
}
```

### Verifying Webhook Signatures

All webhook deliveries include `X-Openahrush-Signature` header:

**Python example:**

```python
import hmac
import hashlib

def verify_webhook(request_body, signature_header, webhook_secret):
    expected = hmac.new(
        webhook_secret.encode(),
        request_body.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)

# Usage
if verify_webhook(request.body, request.headers['X-Openahrush-Signature'], 'your-webhook-secret'):
    # Process webhook
    pass
else:
    # Reject invalid signature
    return 401
```

### Webhook Retries

- **Retry attempts:** 5
- **Backoff:** Exponential (1s, 2s, 4s, 8s, 16s)
- **Timeout:** 30 seconds per request
- **Success:** HTTP 2xx response

If all retries fail, webhook delivery is marked as failed. Check webhook logs in the API.

---

## Best Practices

### Project Organization

- **One project per website/domain**
- Add all relevant competitors for link analysis
- Configure settings before first crawl
- Use meaningful project names

### Crawl Configuration

- **Start conservative:** Begin with `max_pages: 1000` for testing
- **Exclude admin areas:** Add `/wp-admin/`, `/admin/` to `exclude_regexes`
- **Use hybrid mode:** Detects JS-heavy pages automatically
- **Respect robots.txt:** Keep `respect_robots: true` in production

### Integration Best Practices

- **Map all properties:** Connect GSC + GA4 for complete data
- **Daily syncs:** Keep default `integration_sync_frequency: daily`
- **Monitor sync failures:** Set up alerts for `integration.sync_failed`

### Issue Prioritization

1. **Fix critical issues first:** 5xx errors, redirect loops
2. **Focus on high-traffic pages:** Use impact scores
3. **Verify with integrations:** Check if pages actually get traffic
4. **Batch similar issues:** Fix all "missing titles" at once

### Backlink Strategy

1. **Analyze gap domains:** Find link building opportunities via `/intersect`
2. **Monitor new/lost:** Track Common Crawl snapshots monthly
3. **Import external data:** Combine with other backlink tools
4. **Check anchor distribution:** Ensure natural anchor text variety

### Reporting

- **Schedule weekly PDFs:** Stakeholder summary reports
- **Export CSV for deep dives:** Import into spreadsheets for analysis
- **Use webhooks for alerts:** Real-time notifications to Slack/Discord

### Performance

- **Limit concurrent crawls:** Don't trigger multiple crawls simultaneously
- **Use pagination:** Don't fetch all issues at once (use `page_size: 50`)
- **Cache expensive queries:** Store backlink data locally if querying frequently

---

## Common Workflows

### Weekly SEO Routine

1. **Monday morning:** Review scheduled PDF report (email/webhook)
2. **Check new issues:** Compare with last week's crawl
3. **Prioritize fixes:** Sort by impact score
4. **Track progress:** Monitor resolved issues count
5. **Friday:** Trigger new crawl to verify fixes

### Pre-Launch Site Audit

1. Create project for new site
2. Configure settings (exclude staging patterns)
3. Run full audit
4. Fix all critical and high-severity issues
5. Re-crawl to verify
6. Export final report

### Competitor Link Analysis

1. Add competitor domains to project
2. Run `/overlap` to find shared link sources
3. Run `/intersect` to find gap opportunities
4. Export results to CSV
5. Prioritize outreach based on domain authority/relevance

### Integration Troubleshooting

1. Check integration account status: `GET /integrations/accounts`
2. Verify last sync time
3. Trigger manual sync: `POST /projects/{id}/integrations/sync`
4. Check logs for errors
5. Re-authorize if needed

---

## FAQ

**Q: How often should I run site audits?**

A: Weekly is recommended for active sites. Monthly for static sites. Configure `audit_frequency` in project settings for automatic scheduling.

**Q: What's the difference between hybrid and JS-only rendering?**

A: Hybrid renders only pages that look JS-dependent (based on heuristics), saving resources. JS-only renders all pages, which is slower but catches all dynamic content.

**Q: How do I stop a running crawl?**

A: Currently, crawls run to completion. Set `max_pages` limit to control duration. Cancellation feature coming in future release.

**Q: Can I export historical data?**

A: Yes, exports include data from the selected crawl run. Use diffs to compare historical crawls.

**Q: How is Common Crawl data updated?**

A: Openahrush ingests Common Crawl snapshots (published monthly). Contact your administrator to trigger ingestion of new snapshots.

**Q: What happens if integration sync fails?**

A: Openahrush retries automatically. If all retries fail, a webhook event is fired (if configured). Check integration account status and re-authorize if needed.

---

## Getting Help

- **Documentation:** [Full documentation](/Users/beckett/Projects/Openahrush/docs/)
- **API Reference:** [API_REFERENCE.md](/Users/beckett/Projects/Openahrush/docs/API_REFERENCE.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](/Users/beckett/Projects/Openahrush/docs/TROUBLESHOOTING.md)
- **GitHub Issues:** https://github.com/yourusername/openahrush/issues
- **Community:** Discord/Slack channel
