# Sprint 4: Reports, Exports & Webhooks

**Duration:** 1-2 weeks
**Dependencies:** Sprints 1-3 (Integrations, Crawl, Backlinks)
**Status:** Complete

This sprint implements data export capabilities, PDF report generation, scheduled exports, and event-driven webhook delivery.

---

## Objectives

1. Build CSV/JSON export generation
2. Implement PDF report rendering
3. Create export scheduling system
4. Build webhook configuration and delivery
5. Integrate MinIO for artifact storage
6. Implement at-least-once webhook delivery

---

## Epic 4.1: Export Infrastructure

### Task 4.1.1: Create exports table migration

**Description:** Store export job metadata and status.

**Schema:**
```sql
CREATE TABLE exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    format TEXT NOT NULL,  -- 'csv', 'json', 'pdf'
    resource TEXT NOT NULL,  -- 'issues', 'performance', 'backlinks', 'full_report'
    status TEXT NOT NULL DEFAULT 'queued',
    -- queued, running, completed, failed
    params JSONB DEFAULT '{}',  -- filter/date range params
    artifact_key TEXT,  -- MinIO object key
    file_size_bytes BIGINT,
    download_url TEXT,  -- presigned URL (expires)
    download_expires_at TIMESTAMPTZ,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_exports_project ON exports(project_id, created_at DESC);
CREATE INDEX idx_exports_status ON exports(status);
```

**Acceptance Criteria:**
- [x] Migration creates table
- [x] Status tracks full lifecycle
- [x] Artifact key references MinIO object

**Implementation:** `libs/core/src/semrush_core/models/export.py` (Export model), `migrations/versions/008_exports_infrastructure.py`

---

### Task 4.1.2: Create export_schedules table migration

**Description:** Store scheduled export configurations.

**Schema:**
```sql
CREATE TABLE export_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    format TEXT NOT NULL,
    resource TEXT NOT NULL,
    params JSONB DEFAULT '{}',
    cron_expression TEXT NOT NULL,  -- e.g., '0 9 * * 1' (Monday 9am)
    timezone TEXT DEFAULT 'UTC',
    is_enabled BOOLEAN DEFAULT true,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_export_schedules_next ON export_schedules(next_run_at) WHERE is_enabled;
```

**Acceptance Criteria:**
- [x] Migration creates table
- [x] Cron expression supports standard format
- [x] Timezone support for user-local scheduling

**Implementation:** `libs/core/src/semrush_core/models/export.py` (ExportSchedule model), `migrations/versions/008_exports_infrastructure.py`

---

### Task 4.1.3: Implement MinIO storage utilities

**Description:** Create utilities for MinIO object storage.

**Acceptance Criteria:**
- [x] `libs/core/src/semrush_core/storage/minio.py` created
- [x] Async client initialization
- [x] `upload_file(bucket, key, data) -> str` function
- [x] `generate_presigned_url(bucket, key, expires_in) -> str` function
- [x] `delete_file(bucket, key)` function
- [x] Bucket creation on startup if missing

**Implementation:** `libs/core/src/semrush_core/storage/minio.py` (MinIOStorage class with upload, presigned_url, delete, get, exists, list methods)

**Implementation:**
```python
from minio import Minio
from datetime import timedelta

class MinIOStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        self.client = Minio(endpoint, access_key, secret_key, secure=False)
        self.bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(
            self.bucket, key, io.BytesIO(data), len(data),
            content_type=content_type
        )
        return f"s3://{self.bucket}/{key}"

    def presigned_url(self, key: str, expires_hours: int = 24) -> str:
        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(hours=expires_hours)
        )
```

---

## Epic 4.2: CSV/JSON Exports

### Task 4.2.1: Implement export job queue

**Description:** Create queue infrastructure for export jobs.

**Acceptance Criteria:**
- [x] Redis queue named `exports.generate` created
- [x] Job payload includes export_id
- [x] Worker consumes and processes jobs
- [x] Status updates in exports table
- [x] Timeout for long-running exports

**Implementation:** `apps/api/src/semrush_api/services/export_service.py`, `apps/reports/src/semrush_reports/`

---

### Task 4.2.2: Implement issues CSV export

**Description:** Export audit issues to CSV format.

