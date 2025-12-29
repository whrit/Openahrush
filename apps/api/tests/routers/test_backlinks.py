"""
Tests for the backlinks router.

Tests cover:
- GET /links/domain/{domain}/refdomains - Get referring domains
- GET /links/domain/{domain}/backlinks - Get individual backlinks
- GET /links/domain/{domain}/anchors - Get anchor distribution
- GET /links/domain/{domain}/new-lost - Compare snapshots for new/lost domains
- GET /links/domain/{domain}/overlap - Shared referring domains with competitors
- GET /links/domain/{domain}/intersect - Link building opportunities
- POST /projects/{project_id}/backlinks/import - Import CSV
- GET /projects/{project_id}/backlinks/overview - Project backlink summary
- GET /projects/{project_id}/backlinks/anchors - Project anchor distribution
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def test_snapshot_id() -> uuid.UUID:
    """Test snapshot ID."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def test_snapshot_a_id() -> uuid.UUID:
    """Test snapshot A ID for comparison."""
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def test_snapshot_b_id() -> uuid.UUID:
    """Test snapshot B ID for comparison."""
    return uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def sample_ref_domains() -> list[dict]:
    """Create sample referring domains data."""
    return [
        {
            "ref_domain": "example.com",
            "backlinks": 150,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 1, tzinfo=UTC),
        },
        {
            "ref_domain": "blog.example.org",
            "backlinks": 75,
            "first_seen": datetime(2024, 2, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        },
        {
            "ref_domain": "news.site.com",
            "backlinks": 25,
            "first_seen": datetime(2024, 3, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 5, 1, tzinfo=UTC),
        },
    ]


@pytest.fixture
def sample_backlinks() -> list[dict]:
    """Create sample backlink data."""
    return [
        {
            "source_url": "https://example.com/article",
            "source_domain": "example.com",
            "target_url": "https://mysite.com/page1",
            "target_domain": "mysite.com",
            "anchor": "great resource",
            "flags": {"dofollow": True, "image": False},
        },
        {
            "source_url": "https://blog.example.org/post",
            "source_domain": "blog.example.org",
            "target_url": "https://mysite.com/page2",
            "target_domain": "mysite.com",
            "anchor": "click here",
            "flags": {"dofollow": False, "image": False},
        },
    ]


@pytest.fixture
def sample_anchors() -> list[dict]:
    """Create sample anchor distribution data."""
    return [
        {"anchor": "great resource", "count": 50},
        {"anchor": "click here", "count": 30},
        {"anchor": "mysite", "count": 25},
        {"anchor": "[image]", "count": 10},
    ]


class TestGetRefDomains:
    """Tests for GET /links/domain/{domain}/refdomains."""

    @pytest.mark.asyncio
    async def test_get_refdomains_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_ref_domains,
    ):
        """Successfully get referring domains for a domain."""
        # Mock the storage/query response
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = sample_ref_domains

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/links/domain/mysite.com/refdomains",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 3
        assert data["items"][0]["ref_domain"] == "example.com"
        assert data["items"][0]["backlinks"] == 150

    @pytest.mark.asyncio
    async def test_get_refdomains_with_snapshot(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_snapshot_id,
        sample_ref_domains,
    ):
        """Get referring domains filtered by snapshot."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = sample_ref_domains[:2]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/links/domain/mysite.com/refdomains?snapshot_id={test_snapshot_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_refdomains_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_ref_domains,
    ):
        """Limit parameter is applied."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = sample_ref_domains[:1]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/links/domain/mysite.com/refdomains?limit=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_refdomains_limit_max_10000(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Limit cannot exceed 10000."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/links/domain/mysite.com/refdomains?limit=50000",
            headers=auth_headers,
        )

        # Should return 422 validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_refdomains_empty_result(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Return empty list when no referring domains found."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/links/domain/unknown-domain.com/refdomains",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_refdomains_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get("/links/domain/mysite.com/refdomains")
        assert response.status_code == 401


