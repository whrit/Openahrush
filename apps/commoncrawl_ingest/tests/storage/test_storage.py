"""
Tests for storage adapter implementations.

Tests cover:
- Edge, RefDomain, Backlink, AnchorCount dataclasses
- PostgresStorage implementation with mocked session
- ClickHouseStorage stub (NotImplementedError)
- EdgeStorage Protocol compliance
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestEdgeDataclass:
    """Tests for the Edge dataclass."""

    def test_edge_creation_with_required_fields(self) -> None:
        """Test creating an Edge with required fields."""
        from semrush_commoncrawl.storage.base import Edge

        edge = Edge(
            snapshot_id="CC-MAIN-2024-10",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
        )

        assert edge.snapshot_id == "CC-MAIN-2024-10"
        assert edge.source_url == "https://example.com/page"
        assert edge.source_domain == "example.com"
        assert edge.target_url == "https://target.com/"
        assert edge.target_domain == "target.com"
        assert edge.anchor is None
        assert edge.rel_flags is None

    def test_edge_creation_with_all_fields(self) -> None:
        """Test creating an Edge with all fields."""
        from semrush_commoncrawl.storage.base import Edge

        edge = Edge(
            snapshot_id="CC-MAIN-2024-10",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            anchor="Click here",
            rel_flags=["nofollow", "ugc"],
        )

        assert edge.anchor == "Click here"
        assert edge.rel_flags == ["nofollow", "ugc"]

    def test_edge_with_empty_anchor(self) -> None:
        """Test Edge with empty anchor string."""
        from semrush_commoncrawl.storage.base import Edge

        edge = Edge(
            snapshot_id="CC-MAIN-2024-10",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            anchor="",
        )

        assert edge.anchor == ""

    def test_edge_with_empty_rel_flags(self) -> None:
        """Test Edge with empty rel_flags list."""
        from semrush_commoncrawl.storage.base import Edge

        edge = Edge(
            snapshot_id="CC-MAIN-2024-10",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            rel_flags=[],
        )

        assert edge.rel_flags == []


class TestRefDomainDataclass:
    """Tests for the RefDomain dataclass."""

    def test_refdomain_creation_with_required_fields(self) -> None:
        """Test creating a RefDomain with required fields."""
        from semrush_commoncrawl.storage.base import RefDomain

        refdomain = RefDomain(
            source_domain="example.com",
            backlink_count=42,
        )

        assert refdomain.source_domain == "example.com"
        assert refdomain.backlink_count == 42
        assert refdomain.first_seen is None
        assert refdomain.last_seen is None

    def test_refdomain_creation_with_all_fields(self) -> None:
        """Test creating a RefDomain with all fields."""
        from semrush_commoncrawl.storage.base import RefDomain

        first_seen = datetime(2024, 1, 1, tzinfo=UTC)
        last_seen = datetime(2024, 10, 15, tzinfo=UTC)

        refdomain = RefDomain(
            source_domain="example.com",
            backlink_count=100,
            first_seen=first_seen,
            last_seen=last_seen,
        )

        assert refdomain.source_domain == "example.com"
        assert refdomain.backlink_count == 100
        assert refdomain.first_seen == first_seen
        assert refdomain.last_seen == last_seen

    def test_refdomain_with_zero_count(self) -> None:
        """Test RefDomain with zero backlink count."""
        from semrush_commoncrawl.storage.base import RefDomain

        refdomain = RefDomain(
            source_domain="example.com",
            backlink_count=0,
        )

        assert refdomain.backlink_count == 0


class TestBacklinkDataclass:
    """Tests for the Backlink dataclass."""

    def test_backlink_creation_with_required_fields(self) -> None:
        """Test creating a Backlink with required fields."""
        from semrush_commoncrawl.storage.base import Backlink

        backlink = Backlink(
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
        )

        assert backlink.source_url == "https://example.com/page"
        assert backlink.source_domain == "example.com"
        assert backlink.target_url == "https://target.com/"
        assert backlink.target_domain == "target.com"
        assert backlink.anchor is None
        assert backlink.rel_flags is None

    def test_backlink_creation_with_all_fields(self) -> None:
        """Test creating a Backlink with all fields."""
        from semrush_commoncrawl.storage.base import Backlink

        backlink = Backlink(
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            anchor="Best SEO tool",
            rel_flags=["sponsored"],
        )

        assert backlink.anchor == "Best SEO tool"
        assert backlink.rel_flags == ["sponsored"]


class TestAnchorCountDataclass:
    """Tests for the AnchorCount dataclass."""

    def test_anchorcount_creation(self) -> None:
        """Test creating an AnchorCount."""
        from semrush_commoncrawl.storage.base import AnchorCount

        anchor_count = AnchorCount(
            anchor="click here",
            count=150,
        )

        assert anchor_count.anchor == "click here"
        assert anchor_count.count == 150

    def test_anchorcount_with_empty_anchor(self) -> None:
        """Test AnchorCount with empty anchor (for image links without alt)."""
        from semrush_commoncrawl.storage.base import AnchorCount

        anchor_count = AnchorCount(
            anchor="",
            count=50,
        )

        assert anchor_count.anchor == ""
        assert anchor_count.count == 50


class TestEdgeStorageProtocol:
    """Tests for EdgeStorage Protocol compliance."""

    def test_postgres_storage_implements_protocol(self) -> None:
        """Test that PostgresStorage implements EdgeStorage protocol."""
        from semrush_commoncrawl.storage.base import EdgeStorage
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_session = AsyncMock()
        storage = PostgresStorage(session=mock_session)

        # Check that it implements the protocol
        assert isinstance(storage, EdgeStorage)

        # Check that the class has all required methods
        assert hasattr(storage, "insert_edges")
        assert hasattr(storage, "query_refdomains")
        assert hasattr(storage, "query_backlinks")
        assert hasattr(storage, "query_anchors")

        # Verify it's callable
        assert callable(storage.insert_edges)
        assert callable(storage.query_refdomains)
        assert callable(storage.query_backlinks)
        assert callable(storage.query_anchors)

    def test_clickhouse_storage_implements_protocol(self) -> None:
        """Test that ClickHouseStorage implements EdgeStorage protocol."""
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = ClickHouseStorage()

        # Check that the class has all required methods
        assert hasattr(storage, "insert_edges")
        assert hasattr(storage, "query_refdomains")
        assert hasattr(storage, "query_backlinks")
        assert hasattr(storage, "query_anchors")


class TestPostgresStorageInsertEdges:
    """Tests for PostgresStorage.insert_edges method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_insert_edges_empty_list(self, mock_session: AsyncMock) -> None:
        """Test inserting an empty list of edges."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        storage = PostgresStorage(session=mock_session)
        result = await storage.insert_edges([])

        assert result == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_insert_edges_single_edge(self, mock_session: AsyncMock) -> None:
        """Test inserting a single edge."""
        from semrush_commoncrawl.storage.base import Edge
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        storage = PostgresStorage(session=mock_session)

        edge = Edge(
            snapshot_id="CC-MAIN-2024-10",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            anchor="Test anchor",
            rel_flags=["nofollow"],
        )

        result = await storage.insert_edges([edge])

        assert result == 1
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_edges_multiple_edges(self, mock_session: AsyncMock) -> None:
        """Test inserting multiple edges."""
        from semrush_commoncrawl.storage.base import Edge
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        storage = PostgresStorage(session=mock_session)

        edges = [
            Edge(
                snapshot_id="CC-MAIN-2024-10",
                source_url=f"https://example{i}.com/page",
                source_domain=f"example{i}.com",
                target_url="https://target.com/",
                target_domain="target.com",
            )
            for i in range(5)
        ]

        result = await storage.insert_edges(edges)

        assert result == 5
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_edges_with_null_optional_fields(self, mock_session: AsyncMock) -> None:
        """Test inserting edges with null optional fields."""
        from semrush_commoncrawl.storage.base import Edge
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        storage = PostgresStorage(session=mock_session)

        edge = Edge(
            snapshot_id="CC-MAIN-2024-10",
            source_url="https://example.com/page",
            source_domain="example.com",
            target_url="https://target.com/",
            target_domain="target.com",
            anchor=None,
            rel_flags=None,
        )

        result = await storage.insert_edges([edge])

        assert result == 1


class TestPostgresStorageQueryRefdomains:
    """Tests for PostgresStorage.query_refdomains method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_query_refdomains_returns_list(self, mock_session: AsyncMock) -> None:
        """Test query_refdomains returns a list of RefDomain."""
        from semrush_commoncrawl.storage.base import RefDomain
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        # Mock query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                source_domain="example1.com",
                backlink_count=100,
                first_seen=datetime(2024, 1, 1, tzinfo=UTC),
                last_seen=datetime(2024, 10, 1, tzinfo=UTC),
            ),
            MagicMock(
                source_domain="example2.com",
                backlink_count=50,
                first_seen=datetime(2024, 2, 1, tzinfo=UTC),
                last_seen=datetime(2024, 9, 1, tzinfo=UTC),
            ),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        result = await storage.query_refdomains("target.com")

        assert len(result) == 2
        assert all(isinstance(r, RefDomain) for r in result)
        assert result[0].source_domain == "example1.com"
        assert result[0].backlink_count == 100
        assert result[1].source_domain == "example2.com"
        assert result[1].backlink_count == 50

    @pytest.mark.asyncio
    async def test_query_refdomains_with_snapshot_id(self, mock_session: AsyncMock) -> None:
        """Test query_refdomains with snapshot_id filter."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        await storage.query_refdomains("target.com", snapshot_id="CC-MAIN-2024-10")

        # Verify execute was called (the actual query is implementation detail)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_refdomains_with_limit(self, mock_session: AsyncMock) -> None:
        """Test query_refdomains with custom limit."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        await storage.query_refdomains("target.com", limit=50)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_refdomains_empty_result(self, mock_session: AsyncMock) -> None:
        """Test query_refdomains with no results."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        result = await storage.query_refdomains("nonexistent.com")

        assert result == []


class TestPostgresStorageQueryBacklinks:
    """Tests for PostgresStorage.query_backlinks method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_query_backlinks_returns_list(self, mock_session: AsyncMock) -> None:
        """Test query_backlinks returns a list of Backlink."""
        from semrush_commoncrawl.storage.base import Backlink
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                source_url="https://example1.com/page",
                source_domain="example1.com",
                target_url="https://target.com/",
                target_domain="target.com",
                anchor="Great site",
                rel_flags=["nofollow"],
            ),
            MagicMock(
                source_url="https://example2.com/article",
                source_domain="example2.com",
                target_url="https://target.com/product",
                target_domain="target.com",
                anchor=None,
                rel_flags=None,
            ),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        result = await storage.query_backlinks("target.com")

        assert len(result) == 2
        assert all(isinstance(r, Backlink) for r in result)
        assert result[0].source_url == "https://example1.com/page"
        assert result[0].anchor == "Great site"
        assert result[1].anchor is None

    @pytest.mark.asyncio
    async def test_query_backlinks_with_pagination(self, mock_session: AsyncMock) -> None:
        """Test query_backlinks with pagination parameters."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        await storage.query_backlinks("target.com", limit=50, offset=100)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_backlinks_with_snapshot_id(self, mock_session: AsyncMock) -> None:
        """Test query_backlinks with snapshot_id filter."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        await storage.query_backlinks("target.com", snapshot_id="CC-MAIN-2024-10")

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_backlinks_default_pagination(self, mock_session: AsyncMock) -> None:
        """Test query_backlinks uses default pagination values."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        await storage.query_backlinks("target.com")

        # Default limit=100, offset=0
        mock_session.execute.assert_called_once()


class TestPostgresStorageQueryAnchors:
    """Tests for PostgresStorage.query_anchors method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_query_anchors_returns_list(self, mock_session: AsyncMock) -> None:
        """Test query_anchors returns a list of AnchorCount."""
        from semrush_commoncrawl.storage.base import AnchorCount
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(anchor="click here", count=500),
            MagicMock(anchor="best tool", count=250),
            MagicMock(anchor="", count=100),  # Empty anchor (image links)
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        result = await storage.query_anchors("target.com")

        assert len(result) == 3
        assert all(isinstance(r, AnchorCount) for r in result)
        assert result[0].anchor == "click here"
        assert result[0].count == 500
        assert result[2].anchor == ""
        assert result[2].count == 100

    @pytest.mark.asyncio
    async def test_query_anchors_with_snapshot_id(self, mock_session: AsyncMock) -> None:
        """Test query_anchors with snapshot_id filter."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        await storage.query_anchors("target.com", snapshot_id="CC-MAIN-2024-10")

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_anchors_with_limit(self, mock_session: AsyncMock) -> None:
        """Test query_anchors with custom limit."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        await storage.query_anchors("target.com", limit=25)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_anchors_empty_result(self, mock_session: AsyncMock) -> None:
        """Test query_anchors with no results."""
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        storage = PostgresStorage(session=mock_session)
        result = await storage.query_anchors("nonexistent.com")

        assert result == []