**Acceptance Criteria:**
- [x] Queries issues for project/crawl
- [x] Columns: url, issue_type, category, severity, impact_score, evidence
- [x] Streaming for large result sets
- [x] UTF-8 encoding with BOM for Excel
- [x] Stores to MinIO and updates export record

**Implementation:** `apps/reports/src/semrush_reports/csv_export.py`

**Export Flow:**
```python
async def export_issues_csv(export_id: UUID):
    export = await get_export(export_id)
    issues = await get_issues(export.project_id, export.params)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["URL", "Issue Type", "Category", "Severity", "Impact Score"])
    for issue in issues:
        writer.writerow([issue.url, issue.type, issue.category, issue.severity, issue.impact])

    key = f"exports/{export.project_id}/{export_id}.csv"
    await storage.upload(key, buffer.getvalue().encode('utf-8-sig'), 'text/csv')

    url = await storage.presigned_url(key, expires_hours=168)
    await update_export(export_id, status='completed', artifact_key=key, download_url=url)
```

---

### Task 4.2.3: Implement performance CSV export

**Description:** Export search performance data to CSV.

**Acceptance Criteria:**
- [x] Queries search_fact_daily for date range
- [x] Columns: date, query, page, impressions, clicks, ctr, position
- [x] Supports aggregation level (daily/weekly)
- [x] Stores to MinIO

**Implementation:** `apps/reports/src/semrush_reports/csv_export.py`

---

### Task 4.2.4: Implement backlinks CSV export

**Description:** Export backlink data to CSV.

**Acceptance Criteria:**
- [x] Exports ref domains or individual backlinks
- [x] Columns: source_url, source_domain, target_url, anchor, first_seen
- [x] Supports domain filter
- [x] Handles large result sets

**Implementation:** `apps/reports/src/semrush_reports/csv_export.py`

---

### Task 4.2.5: Implement JSON export format

**Description:** Export data as JSON for API consumers.

**Acceptance Criteria:**
- [x] All export types support JSON format
- [x] JSON Lines format for streaming (optional)
- [x] Pretty-printed or compact (configurable)
- [x] Same data as CSV exports

**Implementation:** `apps/reports/src/semrush_reports/json_export.py`

---

### Task 4.2.6: Create export trigger endpoint

**Description:** API endpoint to trigger exports.

**Acceptance Criteria:**
- [x] `POST /projects/{id}/exports` creates export job
- [x] Request body specifies format, resource, params
- [x] Returns 202 Accepted with export record
- [x] Status can be polled via export list

**Implementation:** `apps/api/src/semrush_api/routers/exports.py`

**Request Body:**
```json
{
  "format": "csv",
  "resource": "issues",
  "params": {
    "crawl_run_id": "uuid",
    "severity_min": 3
  }
}
```

---

### Task 4.2.7: Create export list endpoint

**Description:** API endpoint to list exports.

**Acceptance Criteria:**
- [x] `GET /projects/{id}/exports` lists exports
- [x] Returns id, format, resource, status, download_url
- [x] Supports pagination
- [x] Includes completed exports with valid download URLs

**Implementation:** `apps/api/src/semrush_api/routers/exports.py`

---

## Epic 4.3: PDF Reports

### Task 4.3.1: Create report templates

**Description:** HTML templates for PDF rendering.

**Acceptance Criteria:**
- [x] `apps/reports/src/semrush_reports/templates/` directory created
- [x] Base template with header/footer/styling
- [x] Audit report template (issues summary, top issues, charts)
- [x] Performance report template (trends, top queries)
- [x] Backlinks report template (ref domains, anchors)
- [x] Full overview template (combines all)

**Implementation:** `apps/reports/src/semrush_reports/templates/` (base.html, audit_report.html, performance_report.html, backlinks_report.html, overview_report.html)

**Template Structure:**
```
templates/
├── base.html
├── audit_report.html
├── performance_report.html
├── backlinks_report.html
└── overview_report.html
```

---

### Task 4.3.2: Implement template data builders

**Description:** Build data context for templates.

**Acceptance Criteria:**
- [x] `apps/reports/src/semrush_reports/builders.py` created
- [x] `build_audit_context(project_id, params)` function
- [x] `build_performance_context(project_id, params)` function
- [x] `build_backlinks_context(project_id, params)` function
- [x] Returns dict suitable for Jinja2 rendering

**Implementation:** `apps/reports/src/semrush_reports/pdf_report.py` (ReportBuilder class)

