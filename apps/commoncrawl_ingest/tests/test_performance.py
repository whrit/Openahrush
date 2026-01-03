"""TDD tests for Common Crawl ingestion performance optimizations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest
from semrush_commoncrawl.storage.base import Edge


@dataclass
class MockBatchStorage:
    edges: list[Edge] = field(default_factory=list)
    insert_calls: list[int] = field(default_factory=list)

    async def insert_edges(self, edges: list[Edge]) -> int:
        self.edges.extend(edges)
        self.insert_calls.append(len(edges))
        return len(edges)


class MockRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._data[key] = value

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                deleted += 1
            if key in self._sets:
                del self._sets[key]
                deleted += 1
        return deleted

    async def sadd(self, key: str, *members: str) -> int:
        if key not in self._sets:
            self._sets[key] = set()
        added = 0
        for member in members:
            if member not in self._sets[key]:
                self._sets[key].add(member)
                added += 1
        return added

    async def sismember(self, key: str, member: str) -> bool:
        return key in self._sets and member in self._sets[key]

    async def smembers(self, key: str) -> set[str]:
        return self._sets.get(key, set())


def create_sample_edge(source_url: str = "https://source.com/page") -> Edge:
    return Edge(
        source_url=source_url,
        source_domain="source.com",
        target_url="https://target.com/page",
        target_domain="target.com",
        anchor="Link",
        snapshot_id="CC-MAIN-2024-10",
    )


def create_mock_wat_content(num_links: int = 3) -> bytes:
    links = [
        {"url": f"https://target{i}.com/page", "path": "A@/href", "text": f"Link {i}"}
        for i in range(num_links)
    ]
    record = {
        "Envelope": {
            "WARC-Header-Metadata": {
                "WARC-Type": "metadata",
                "WARC-Target-URI": "https://source.com/page",
            },
            "Payload-Metadata": {"HTTP-Response-Metadata": {"HTML-Metadata": {"Links": links}}},
        }
    }
    json_data = json.dumps(record)
    crlf = chr(13) + chr(10)
    header = (
        "WARC/1.0"
        + crlf
        + "WARC-Type: metadata"
        + crlf
        + "Content-Length: "
        + str(len(json_data))
        + crlf
        + crlf
    )
    return (header + json_data + crlf + crlf).encode()


class TestBatchInserterInit:
    @pytest.mark.asyncio
    async def test_default_batch_size(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        inserter = BatchInserter(storage=MockBatchStorage())
        assert inserter.batch_size == 10000

    @pytest.mark.asyncio
    async def test_initial_buffer_empty(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        inserter = BatchInserter(storage=MockBatchStorage())
        assert inserter.pending_count == 0


class TestBatchInserterAdd:
    @pytest.mark.asyncio
    async def test_add_single_edge(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        inserter = BatchInserter(storage=MockBatchStorage(), batch_size=100)
        await inserter.add(create_sample_edge())
        assert inserter.pending_count == 1

    @pytest.mark.asyncio
    async def test_auto_flush_when_batch_full(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        storage = MockBatchStorage()
        inserter = BatchInserter(storage=storage, batch_size=5)
        for i in range(5):
            await inserter.add(create_sample_edge(f"https://src{i}.com"))
        assert inserter.pending_count == 0
        assert len(storage.edges) == 5


class TestBatchInserterFlush:
    @pytest.mark.asyncio
    async def test_flush_partial_buffer(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        storage = MockBatchStorage()
        inserter = BatchInserter(storage=storage, batch_size=100)
        for i in range(30):
            await inserter.add(create_sample_edge(f"https://src{i}.com"))
        await inserter.flush()
        assert inserter.pending_count == 0
        assert len(storage.edges) == 30


class TestBatchInserterContextManager:
    @pytest.mark.asyncio
    async def test_context_manager_flushes_on_exit(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        storage = MockBatchStorage()
        async with BatchInserter(storage=storage, batch_size=100) as inserter:
            for i in range(30):
                await inserter.add(create_sample_edge(f"https://src{i}.com"))
        assert len(storage.edges) == 30


class TestBatchInserterStats:
    @pytest.mark.asyncio
    async def test_total_inserted_count(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        storage = MockBatchStorage()
        inserter = BatchInserter(storage=storage, batch_size=10)
        for i in range(25):
            await inserter.add(create_sample_edge(f"https://src{i}.com"))
        assert inserter.total_inserted == 20
        await inserter.flush()
        assert inserter.total_inserted == 25


class TestIngestionCheckpoint:
    @pytest.mark.asyncio
    async def test_save_and_get_progress(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        redis = MockRedis()
        checkpoint = IngestionCheckpoint(redis=redis, job_id="test")
        await checkpoint.save_progress(files_processed=10, edges_ingested=5000)
        progress = await checkpoint.get_progress()
        assert progress is not None
        assert progress["files_processed"] == 10

    @pytest.mark.asyncio
    async def test_mark_file_complete(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        checkpoint = IngestionCheckpoint(redis=MockRedis(), job_id="test")
        await checkpoint.mark_file_complete("file1.wat.gz")
        assert await checkpoint.is_file_complete("file1.wat.gz")

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        redis = MockRedis()
        checkpoint = IngestionCheckpoint(redis=redis, job_id="test")
        await checkpoint.save_progress(files_processed=10, edges_ingested=5000)
        await checkpoint.clear()
        assert await checkpoint.get_progress() is None


class TestStreamParseWat:
    @pytest.mark.asyncio
    async def test_parse_yields_edges(self) -> None:
        from semrush_commoncrawl.streaming import stream_parse_wat

        edges = [e async for e in stream_parse_wat(create_mock_wat_content(5))]
        assert len(edges) == 5

    @pytest.mark.asyncio
    async def test_parse_empty(self) -> None:
        from semrush_commoncrawl.streaming import stream_parse_wat

        edges = [e async for e in stream_parse_wat(b"")]
        assert len(edges) == 0


class TestProcessingResult:
    def test_success_result(self) -> None:
        from semrush_commoncrawl.parallel import ProcessingResult

        result = ProcessingResult(path="f.gz", success=True, edges_count=100)
        assert result.success

    def test_failure_result(self) -> None:
        from semrush_commoncrawl.parallel import ProcessingResult

        result = ProcessingResult(path="f.gz", success=False, error="fail")
        assert not result.success


class TestProcessWatFilesParallel:
    @pytest.mark.asyncio
    async def test_parallel_processing(self) -> None:
        from semrush_commoncrawl.parallel import process_wat_files_parallel

        async def dl(p: str) -> bytes:
            return create_mock_wat_content(3)

        results = [r async for r in process_wat_files_parallel(["a.gz", "b.gz"], dl, 2)]
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_handles_errors(self) -> None:
        from semrush_commoncrawl.parallel import process_wat_files_parallel

        async def dl(p: str) -> bytes:
            if "fail" in p:
                raise RuntimeError("fail")
            return create_mock_wat_content(1)

        results = [r async for r in process_wat_files_parallel(["a.gz", "fail.gz"], dl, 2)]
        assert len(results) == 2
        assert sum(1 for r in results if not r.success) == 1


class TestCheckpointPendingFiles:
    @pytest.mark.asyncio
    async def test_get_pending_files_all_pending(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        checkpoint = IngestionCheckpoint(redis=MockRedis(), job_id="test")
        all_files = ["a.gz", "b.gz", "c.gz"]
        pending = await checkpoint.get_pending_files(all_files)
        assert pending == all_files

    @pytest.mark.asyncio
    async def test_get_pending_files_some_complete(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        checkpoint = IngestionCheckpoint(redis=MockRedis(), job_id="test")
        await checkpoint.mark_file_complete("a.gz")
        await checkpoint.mark_file_complete("c.gz")
        pending = await checkpoint.get_pending_files(["a.gz", "b.gz", "c.gz"])
        assert pending == ["b.gz"]

    @pytest.mark.asyncio
    async def test_get_pending_files_all_complete(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        checkpoint = IngestionCheckpoint(redis=MockRedis(), job_id="test")
        for f in ["a.gz", "b.gz"]:
            await checkpoint.mark_file_complete(f)
        pending = await checkpoint.get_pending_files(["a.gz", "b.gz"])
        assert pending == []


class TestCheckpointCompletedCount:
    @pytest.mark.asyncio
    async def test_completed_count_zero(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        checkpoint = IngestionCheckpoint(redis=MockRedis(), job_id="test")
        count = await checkpoint.get_completed_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_completed_count_after_marking(self) -> None:
        from semrush_commoncrawl.checkpoint import IngestionCheckpoint

        checkpoint = IngestionCheckpoint(redis=MockRedis(), job_id="test")
        await checkpoint.mark_file_complete("a.gz")
        await checkpoint.mark_file_complete("b.gz")
        await checkpoint.mark_file_complete("c.gz")
        count = await checkpoint.get_completed_count()
        assert count == 3


class TestStreamParseWatBatched:
    @pytest.mark.asyncio
    async def test_batched_parsing(self) -> None:
        from semrush_commoncrawl.streaming import stream_parse_wat_batched

        batches = [b async for b in stream_parse_wat_batched(create_mock_wat_content(10), batch_size=3)]
        # 10 edges with batch_size=3 = 4 batches (3+3+3+1)
        assert len(batches) == 4
        assert len(batches[0]) == 3
        assert len(batches[-1]) == 1

    @pytest.mark.asyncio
    async def test_batched_empty_content(self) -> None:
        from semrush_commoncrawl.streaming import stream_parse_wat_batched

        batches = [b async for b in stream_parse_wat_batched(b"", batch_size=5)]
        assert len(batches) == 0


class TestBatchInserterAddBatch:
    @pytest.mark.asyncio
    async def test_add_batch_triggers_flush(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        storage = MockBatchStorage()
        inserter = BatchInserter(storage=storage, batch_size=5)
        edges = [create_sample_edge(f"https://src{i}.com") for i in range(12)]
        await inserter.add_batch(edges)
        # 12 edges with batch_size=5: 2 full batches (5+5) + 2 pending
        assert inserter.pending_count == 2
        assert len(storage.insert_calls) == 2
        assert sum(storage.insert_calls) == 10


class TestBatchInserterGetStats:
    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        from semrush_commoncrawl.batch_inserter import BatchInserter

        storage = MockBatchStorage()
        inserter = BatchInserter(storage=storage, batch_size=10)
        for i in range(15):
            await inserter.add(create_sample_edge(f"https://src{i}.com"))
        stats = inserter.get_stats()
        assert stats["total_inserted"] == 10
        assert stats["pending_count"] == 5
        assert stats["flush_count"] == 1
        assert stats["batch_size"] == 10


class TestOptimizedIngestSpec:
    def test_valid_sample_rate(self) -> None:
        from semrush_commoncrawl.optimized_orchestrator import OptimizedIngestSpec

        spec = OptimizedIngestSpec(sample_rate=0.5)
        assert spec.sample_rate == 0.5

    def test_invalid_sample_rate_raises(self) -> None:
        from semrush_commoncrawl.optimized_orchestrator import OptimizedIngestSpec

        with pytest.raises(ValueError):
            OptimizedIngestSpec(sample_rate=1.5)


class TestOptimizedIngestionResult:
    def test_success_with_no_errors(self) -> None:
        from semrush_commoncrawl.optimized_orchestrator import OptimizedIngestionResult

        result = OptimizedIngestionResult(
            edges_ingested=1000,
            files_processed=10,
            files_skipped=5,
        )
        assert result.success

    def test_failure_with_errors(self) -> None:
        from semrush_commoncrawl.optimized_orchestrator import OptimizedIngestionResult

        result = OptimizedIngestionResult(
            edges_ingested=500,
            files_processed=5,
            errors=["Download error"],
        )
        assert not result.success


class TestOptimizedIngestionSettings:
    def test_default_batch_size_10k(self) -> None:
        from semrush_commoncrawl.optimized_orchestrator import OptimizedIngestionSettings

        settings = OptimizedIngestionSettings()
        assert settings.batch_size == 10000

    def test_default_concurrency(self) -> None:
        from semrush_commoncrawl.optimized_orchestrator import OptimizedIngestionSettings

        settings = OptimizedIngestionSettings()
        assert settings.concurrency == 8


class TestClickHouseAsyncConfig:
    def test_default_async_insert_enabled(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import ClickHouseAsyncConfig

        config = ClickHouseAsyncConfig()
        assert config.async_insert is True

    def test_default_batch_size_50k(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import ClickHouseAsyncConfig

        config = ClickHouseAsyncConfig()
        assert config.insert_batch_size == 50000


class TestClickHouseAsyncStorage:
    @pytest.mark.asyncio
    async def test_insert_edges_with_mock_client(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import (
            ClickHouseAsyncConfig,
            ClickHouseAsyncStorage,
            MockClickHouseClient,
        )

        config = ClickHouseAsyncConfig(insert_batch_size=100)
        storage = ClickHouseAsyncStorage(config=config)
        storage.client = MockClickHouseClient()

        edges = [create_sample_edge(f"https://src{i}.com") for i in range(50)]
        count = await storage.insert_edges(edges)

        assert count == 50
        assert storage.stats.total_rows == 50
        assert storage.stats.total_batches == 1

    @pytest.mark.asyncio
    async def test_insert_edges_chunks_large_batches(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import (
            ClickHouseAsyncConfig,
            ClickHouseAsyncStorage,
            MockClickHouseClient,
        )

        config = ClickHouseAsyncConfig(insert_batch_size=10)
        storage = ClickHouseAsyncStorage(config=config)
        storage.client = MockClickHouseClient()

        edges = [create_sample_edge(f"https://src{i}.com") for i in range(25)]
        count = await storage.insert_edges(edges)

        assert count == 25
        # 25 edges with batch_size=10 = 3 batches (10+10+5)
        assert storage.stats.total_batches == 3

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import (
            ClickHouseAsyncConfig,
            ClickHouseAsyncStorage,
            MockClickHouseClient,
        )

        config = ClickHouseAsyncConfig(insert_batch_size=100)
        storage = ClickHouseAsyncStorage(config=config)
        storage.client = MockClickHouseClient()

        edges = [create_sample_edge(f"https://src{i}.com") for i in range(10)]
        await storage.insert_edges(edges)

        stats = storage.get_stats()
        assert stats["total_rows"] == 10
        assert stats["total_batches"] == 1
        assert stats["failed_batches"] == 0

    @pytest.mark.asyncio
    async def test_insert_empty_edges_returns_zero(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import (
            ClickHouseAsyncConfig,
            ClickHouseAsyncStorage,
            MockClickHouseClient,
        )

        storage = ClickHouseAsyncStorage(config=ClickHouseAsyncConfig())
        storage.client = MockClickHouseClient()

        count = await storage.insert_edges([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_insert_without_client_raises(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import (
            ClickHouseAsyncConfig,
            ClickHouseAsyncStorage,
        )

        storage = ClickHouseAsyncStorage(config=ClickHouseAsyncConfig())

        with pytest.raises(RuntimeError, match="not connected"):
            await storage.insert_edges([create_sample_edge()])


class TestMockClickHouseClient:
    @pytest.mark.asyncio
    async def test_execute_tracks_queries(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import MockClickHouseClient

        client = MockClickHouseClient()
        await client.execute("SELECT 1", None)
        await client.execute("INSERT INTO test VALUES", [(1, 2), (3, 4)])

        assert len(client.executed_queries) == 2
        assert client.row_count == 2

    @pytest.mark.asyncio
    async def test_count_query_returns_row_count(self) -> None:
        from semrush_commoncrawl.storage.clickhouse_async import MockClickHouseClient

        client = MockClickHouseClient()
        await client.execute("INSERT", [(1,), (2,), (3,)])
        result = await client.execute("SELECT count() FROM table", None)

        assert result == [[3]]
