"""
Load testing infrastructure for Openahrush API.

This package provides Locust-based load testing scenarios for validating
API performance under concurrent load. Target metrics:
- 100 concurrent users
- p50 latency < 50ms
- p95 latency < 200ms
- p99 latency < 500ms
"""