**Context Example:**
```python
{
    "project": {"name": "Example Site", "domain": "example.com"},
    "generated_at": "2025-01-15T10:00:00Z",
    "date_range": {"start": "2024-12-15", "end": "2025-01-15"},
    "issues_summary": {"critical": 5, "high": 23, "medium": 89, "low": 45},
    "top_issues": [...],
    "charts": {"issues_by_category": {...}}
}
```

---

### Task 4.3.3: Implement PDF renderer (WeasyPrint)

**Description:** Render HTML templates to PDF using WeasyPrint.

**Acceptance Criteria:**
- [x] `apps/reports/src/semrush_reports/renderer.py` created
- [x] Uses WeasyPrint for HTML → PDF conversion
- [x] Supports CSS styling and fonts
- [x] Handles charts (embedded images or SVG)
- [x] Returns PDF bytes

**Implementation:** `apps/reports/src/semrush_reports/pdf_report.py` (PDFRenderer class)

**Implementation:**
```python
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader

class PDFRenderer:
    def __init__(self, template_dir: str):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def render(self, template_name: str, context: dict) -> bytes:
        template = self.env.get_template(template_name)
        html_content = template.render(**context)
        pdf = HTML(string=html_content).write_pdf()
        return pdf
```

---

### Task 4.3.4: Implement chart generation

**Description:** Generate charts for PDF reports.

**Acceptance Criteria:**
- [x] Use matplotlib or altair for chart generation
- [x] Issue distribution pie chart
- [x] Performance trend line chart
- [x] Backlink growth chart
- [x] Charts rendered as PNG or SVG
- [x] Embedded in HTML templates

**Implementation:** `apps/reports/src/semrush_reports/charts.py` (ChartGenerator with pie, line, bar charts)

---

### Task 4.3.5: Implement PDF export job

**Description:** Background job for PDF generation.

**Acceptance Criteria:**
- [x] Triggered when format='pdf'
- [x] Builds context, renders template, generates PDF
- [x] Uploads to MinIO
- [x] Updates export record with download URL
- [x] Handles large reports (pagination if needed)

**Implementation:** `apps/reports/src/semrush_reports/pdf_report.py` (PDFReportService)

---

## Epic 4.4: Export Scheduling

### Task 4.4.1: Implement schedule creation endpoint

**Description:** API endpoint to create export schedules.

**Acceptance Criteria:**
- [x] `POST /projects/{id}/exports/schedules` creates schedule
- [x] Validates cron expression format
- [x] Validates timezone
- [x] Calculates next_run_at from cron
- [x] Returns schedule record

**Implementation:** `apps/api/src/semrush_api/routers/schedules.py`, `apps/api/src/semrush_api/services/schedule_service.py`

**Request Body:**
```json
{
  "format": "pdf",
  "resource": "full_report",
  "cron": "0 9 * * 1",
  "timezone": "America/Los_Angeles",
  "params": {}
}
```

---

### Task 4.4.2: Implement schedule executor

**Description:** Background job to execute due schedules.

**Acceptance Criteria:**
- [x] Runs every minute (or 5 minutes)
- [x] Queries schedules where next_run_at <= now AND is_enabled
- [x] Creates export job for each due schedule
- [x] Updates last_run_at and next_run_at
- [x] Handles timezone correctly

**Implementation:** `apps/api/src/semrush_api/services/schedule_service.py` (get_due_schedules, calculate_next_run)

**Implementation:**
```python
from croniter import croniter

async def execute_due_schedules():
    now = datetime.now(timezone.utc)
    due_schedules = await get_due_schedules(now)

    for schedule in due_schedules:
        # Create export
        export = await create_export(
            project_id=schedule.project_id,
            format=schedule.format,
            resource=schedule.resource,
            params=schedule.params
        )
        await enqueue_export(export.id)

        # Update schedule
        cron = croniter(schedule.cron_expression, now)
        next_run = cron.get_next(datetime)
        await update_schedule(schedule.id, last_run_at=now, next_run_at=next_run)
```

---

### Task 4.4.3: Implement schedule management

**Description:** API endpoints to list/update/delete schedules.

**Acceptance Criteria:**
- [x] `GET /projects/{id}/exports/schedules` lists schedules
- [x] `PATCH /projects/{id}/exports/schedules/{id}` updates schedule
- [x] `DELETE /projects/{id}/exports/schedules/{id}` deletes schedule
- [x] Can enable/disable schedules