class TestClickHouseStorage:
    """Tests for ClickHouseStorage stub implementation."""

    @pytest.mark.asyncio
    async def test_insert_edges_raises_not_implemented(self) -> None:
        """Test insert_edges raises NotImplementedError."""
        from semrush_commoncrawl.storage.base import Edge
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = ClickHouseStorage()
        edges = [
            Edge(
                snapshot_id="CC-MAIN-2024-10",
                source_url="https://example.com/page",
                source_domain="example.com",
                target_url="https://target.com/",
                target_domain="target.com",
            )
        ]

        with pytest.raises(NotImplementedError) as exc_info:
            await storage.insert_edges(edges)

        assert "ClickHouse storage not implemented" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_refdomains_raises_not_implemented(self) -> None:
        """Test query_refdomains raises NotImplementedError."""
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = ClickHouseStorage()

        with pytest.raises(NotImplementedError) as exc_info:
            await storage.query_refdomains("target.com")

        assert "ClickHouse storage not implemented" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_backlinks_raises_not_implemented(self) -> None:
        """Test query_backlinks raises NotImplementedError."""
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = ClickHouseStorage()

        with pytest.raises(NotImplementedError) as exc_info:
            await storage.query_backlinks("target.com")

        assert "ClickHouse storage not implemented" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_anchors_raises_not_implemented(self) -> None:
        """Test query_anchors raises NotImplementedError."""
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = ClickHouseStorage()

        with pytest.raises(NotImplementedError) as exc_info:
            await storage.query_anchors("target.com")

        assert "ClickHouse storage not implemented" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_refdomains_with_all_params_raises_not_implemented(
        self,
    ) -> None:
        """Test query_refdomains with all params raises NotImplementedError."""
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = ClickHouseStorage()

        with pytest.raises(NotImplementedError) as exc_info:
            await storage.query_refdomains("target.com", snapshot_id="CC-MAIN-2024-10", limit=50)

        assert "ClickHouse storage not implemented" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_backlinks_with_pagination_raises_not_implemented(
        self,
    ) -> None:
        """Test query_backlinks with pagination raises NotImplementedError."""
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = ClickHouseStorage()

        with pytest.raises(NotImplementedError) as exc_info:
            await storage.query_backlinks(
                "target.com",
                snapshot_id="CC-MAIN-2024-10",
                limit=50,
                offset=100,
            )

        assert "ClickHouse storage not implemented" in str(exc_info.value)


class TestStorageFactory:
    """Tests for storage factory function."""

    def test_get_postgres_storage(self) -> None:
        """Test creating PostgresStorage via factory."""
        from semrush_commoncrawl.storage import get_storage
        from semrush_commoncrawl.storage.postgres import PostgresStorage

        mock_session = AsyncMock()
        storage = get_storage("postgres", session=mock_session)

        assert isinstance(storage, PostgresStorage)

    def test_get_clickhouse_storage(self) -> None:
        """Test creating ClickHouseStorage via factory."""
        from semrush_commoncrawl.storage import get_storage
        from semrush_commoncrawl.storage.clickhouse import ClickHouseStorage

        storage = get_storage("clickhouse")

        assert isinstance(storage, ClickHouseStorage)

    def test_get_storage_invalid_type(self) -> None:
        """Test factory raises error for invalid storage type."""
        from semrush_commoncrawl.storage import get_storage

        with pytest.raises(ValueError) as exc_info:
            get_storage("invalid")

        assert "Unknown storage type" in str(exc_info.value)
