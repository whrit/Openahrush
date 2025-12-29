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