**Implementation:** `apps/api/src/semrush_api/routers/schedules.py`

---

## Epic 4.5: Webhooks

### Task 4.5.1: Create webhooks table migration

**Description:** Store webhook configurations.

**Schema:**
```sql
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,  -- for HMAC signature
    events TEXT[] NOT NULL,
    -- ['crawl.completed', 'alert.fired', 'integration.sync_failed', 'export.completed']
    is_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_id UUID NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    -- pending, delivered, failed
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    response_status INTEGER,
    response_body TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_webhooks_project ON webhooks(project_id);
CREATE INDEX idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id);
CREATE INDEX idx_webhook_deliveries_pending ON webhook_deliveries(next_retry_at)
    WHERE status = 'pending' OR status = 'failed';
```

**Acceptance Criteria:**
- [x] Migration creates both tables
- [x] Delivery tracking supports retries
- [x] Indexes support pending delivery queries

**Implementation:** `libs/core/src/semrush_core/models/webhook.py` (WebhookConfig, WebhookDelivery models)

---

### Task 4.5.2: Implement webhook CRUD endpoints

**Description:** API endpoints for webhook management.

**Acceptance Criteria:**
- [x] `POST /projects/{id}/webhooks` creates webhook
- [x] `GET /projects/{id}/webhooks` lists webhooks
- [x] `DELETE /projects/{id}/webhooks/{id}` deletes webhook
- [x] Secret is write-only (never returned in responses)
- [x] Events validated against allowed list

**Implementation:** `apps/api/src/semrush_api/routers/webhooks.py`

**Request Body:**
```json
{
  "url": "https://example.com/webhook",
  "secret": "your-webhook-secret",
  "events": ["crawl.completed", "alert.fired"]
}
```

---

### Task 4.5.3: Implement webhook signature generation

**Description:** Generate HMAC-SHA256 signatures for webhook payloads.

**Acceptance Criteria:**
- [x] `libs/core/src/semrush_core/webhooks/signature.py` created
- [x] Uses HMAC-SHA256 with webhook secret
- [x] Signature sent in `X-Webhook-Signature` header
- [x] Timestamp included to prevent replay attacks

**Implementation:** `libs/core/src/semrush_core/webhooks/signature.py` (generate_signature, verify_signature)

**Implementation:**
```python
import hmac
import hashlib
import time

def generate_signature(payload: str, secret: str, timestamp: int) -> str:
    message = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"
```

---

### Task 4.5.4: Implement webhook delivery queue

**Description:** Queue infrastructure for webhook delivery.

**Acceptance Criteria:**
- [x] Redis queue named `webhooks.deliver` created
- [x] Job includes delivery_id
- [x] Worker processes deliveries
- [x] Retry logic with exponential backoff

**Implementation:** `libs/core/src/semrush_core/webhooks/delivery.py`

---

### Task 4.5.5: Implement webhook delivery worker

**Description:** Worker to deliver webhooks to endpoints.

**Acceptance Criteria:**
- [x] Fetches pending deliveries
- [x] Makes HTTP POST to webhook URL
- [x] Includes headers: Content-Type, X-Webhook-Signature, X-Delivery-ID
- [x] Timeout: 30 seconds
- [x] Success: 2xx status → mark delivered
- [x] Failure: non-2xx or timeout → schedule retry
- [x] Max retries: 5 (configurable)
- [x] Backoff: 1min, 5min, 30min, 2hr, 12hr

**Implementation:** `libs/core/src/semrush_core/webhooks/delivery.py` (deliver_webhook, schedule_retry with RETRY_DELAYS)

**Implementation:**
```python
RETRY_DELAYS = [60, 300, 1800, 7200, 43200]  # seconds

async def deliver_webhook(delivery_id: UUID):
    delivery = await get_delivery(delivery_id)
    webhook = await get_webhook(delivery.webhook_id)

    timestamp = int(time.time())
    payload = json.dumps(delivery.payload)
    signature = generate_signature(payload, webhook.secret, timestamp)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Delivery-ID": str(delivery_id),
        "X-Event-Type": delivery.event_type
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(webhook.url, content=payload, headers=headers)

        if 200 <= response.status_code < 300:
            await mark_delivered(delivery_id, response.status_code)
        else:
            await schedule_retry(delivery_id, delivery.attempts, response.status_code)
    except Exception as e:
        await schedule_retry(delivery_id, delivery.attempts, error=str(e))
```