class TestGetBacklinks:
    """Tests for GET /links/domain/{domain}/backlinks."""

    @pytest.mark.asyncio
    async def test_get_backlinks_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_backlinks,
    ):
        """Successfully get individual backlinks for a domain."""
        # Mock total count
        count_result = MagicMock()
        count_result.scalar.return_value = len(sample_backlinks)

        # Mock backlinks data
        backlinks_result = MagicMock()
        backlinks_result.mappings.return_value.all.return_value = sample_backlinks

        mock_db_session.execute = AsyncMock(
            side_effect=[count_result, backlinks_result]
        )

        response = await client.get(
            "/links/domain/mysite.com/backlinks",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["source_url"] == "https://example.com/article"

    @pytest.mark.asyncio
    async def test_get_backlinks_with_pagination(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_backlinks,
    ):
        """Pagination parameters are applied."""
        count_result = MagicMock()
        count_result.scalar.return_value = 100

        backlinks_result = MagicMock()
        backlinks_result.mappings.return_value.all.return_value = sample_backlinks[:1]

        mock_db_session.execute = AsyncMock(
            side_effect=[count_result, backlinks_result]
        )

        response = await client.get(
            "/links/domain/mysite.com/backlinks?limit=10&offset=20",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 100
        assert data["limit"] == 10
        assert data["offset"] == 20

    @pytest.mark.asyncio
    async def test_get_backlinks_with_source_domain_filter(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_backlinks,
    ):
        """Filter by source domain is applied."""
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        backlinks_result = MagicMock()
        backlinks_result.mappings.return_value.all.return_value = [sample_backlinks[0]]

        mock_db_session.execute = AsyncMock(
            side_effect=[count_result, backlinks_result]
        )

        response = await client.get(
            "/links/domain/mysite.com/backlinks?source_domain=example.com",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["source_domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_get_backlinks_with_snapshot(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_snapshot_id,
        sample_backlinks,
    ):
        """Filter by snapshot is applied."""
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        backlinks_result = MagicMock()
        backlinks_result.mappings.return_value.all.return_value = sample_backlinks

        mock_db_session.execute = AsyncMock(
            side_effect=[count_result, backlinks_result]
        )

        response = await client.get(
            f"/links/domain/mysite.com/backlinks?snapshot_id={test_snapshot_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_backlinks_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get("/links/domain/mysite.com/backlinks")
        assert response.status_code == 401


class TestGetAnchors:
    """Tests for GET /links/domain/{domain}/anchors."""

    @pytest.mark.asyncio
    async def test_get_anchors_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_anchors,
    ):
        """Successfully get anchor distribution for a domain."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = sample_anchors

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/links/domain/mysite.com/anchors",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 4
        # Should be sorted by count DESC
        assert data["items"][0]["count"] >= data["items"][1]["count"]

    @pytest.mark.asyncio
    async def test_get_anchors_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_anchors,
    ):
        """Limit parameter is applied."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = sample_anchors[:2]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            "/links/domain/mysite.com/anchors?limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_anchors_with_snapshot(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_snapshot_id,
        sample_anchors,
    ):
        """Filter by snapshot is applied."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = sample_anchors

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client.get(
            f"/links/domain/mysite.com/anchors?snapshot_id={test_snapshot_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_anchors_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get("/links/domain/mysite.com/anchors")
        assert response.status_code == 401


class TestNewLostDomains:
    """Tests for GET /links/domain/{domain}/new-lost."""

    @pytest.mark.asyncio
    async def test_get_new_lost_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_snapshot_a_id,
        test_snapshot_b_id,
    ):
        """Successfully compare snapshots for new/lost domains."""
        # Mock snapshot A domains
        snapshot_a_result = MagicMock()
        snapshot_a_result.scalars.return_value.all.return_value = [
            "example.com",
            "blog.example.org",
            "old-domain.com",
        ]

        # Mock snapshot B domains
        snapshot_b_result = MagicMock()
        snapshot_b_result.scalars.return_value.all.return_value = [
            "example.com",
            "blog.example.org",
            "new-domain.com",
        ]

        # Mock new domain details
        new_domain_result = MagicMock()
        new_domain_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "new-domain.com",
                "backlinks": 10,
                "first_seen": datetime(2024, 6, 1, tzinfo=UTC),
                "last_seen": datetime(2024, 6, 1, tzinfo=UTC),
            }
        ]

        # Mock lost domain details
        lost_domain_result = MagicMock()
        lost_domain_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "old-domain.com",
                "backlinks": 5,
                "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
                "last_seen": datetime(2024, 5, 1, tzinfo=UTC),
            }
        ]

        mock_db_session.execute = AsyncMock(
            side_effect=[
                snapshot_a_result,
                snapshot_b_result,
                new_domain_result,
                lost_domain_result,
            ]
        )

        response = await client.get(
            f"/links/domain/mysite.com/new-lost?snapshot_a={test_snapshot_a_id}&snapshot_b={test_snapshot_b_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "new" in data
        assert "lost" in data
        assert len(data["new"]) == 1
        assert len(data["lost"]) == 1
        assert data["new"][0]["ref_domain"] == "new-domain.com"
        assert data["lost"][0]["ref_domain"] == "old-domain.com"

    @pytest.mark.asyncio
    async def test_get_new_lost_missing_snapshot_a(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_snapshot_b_id,
    ):
        """Returns 400 when snapshot_a is missing."""
        response = await client.get(
            f"/links/domain/mysite.com/new-lost?snapshot_b={test_snapshot_b_id}",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_new_lost_missing_snapshot_b(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_snapshot_a_id,
    ):
        """Returns 400 when snapshot_b is missing."""
        response = await client.get(
            f"/links/domain/mysite.com/new-lost?snapshot_a={test_snapshot_a_id}",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_new_lost_unauthorized(
        self,
        client,
        test_snapshot_a_id,
        test_snapshot_b_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(
            f"/links/domain/mysite.com/new-lost?snapshot_a={test_snapshot_a_id}&snapshot_b={test_snapshot_b_id}"
        )
        assert response.status_code == 401


class TestDomainOverlap:
    """Tests for GET /links/domain/{domain}/overlap."""

    @pytest.mark.asyncio
    async def test_get_overlap_success(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Successfully get shared referring domains with competitors."""
        # Mock shared domains query
        overlap_result = MagicMock()
        overlap_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "shared-site.com",
                "domains_linking_to": ["mysite.com", "competitor1.com"],
                "backlinks": 25,
            },
            {
                "ref_domain": "common-blog.org",
                "domains_linking_to": ["mysite.com", "competitor1.com", "competitor2.com"],
                "backlinks": 15,
            },
        ]

        mock_db_session.execute = AsyncMock(return_value=overlap_result)

        response = await client.get(
            "/links/domain/mysite.com/overlap?competitors=competitor1.com,competitor2.com",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "domain" in data
        assert "competitors" in data
        assert "shared_ref_domains" in data
        assert data["domain"] == "mysite.com"
        assert len(data["shared_ref_domains"]) == 2

    @pytest.mark.asyncio
    async def test_get_overlap_single_competitor(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Works with a single competitor."""
        overlap_result = MagicMock()
        overlap_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "shared-site.com",
                "domains_linking_to": ["mysite.com", "competitor1.com"],
                "backlinks": 25,
            },
        ]

        mock_db_session.execute = AsyncMock(return_value=overlap_result)

        response = await client.get(
            "/links/domain/mysite.com/overlap?competitors=competitor1.com",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["competitors"] == ["competitor1.com"]

    @pytest.mark.asyncio
    async def test_get_overlap_missing_competitors(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 422 when competitors parameter is missing."""
        response = await client.get(
            "/links/domain/mysite.com/overlap",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_overlap_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get(
            "/links/domain/mysite.com/overlap?competitors=competitor1.com"
        )
        assert response.status_code == 401


class TestDomainIntersect:
    """Tests for GET /links/domain/{domain}/intersect."""

    @pytest.mark.asyncio
    async def test_get_intersect_success(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Successfully get link building opportunities."""
        # Mock intersect domains query
        intersect_result = MagicMock()
        intersect_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "opportunity-site.com",
                "links_to_competitors": ["competitor1.com", "competitor2.com"],
                "backlinks": 30,
            },
            {
                "ref_domain": "missed-blog.org",
                "links_to_competitors": ["competitor1.com"],
                "backlinks": 20,
            },
        ]

        mock_db_session.execute = AsyncMock(return_value=intersect_result)

        response = await client.get(
            "/links/domain/mysite.com/intersect?competitors=competitor1.com,competitor2.com",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "domain" in data
        assert "competitors" in data
        assert "intersect_ref_domains" in data
        assert data["domain"] == "mysite.com"
        assert len(data["intersect_ref_domains"]) == 2

    @pytest.mark.asyncio
    async def test_get_intersect_missing_competitors(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 422 when competitors parameter is missing."""
        response = await client.get(
            "/links/domain/mysite.com/intersect",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_intersect_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get(
            "/links/domain/mysite.com/intersect?competitors=competitor1.com"
        )
        assert response.status_code == 401


class TestProjectBacklinksImport:
    """Tests for POST /projects/{project_id}/backlinks/import."""

    @pytest.mark.asyncio
    async def test_import_csv_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Successfully import backlinks from CSV."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        csv_content = b"source_url,target_url,anchor\nhttps://example.com/page,https://mysite.com/,click here\nhttps://blog.org/post,https://mysite.com/about,learn more"

        response = await client.post(
            f"/projects/{test_project_id}/backlinks/import",
            headers=auth_headers,
            files={"file": ("backlinks.csv", io.BytesIO(csv_content), "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 2
        assert data["errors"] == 0

    @pytest.mark.asyncio
    async def test_import_csv_with_errors(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Import CSV with some invalid rows."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        # Third row has invalid URL
        csv_content = b"source_url,target_url,anchor\nhttps://example.com/page,https://mysite.com/,click here\nnot-a-url,https://mysite.com/about,learn more\nhttps://valid.org/,https://mysite.com/,test"

        response = await client.post(
            f"/projects/{test_project_id}/backlinks/import",
            headers=auth_headers,
            files={"file": ("backlinks.csv", io.BytesIO(csv_content), "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 2
        assert data["errors"] == 1
        assert len(data["error_details"]) == 1

    @pytest.mark.asyncio
    async def test_import_csv_missing_columns(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Returns 400 when required columns are missing."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)

        csv_content = b"source,destination\nhttps://example.com/,https://mysite.com/"

        response = await client.post(
            f"/projects/{test_project_id}/backlinks/import",
            headers=auth_headers,
            files={"file": ("backlinks.csv", io.BytesIO(csv_content), "text/csv")},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_import_csv_project_not_found(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 404 when project not found."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=project_result)

        csv_content = b"source_url,target_url,anchor\nhttps://example.com/,https://mysite.com/,test"

        response = await client.post(
            f"/projects/{uuid.uuid4()}/backlinks/import",
            headers=auth_headers,
            files={"file": ("backlinks.csv", io.BytesIO(csv_content), "text/csv")},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_import_csv_unauthorized(
        self,
        client,
        test_project_id,
    ):
        """Returns 401 without authentication."""
        csv_content = b"source_url,target_url,anchor\nhttps://example.com/,https://mysite.com/,test"

        response = await client.post(
            f"/projects/{test_project_id}/backlinks/import",
            files={"file": ("backlinks.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 401


class TestProjectBacklinksOverview:
    """Tests for GET /projects/{project_id}/backlinks/overview."""

    @pytest.mark.asyncio
    async def test_get_overview_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Successfully get project backlink overview."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock backlink stats
        stats_result = MagicMock()
        stats_result.one_or_none.return_value = {
            "total_backlinks": 500,
            "unique_ref_domains": 75,
            "dofollow_count": 400,
            "nofollow_count": 100,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        }

        mock_db_session.execute = AsyncMock(
            side_effect=[project_result, stats_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_backlinks" in data
        assert "unique_ref_domains" in data
        assert data["total_backlinks"] == 500
        assert data["unique_ref_domains"] == 75

    @pytest.mark.asyncio
    async def test_get_overview_project_not_found(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 404 when project not found."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{uuid.uuid4()}/backlinks/overview",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_overview_unauthorized(
        self,
        client,
        test_project_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(f"/projects/{test_project_id}/backlinks/overview")
        assert response.status_code == 401


class TestProjectBacklinksAnchors:
    """Tests for GET /projects/{project_id}/backlinks/anchors."""

    @pytest.mark.asyncio
    async def test_get_project_anchors_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        sample_anchors,
    ):
        """Successfully get project anchor distribution."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock anchor distribution
        anchors_result = MagicMock()
        anchors_result.mappings.return_value.all.return_value = sample_anchors

        mock_db_session.execute = AsyncMock(
            side_effect=[project_result, anchors_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/anchors",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 4

    @pytest.mark.asyncio
    async def test_get_project_anchors_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        sample_anchors,
    ):
        """Limit parameter is applied."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        anchors_result = MagicMock()
        anchors_result.mappings.return_value.all.return_value = sample_anchors[:2]

        mock_db_session.execute = AsyncMock(
            side_effect=[project_result, anchors_result]
        )

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/anchors?limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_project_anchors_project_not_found(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Returns 404 when project not found."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{uuid.uuid4()}/backlinks/anchors",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_anchors_unauthorized(
        self,
        client,
        test_project_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(f"/projects/{test_project_id}/backlinks/anchors")
        assert response.status_code == 401
