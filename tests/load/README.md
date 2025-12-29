# Load Testing

This directory contains load testing infrastructure for the Openahrush API using [Locust](https://locust.io/).

## Prerequisites

```bash
# Install dependencies (locust is included in dev dependencies)
uv sync

# Or install locust directly
pip install locust
```

## Performance Targets

| Metric | Target | Description |
|--------|--------|-------------|
| Concurrent users | 100+ | System should handle 100 simultaneous users |
| p50 latency | < 50ms | Median response time |
| p95 latency | < 200ms | 95th percentile response time |
| p99 latency | < 500ms | 99th percentile response time |
| Error rate | < 1% | Request failure rate |

## Running Load Tests

### Start the API Server

```bash
# Start the development environment
scripts/dev.sh up

# Or run the API directly
uv run --package semrush-api uvicorn semrush_api.main:app --reload --port 8000
```

### Main Load Test (Web UI)

```bash
# Start Locust with web interface
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Open http://localhost:8089 in your browser
# Configure users and spawn rate, then start the test
```

### Headless Mode (CI/CD)

```bash
# Run with specific user count and duration
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless

# With HTML report
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless \
    --html=reports/load_test_report.html

# With CSV output for analysis
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless \
    --csv=reports/load_test_results
```

### Scenario-Specific Tests

```bash
# Authentication load test
locust -f tests/load/scenarios/auth_load.py --host=http://localhost:8000

# Read API load test
locust -f tests/load/scenarios/api_read_load.py --host=http://localhost:8000

# Write API / Crawl trigger load test
locust -f tests/load/scenarios/crawl_load.py --host=http://localhost:8000
```

## Test Scenarios

### Main Load Test (`locustfile.py`)

The primary load test simulates realistic API usage with:
- User registration and login
- Project CRUD operations
- Issue and alert queries
- Backlink analysis requests
- Health checks

Task weights reflect expected real-world usage patterns.

### Authentication Load (`scenarios/auth_load.py`)

Focused testing of authentication endpoints:
- Registration throughput
- Login/logout cycles
- Token validation
- Invalid credential handling
- Authentication spikes

### Read API Load (`scenarios/api_read_load.py`)

Heavy read operation testing:
- Project listing (paginated)
- Project details
- Issues retrieval
- Alerts and rules
- Settings access
- Backlinks overview

### Write API Load (`scenarios/crawl_load.py`)

Write operation testing:
- Project creation/update/deletion
- Site management
- Competitor management
- Alert rule creation
- Settings updates

## Configuration

### Environment Variables

```bash
# Test user credentials
export LOAD_TEST_EMAIL="loadtest@example.com"
export LOAD_TEST_PASSWORD="loadtest123!"
```

### Locust Configuration

Create a `locust.conf` file for persistent settings:

```ini
# locust.conf
host = http://localhost:8000
users = 100
spawn-rate = 10
run-time = 5m
headless = false
html = reports/load_test_report.html
```

Then run with:
```bash
locust -f tests/load/locustfile.py
```

## Interpreting Results

### Web UI Metrics

- **RPS**: Requests per second - overall throughput
- **Response Times**: p50, p95, p99, min, max
- **Failures**: Count and percentage of failed requests
- **Charts**: Real-time visualization of performance

### CSV Output Files

When using `--csv=prefix`, three files are generated:
- `prefix_stats.csv`: Per-request statistics
- `prefix_stats_history.csv`: Time-series data
- `prefix_failures.csv`: Failure details

### Example Analysis

```python
import pandas as pd

# Load stats
stats = pd.read_csv('reports/load_test_results_stats.csv')

# Check p95 latencies
p95_violations = stats[stats['95%'] > 200]
if len(p95_violations) > 0:
    print("Endpoints exceeding p95 target:")
    print(p95_violations[['Name', '95%']])
```

## Distributed Testing

For higher load, run Locust in distributed mode:

```bash
# Start master
locust -f tests/load/locustfile.py --master --host=http://localhost:8000

# Start workers (run on multiple machines)
locust -f tests/load/locustfile.py --worker --master-host=<master-ip>
```

## CI/CD Integration

### GitHub Actions Example

```yaml
load-test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - name: Start API
      run: |
        docker-compose up -d
        sleep 10

    - name: Run Load Tests
      run: |
        pip install locust
        locust -f tests/load/locustfile.py \
          --host=http://localhost:8000 \
          --users=50 \
          --spawn-rate=5 \
          --run-time=2m \
          --headless \
          --html=load_test_report.html \
          --exit-code-on-error 1

    - name: Upload Report
      uses: actions/upload-artifact@v4
      with:
        name: load-test-report
        path: load_test_report.html
```

### Performance Gates

Use the `--exit-code-on-error` flag to fail CI if:
- Any requests fail
- Error rate exceeds threshold

Custom exit codes can be implemented using Locust's event hooks.

## Troubleshooting

### High Failure Rate

1. Check if the API server is running
2. Verify database connectivity
3. Check for rate limiting
4. Review server logs for errors

### Inconsistent Results

1. Ensure consistent test environment
2. Warm up the API before testing
3. Run multiple test iterations
4. Check for external factors (network, other processes)

### Memory Issues

For long-running tests:
```bash
# Increase spawn rate to reduce memory
locust -f tests/load/locustfile.py \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=20 \
    --run-time=30m \
    --headless
```

## Best Practices

1. **Baseline First**: Run tests against a known-good configuration to establish baselines
2. **Gradual Ramp-Up**: Use spawn-rate to gradually increase load
3. **Realistic Data**: Ensure test database has representative data volume
4. **Isolated Environment**: Run load tests in isolated environments
5. **Monitor Resources**: Watch CPU, memory, and database metrics during tests
6. **Repeat Tests**: Run multiple iterations for consistent results
7. **Document Changes**: Note configuration changes between test runs