---

### Task 4.5.6: Implement event → webhook routing

**Description:** Route internal events to matching webhooks.

**Acceptance Criteria:**
- [x] Listens for events: crawl.completed, alert.fired, etc.
- [x] Queries webhooks for project with matching event type
- [x] Creates webhook_delivery records
- [x] Enqueues deliveries

**Implementation:** `libs/core/src/semrush_core/webhooks/delivery.py`, `apps/api/src/semrush_api/routers/webhooks.py`

**Event Router:**
```python
async def route_event(event: Event):
    webhooks = await get_webhooks(
        project_id=event.project_id,
        event_type=event.event_type,
        enabled=True
    )

    for webhook in webhooks:
        delivery = await create_delivery(
            webhook_id=webhook.id,
            event_type=event.event_type,
            event_id=event.event_id,
            payload={
                "event_type": event.event_type,
                "event_id": str(event.event_id),
                "occurred_at": event.occurred_at.isoformat(),
                "project_id": str(event.project_id),
                "payload": event.payload
            }
        )
        await enqueue_delivery(delivery.id)
```

---

### Task 4.5.7: Implement webhook event types

**Description:** Define and emit all webhook event types.

**Event Types:**
- `crawl.completed` - Crawl finished
- `alert.fired` - New alert created
- `integration.sync_failed` - Sync job failed
- `export.completed` - Export ready for download
- `commoncrawl.ingest_completed` - CC ingestion done (optional)

**Payload Examples:**

**crawl.completed:**
```json
{
  "event_type": "crawl.completed",
  "project_id": "uuid",
  "payload": {
    "crawl_run_id": "uuid",
    "status": "completed",
    "pages_crawled": 1500,
    "issues_found": 234
  }
}
```

**alert.fired:**
```json
{
  "event_type": "alert.fired",
  "project_id": "uuid",
  "payload": {
    "alert_id": "uuid",
    "kind": "visibility_drop",
    "severity": "warn",
    "entity_key": "/blog/post-123",
    "details": {"drop_pct": 45}
  }
}
```

**export.completed:**
```json
{
  "event_type": "export.completed",
  "project_id": "uuid",
  "payload": {
    "export_id": "uuid",
    "format": "csv",
    "resource": "issues",
    "download_url": "https://..."
  }
}
```

---

## Verification Checklist

### Export Generation
- [x] CSV export creates valid file
- [x] JSON export creates valid file
- [x] PDF report renders correctly
- [x] Charts embedded in PDF
- [x] Exports stored in MinIO
- [x] Presigned URLs work
- [x] Large exports handle streaming

### Export Scheduling
- [x] Schedule created with cron expression
- [x] Scheduler triggers exports on time
- [x] Timezone conversion correct
- [x] Schedule can be disabled
- [x] Multiple schedules per project work

### Webhooks
- [x] Webhook created successfully
- [x] Events trigger webhook creation
- [x] Delivery makes HTTP POST
- [x] Signature validates correctly
- [x] Failed delivery retries
- [x] Max retries respected
- [x] Backoff delays applied

**Test Results:** 1666 tests passing (including 40 export tests, 30 schedule tests, 36 webhook tests, 142 reports tests)

---

## Notes

### PDF Rendering Options

| Library | Pros | Cons |
|---------|------|------|
| WeasyPrint | Native Python, good CSS | No JS support |
| Playwright PDF | Full browser rendering | Heavier, requires browser |
| wkhtmltopdf | Fast, mature | Requires binary install |

**MVP:** WeasyPrint (pure Python, sufficient for reports)

### Webhook Security

1. **HMAC Signature:** Allows receivers to verify authenticity
2. **Timestamp:** Prevents replay attacks (reject old events)
3. **HTTPS Only:** Only deliver to HTTPS endpoints (optional)
4. **Secret Rotation:** Support webhook secret updates (v2)

### Export Storage Lifecycle

- Exports stored for 7 days by default
- Cleanup job deletes old exports
- Presigned URLs expire in 24-168 hours
- Consider S3 lifecycle policies for auto-cleanup

### Performance Considerations

- Stream large CSV exports (don't buffer in memory)
- Generate PDFs in background workers
- Rate limit export requests per project
- Webhook delivery timeout: 30 seconds
- Webhook backoff prevents thundering herd
