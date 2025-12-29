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

        mock_db_session.execute = AsyncMock(side_effect=[count_result, backlinks_result])

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

        mock_db_session.execute = AsyncMock(side_effect=[count_result, backlinks_result])

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

        mock_db_session.execute = AsyncMock(side_effect=[count_result, backlinks_result])

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

        mock_db_session.execute = AsyncMock(side_effect=[count_result, backlinks_result])

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
        response = await client.get("/links/domain/mysite.com/overlap?competitors=competitor1.com")
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

        # Mock backlink stats (using mappings().one_or_none() chain)
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = {
            "total_backlinks": 500,
            "unique_ref_domains": 75,
            "dofollow_count": 400,
            "nofollow_count": 100,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        }

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

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

        mock_db_session.execute = AsyncMock(side_effect=[project_result, anchors_result])

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

        mock_db_session.execute = AsyncMock(side_effect=[project_result, anchors_result])

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


class TestProjectOverlap:
    """Tests for GET /projects/{project_id}/backlinks/overlap."""

    @pytest.mark.asyncio
    async def test_get_project_overlap_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
        test_competitors,
    ):
        """Successfully get shared referring domains using project's competitors."""
        # Set up project with site and competitors
        test_project.sites = [test_site]
        test_project.competitors = test_competitors

        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock overlap query
        overlap_result = MagicMock()
        overlap_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "shared-site.com",
                "domains_linking_to": ["example.com", "competitor1.com"],
                "backlinks": 25,
            },
            {
                "ref_domain": "common-blog.org",
                "domains_linking_to": ["example.com", "competitor1.com", "competitor2.com"],
                "backlinks": 15,
            },
        ]

        mock_db_session.execute = AsyncMock(side_effect=[project_result, overlap_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overlap",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert "domain" in data
        assert "competitors" in data
        assert "shared_ref_domains" in data
        assert str(data["project_id"]) == str(test_project_id)
        assert data["domain"] == "example.com"
        assert len(data["competitors"]) == 2
        assert len(data["shared_ref_domains"]) == 2

    @pytest.mark.asyncio
    async def test_get_project_overlap_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
        test_competitors,
    ):
        """Limit parameter is applied."""
        test_project.sites = [test_site]
        test_project.competitors = test_competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        overlap_result = MagicMock()
        overlap_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "shared-site.com",
                "domains_linking_to": ["example.com", "competitor1.com"],
                "backlinks": 25,
            },
        ]

        mock_db_session.execute = AsyncMock(side_effect=[project_result, overlap_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overlap?limit=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["shared_ref_domains"]) == 1

    @pytest.mark.asyncio
    async def test_get_project_overlap_with_snapshot(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
        test_competitors,
        test_snapshot_id,
    ):
        """Filter by snapshot is applied."""
        test_project.sites = [test_site]
        test_project.competitors = test_competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        overlap_result = MagicMock()
        overlap_result.mappings.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[project_result, overlap_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overlap?snapshot_id={test_snapshot_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_project_overlap_project_not_found(
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
            f"/projects/{uuid.uuid4()}/backlinks/overlap",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_overlap_no_competitors(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
    ):
        """Returns 400 when project has no competitors."""
        test_project.sites = [test_site]
        test_project.competitors = []  # No competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overlap",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "competitors" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_project_overlap_no_sites(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_competitors,
    ):
        """Returns 400 when project has no sites."""
        test_project.sites = []  # No sites
        test_project.competitors = test_competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overlap",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "site" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_project_overlap_unauthorized(
        self,
        client,
        test_project_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(f"/projects/{test_project_id}/backlinks/overlap")
        assert response.status_code == 401


class TestProjectIntersect:
    """Tests for GET /projects/{project_id}/backlinks/intersect."""

    @pytest.mark.asyncio
    async def test_get_project_intersect_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
        test_competitors,
    ):
        """Successfully get link building opportunities using project's competitors."""
        # Set up project with site and competitors
        test_project.sites = [test_site]
        test_project.competitors = test_competitors

        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock intersect query
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

        mock_db_session.execute = AsyncMock(side_effect=[project_result, intersect_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/intersect",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert "domain" in data
        assert "competitors" in data
        assert "intersect_ref_domains" in data
        assert str(data["project_id"]) == str(test_project_id)
        assert data["domain"] == "example.com"
        assert len(data["competitors"]) == 2
        assert len(data["intersect_ref_domains"]) == 2

    @pytest.mark.asyncio
    async def test_get_project_intersect_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
        test_competitors,
    ):
        """Limit parameter is applied."""
        test_project.sites = [test_site]
        test_project.competitors = test_competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        intersect_result = MagicMock()
        intersect_result.mappings.return_value.all.return_value = [
            {
                "ref_domain": "opportunity-site.com",
                "links_to_competitors": ["competitor1.com"],
                "backlinks": 30,
            },
        ]

        mock_db_session.execute = AsyncMock(side_effect=[project_result, intersect_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/intersect?limit=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["intersect_ref_domains"]) == 1

    @pytest.mark.asyncio
    async def test_get_project_intersect_with_snapshot(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
        test_competitors,
        test_snapshot_id,
    ):
        """Filter by snapshot is applied."""
        test_project.sites = [test_site]
        test_project.competitors = test_competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        intersect_result = MagicMock()
        intersect_result.mappings.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[project_result, intersect_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/intersect?snapshot_id={test_snapshot_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_project_intersect_project_not_found(
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
            f"/projects/{uuid.uuid4()}/backlinks/intersect",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_intersect_no_competitors(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
    ):
        """Returns 400 when project has no competitors."""
        test_project.sites = [test_site]
        test_project.competitors = []  # No competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/intersect",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "competitors" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_project_intersect_no_sites(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_competitors,
    ):
        """Returns 400 when project has no sites."""
        test_project.sites = []  # No sites
        test_project.competitors = test_competitors

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/intersect",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "site" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_project_intersect_unauthorized(
        self,
        client,
        test_project_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(f"/projects/{test_project_id}/backlinks/intersect")
        assert response.status_code == 401


# =============================================================================
# Sprint 3: New/Lost Time Series Tests
# =============================================================================


@pytest.fixture
def sample_snapshots() -> list[dict]:
    """Create sample snapshot data for time series testing."""
    return [
        {
            "id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
            "date": datetime(2024, 6, 1, tzinfo=UTC).date(),
        },
        {
            "id": uuid.UUID("55555555-5555-5555-5555-555555555555"),
            "date": datetime(2024, 5, 1, tzinfo=UTC).date(),
        },
        {
            "id": uuid.UUID("66666666-6666-6666-6666-666666666666"),
            "date": datetime(2024, 4, 1, tzinfo=UTC).date(),
        },
        {
            "id": uuid.UUID("77777777-7777-7777-7777-777777777777"),
            "date": datetime(2024, 3, 1, tzinfo=UTC).date(),
        },
    ]


class TestNewLostTimeSeries:
    """Tests for GET /links/domain/{domain}/new-lost/series."""

    @pytest.mark.asyncio
    async def test_get_new_lost_series_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshots,
    ):
        """Successfully get new/lost time series for a domain."""
        # Mock snapshots query
        snapshots_result = MagicMock()
        snapshots_result.mappings.return_value.all.return_value = sample_snapshots

        # Mock domains for each snapshot (4 snapshots means 4 domain queries)
        # Snapshot 4 (oldest): [a.com, b.com]
        # Snapshot 3: [a.com, c.com] -> new: c.com, lost: b.com
        # Snapshot 2: [a.com, c.com, d.com] -> new: d.com, lost: none
        # Snapshot 1 (newest): [c.com, d.com, e.com] -> new: e.com, lost: a.com

        domains_snapshot_4 = MagicMock()
        domains_snapshot_4.scalars.return_value.all.return_value = ["a.com", "b.com"]

        domains_snapshot_3 = MagicMock()
        domains_snapshot_3.scalars.return_value.all.return_value = ["a.com", "c.com"]

        domains_snapshot_2 = MagicMock()
        domains_snapshot_2.scalars.return_value.all.return_value = ["a.com", "c.com", "d.com"]

        domains_snapshot_1 = MagicMock()
        domains_snapshot_1.scalars.return_value.all.return_value = ["c.com", "d.com", "e.com"]

        mock_db_session.execute = AsyncMock(
            side_effect=[
                snapshots_result,
                domains_snapshot_4,  # Oldest
                domains_snapshot_3,
                domains_snapshot_2,
                domains_snapshot_1,  # Newest
            ]
        )

        response = await client.get(
            "/links/domain/mysite.com/new-lost/series",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "domain" in data
        assert "items" in data
        assert data["domain"] == "mysite.com"
        # We get N-1 data points from N snapshots (comparing consecutive pairs)
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_get_new_lost_series_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshots,
    ):
        """Limit parameter restricts number of snapshots analyzed."""
        # Only return 2 snapshots
        snapshots_result = MagicMock()
        snapshots_result.mappings.return_value.all.return_value = sample_snapshots[:2]

        domains_snapshot_2 = MagicMock()
        domains_snapshot_2.scalars.return_value.all.return_value = ["a.com", "b.com"]

        domains_snapshot_1 = MagicMock()
        domains_snapshot_1.scalars.return_value.all.return_value = ["a.com", "c.com"]

        mock_db_session.execute = AsyncMock(
            side_effect=[
                snapshots_result,
                domains_snapshot_2,
                domains_snapshot_1,
            ]
        )

        response = await client.get(
            "/links/domain/mysite.com/new-lost/series?limit=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_new_lost_series_limit_max_50(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Limit cannot exceed 50."""
        response = await client.get(
            "/links/domain/mysite.com/new-lost/series?limit=100",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_new_lost_series_empty_result(
        self,
        client,
        mock_db_session,
        auth_headers,
    ):
        """Return empty items when no snapshots found."""
        snapshots_result = MagicMock()
        snapshots_result.mappings.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=snapshots_result)

        response = await client.get(
            "/links/domain/unknown-domain.com/new-lost/series",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_new_lost_series_single_snapshot(
        self,
        client,
        mock_db_session,
        auth_headers,
        sample_snapshots,
    ):
        """Single snapshot returns empty series (need pairs for comparison)."""
        snapshots_result = MagicMock()
        snapshots_result.mappings.return_value.all.return_value = [sample_snapshots[0]]

        domains_result = MagicMock()
        domains_result.scalars.return_value.all.return_value = ["a.com"]

        mock_db_session.execute = AsyncMock(side_effect=[snapshots_result, domains_result])

        response = await client.get(
            "/links/domain/mysite.com/new-lost/series",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_new_lost_series_unauthorized(
        self,
        client,
    ):
        """Returns 401 without authentication."""
        response = await client.get("/links/domain/mysite.com/new-lost/series")
        assert response.status_code == 401


class TestProjectNewLost:
    """Tests for GET /projects/{project_id}/backlinks/new-lost."""

    @pytest.mark.asyncio
    async def test_get_project_new_lost_success(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Successfully get project new/lost time series."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock new/lost data grouped by date
        new_lost_result = MagicMock()
        new_lost_result.mappings.return_value.all.return_value = [
            {"date": datetime(2024, 6, 15, tzinfo=UTC).date(), "new_count": 10, "lost_count": 2},
            {"date": datetime(2024, 6, 14, tzinfo=UTC).date(), "new_count": 5, "lost_count": 1},
            {"date": datetime(2024, 6, 13, tzinfo=UTC).date(), "new_count": 8, "lost_count": 3},
        ]

        mock_db_session.execute = AsyncMock(side_effect=[project_result, new_lost_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/new-lost",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "project_id" in data
        assert "items" in data
        assert str(data["project_id"]) == str(test_project_id)
        assert len(data["items"]) == 3
        assert data["items"][0]["new_count"] == 10
        assert data["items"][0]["lost_count"] == 2

    @pytest.mark.asyncio
    async def test_get_project_new_lost_with_limit(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Limit parameter restricts number of data points."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        new_lost_result = MagicMock()
        new_lost_result.mappings.return_value.all.return_value = [
            {"date": datetime(2024, 6, 15, tzinfo=UTC).date(), "new_count": 10, "lost_count": 2},
        ]

        mock_db_session.execute = AsyncMock(side_effect=[project_result, new_lost_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/new-lost?limit=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_project_new_lost_with_days(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Days parameter filters date range."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        new_lost_result = MagicMock()
        new_lost_result.mappings.return_value.all.return_value = [
            {"date": datetime(2024, 6, 15, tzinfo=UTC).date(), "new_count": 5, "lost_count": 1},
        ]

        mock_db_session.execute = AsyncMock(side_effect=[project_result, new_lost_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/new-lost?days=7",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_get_project_new_lost_limit_max_50(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Limit cannot exceed 50."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/new-lost?limit=100",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_project_new_lost_days_max_365(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Days cannot exceed 365."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        mock_db_session.execute = AsyncMock(return_value=project_result)

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/new-lost?days=500",
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_project_new_lost_empty_result(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Return empty items when no data found."""
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        new_lost_result = MagicMock()
        new_lost_result.mappings.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[project_result, new_lost_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/new-lost",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_project_new_lost_project_not_found(
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
            f"/projects/{uuid.uuid4()}/backlinks/new-lost",
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_new_lost_unauthorized(
        self,
        client,
        test_project_id,
    ):
        """Returns 401 without authentication."""
        response = await client.get(f"/projects/{test_project_id}/backlinks/new-lost")
        assert response.status_code == 401


# =============================================================================
# Sprint 3: Multi-source Backlink Merge Tests
# =============================================================================


class TestProjectBacklinksOverviewMultiSource:
    """Tests for multi-source backlink merge in overview endpoint."""

    @pytest.mark.asyncio
    async def test_overview_with_commoncrawl_merge(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
    ):
        """Overview merges project_backlinks with commoncrawl_edges when include_commoncrawl=True."""
        # Set up project with site
        test_project.sites = [test_site]

        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock merged stats (including CC data)
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = {
            "total_backlinks": 750,
            "unique_ref_domains": 120,
            "dofollow_count": 600,
            "nofollow_count": 150,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        }

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview?include_commoncrawl=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_backlinks"] == 750
        assert data["unique_ref_domains"] == 120

    @pytest.mark.asyncio
    async def test_overview_without_commoncrawl(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Overview only queries project_backlinks when include_commoncrawl=False."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock project_backlinks only stats
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = {
            "total_backlinks": 250,
            "unique_ref_domains": 40,
            "dofollow_count": 200,
            "nofollow_count": 50,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        }

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview?include_commoncrawl=false",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_backlinks"] == 250
        assert data["unique_ref_domains"] == 40

    @pytest.mark.asyncio
    async def test_overview_deduplicates_sources(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
    ):
        """Overview deduplicates backlinks from multiple sources."""
        # Set up project with site
        test_project.sites = [test_site]

        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock deduplicated stats
        # If we had 100 from project_backlinks and 80 from CC, but 30 duplicates,
        # result would be 150 total (after dedup)
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = {
            "total_backlinks": 150,
            "unique_ref_domains": 85,
            "dofollow_count": 120,
            "nofollow_count": 30,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        }

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Verify dedup'd total is returned
        assert data["total_backlinks"] == 150
        assert data["unique_ref_domains"] == 85

    @pytest.mark.asyncio
    async def test_overview_no_sites_uses_project_backlinks_only(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """When project has no sites, only project_backlinks are queried."""
        # Project has no sites
        test_project.sites = []

        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Mock project_backlinks only stats
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = {
            "total_backlinks": 100,
            "unique_ref_domains": 25,
            "dofollow_count": 80,
            "nofollow_count": 20,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        }

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview?include_commoncrawl=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Since no sites, CC can't be merged (no domain to match)
        assert data["total_backlinks"] == 100

    @pytest.mark.asyncio
    async def test_overview_handles_mixed_source_types(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
        test_site,
    ):
        """Overview correctly counts backlinks from import, crawl, commoncrawl, provider sources."""
        # Set up project with site
        test_project.sites = [test_site]

        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Stats representing mixed sources:
        # - 100 import
        # - 50 crawl
        # - 200 commoncrawl
        # - 25 provider
        # = 375 total
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = {
            "total_backlinks": 375,
            "unique_ref_domains": 200,
            "dofollow_count": 300,
            "nofollow_count": 75,
            "first_seen": datetime(2024, 1, 1, tzinfo=UTC),
            "last_seen": datetime(2024, 6, 15, tzinfo=UTC),
        }

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_backlinks"] == 375
        assert data["unique_ref_domains"] == 200
        assert data["dofollow_count"] == 300
        assert data["nofollow_count"] == 75

    @pytest.mark.asyncio
    async def test_overview_empty_result(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Returns zeros when no backlinks exist."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Empty result
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_backlinks"] == 0
        assert data["unique_ref_domains"] == 0
        assert data["dofollow_count"] == 0
        assert data["nofollow_count"] == 0
        assert data["first_seen"] is None
        assert data["last_seen"] is None

    @pytest.mark.asyncio
    async def test_overview_null_counts_become_zero(
        self,
        client,
        mock_db_session,
        auth_headers,
        test_project_id,
        test_project,
    ):
        """Null counts in database are returned as zeros."""
        # Mock project lookup
        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = test_project

        # Result with None values (can happen with empty aggregations)
        stats_result = MagicMock()
        stats_result.mappings.return_value.one_or_none.return_value = {
            "total_backlinks": None,
            "unique_ref_domains": None,
            "dofollow_count": None,
            "nofollow_count": None,
            "first_seen": None,
            "last_seen": None,
        }

        mock_db_session.execute = AsyncMock(side_effect=[project_result, stats_result])

        response = await client.get(
            f"/projects/{test_project_id}/backlinks/overview",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_backlinks"] == 0
        assert data["unique_ref_domains"] == 0
        assert data["dofollow_count"] == 0
        assert data["nofollow_count"] == 0
