"""
Backlinks API endpoints.

Provides endpoints for:
- Domain Explorer: referring domains, backlinks, anchors
- New/Lost Detection: compare snapshots
- Competitive Analysis: overlap and intersect
- Project Backlinks: import, overview, anchors
"""

import csv
import io
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from semrush_core.models import Project
from sqlalchemy import select, text

from semrush_api.deps import CurrentUser, DbSession
from semrush_api.schemas.backlinks import (
    AnchorListResponse,
    AnchorResponse,
    BacklinkListResponse,
    BacklinkOverviewResponse,
    BacklinkResponse,
    ImportResponse,
    IntersectResponse,
    NewLostResponse,
    OverlapResponse,
    RefDomainListResponse,
    RefDomainResponse,
)

# Router for domain explorer endpoints (/links/domain/...)
links_router = APIRouter(prefix="/links", tags=["Backlinks"])

# Router for project backlinks endpoints (/projects/{project_id}/backlinks/...)
projects_router = APIRouter(prefix="/projects", tags=["Project Backlinks"])


async def get_user_project(
    db: DbSession,
    project_id: UUID,
    current_user: CurrentUser,
) -> Project:
    """
    Get a project owned by the current user.

    Args:
        db: Database session.
        project_id: Project UUID.
        current_user: Current authenticated user.

    Returns:
        Project if found and owned by user.

    Raises:
        HTTPException: 404 if project not found or not owned by user.
    """
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.user_id,
        )
    )
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


def is_valid_url(url: str) -> bool:
    """
    Validate that a string is a valid URL.

    Args:
        url: URL string to validate.

    Returns:
        True if valid URL, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def extract_domain(url: str) -> str:
    """
    Extract domain from a URL.

    Args:
        url: Full URL.

    Returns:
        Domain portion of the URL.
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


# =============================================================================
# Epic 3.4: Domain Explorer API
# =============================================================================


@links_router.get(
    "/domain/{domain}/refdomains",
    response_model=RefDomainListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get referring domains",
    description="Get referring domains for a domain, sorted by backlink count descending.",
)
async def get_referring_domains(
    domain: str,
    db: DbSession,
    current_user: CurrentUser,
    snapshot_id: Annotated[
        UUID | None,
        Query(description="Filter by snapshot ID"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=10000, description="Maximum number of results"),
    ] = 100,
) -> RefDomainListResponse:
    """
    Get referring domains for a domain.

    Returns list of domains that link to the target domain,
    sorted by backlink count in descending order.

    Args:
        domain: Target domain to analyze.
        db: Database session.
        current_user: Current authenticated user.
        snapshot_id: Optional snapshot ID to filter by.
        limit: Maximum number of results (default 100, max 10000).

    Returns:
        List of referring domains with backlink counts.
    """
    # Build query for referring domains
    # Using raw SQL for aggregation - in production this would query
    # the actual backlinks/link_facts table
    query = text("""
        SELECT
            source_domain as ref_domain,
            COUNT(*) as backlinks,
            MIN(first_seen) as first_seen,
            MAX(last_seen) as last_seen
        FROM link_facts
        WHERE target_domain = :domain
        AND (:snapshot_id IS NULL OR snapshot_id = :snapshot_id)
        GROUP BY source_domain
        ORDER BY backlinks DESC
        LIMIT :limit
    """)

    params = {
        "domain": domain,
        "snapshot_id": str(snapshot_id) if snapshot_id else None,
        "limit": limit,
    }
    result = await db.execute(query, params)
    rows = result.mappings().all()

    items = [
        RefDomainResponse(
            ref_domain=row["ref_domain"],
            backlinks=row["backlinks"],
            first_seen=row.get("first_seen"),
            last_seen=row.get("last_seen"),
        )
        for row in rows
    ]

    return RefDomainListResponse(items=items)


@links_router.get(
    "/domain/{domain}/backlinks",
    response_model=BacklinkListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get individual backlinks",
    description="Get individual backlinks for a domain with pagination.",
)
async def get_backlinks(
    domain: str,
    db: DbSession,
    current_user: CurrentUser,
    snapshot_id: Annotated[
        UUID | None,
        Query(description="Filter by snapshot ID"),
    ] = None,
    source_domain: Annotated[
        str | None,
        Query(description="Filter by source domain"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Maximum number of results"),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0, description="Offset for pagination"),
    ] = 0,
) -> BacklinkListResponse:
    """
    Get individual backlinks for a domain.

    Returns paginated list of backlinks pointing to the target domain.

    Args:
        domain: Target domain to analyze.
        db: Database session.
        current_user: Current authenticated user.
        snapshot_id: Optional snapshot ID to filter by.
        source_domain: Optional source domain filter.
        limit: Maximum number of results per page.
        offset: Pagination offset.

    Returns:
        Paginated list of backlinks.
    """
    # Count query
    count_query = text("""
        SELECT COUNT(*) as total
        FROM link_facts
        WHERE target_domain = :domain
        AND (:snapshot_id IS NULL OR snapshot_id = :snapshot_id)
        AND (:source_domain IS NULL OR source_domain = :source_domain)
    """)

    count_result = await db.execute(
        count_query,
        {
            "domain": domain,
            "snapshot_id": str(snapshot_id) if snapshot_id else None,
            "source_domain": source_domain,
        },
    )
    total = count_result.scalar() or 0

    # Data query
    data_query = text("""
        SELECT
            source_url,
            source_domain,
            target_url,
            target_domain,
            anchor,
            flags
        FROM link_facts
        WHERE target_domain = :domain
        AND (:snapshot_id IS NULL OR snapshot_id = :snapshot_id)
        AND (:source_domain IS NULL OR source_domain = :source_domain)
        ORDER BY source_domain, source_url
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(
        data_query,
        {
            "domain": domain,
            "snapshot_id": str(snapshot_id) if snapshot_id else None,
            "source_domain": source_domain,
            "limit": limit,
            "offset": offset,
        },
    )
    rows = result.mappings().all()

    items = [
        BacklinkResponse(
            source_url=row["source_url"],
            source_domain=row["source_domain"],
            target_url=row["target_url"],
            target_domain=row["target_domain"],
            anchor=row.get("anchor"),
            flags=row.get("flags", {}),
        )
        for row in rows
    ]

    return BacklinkListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@links_router.get(
    "/domain/{domain}/anchors",
    response_model=AnchorListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get anchor distribution",
    description="Get anchor text distribution for a domain, sorted by count descending.",
)
async def get_anchor_distribution(
    domain: str,
    db: DbSession,
    current_user: CurrentUser,
    snapshot_id: Annotated[
        UUID | None,
        Query(description="Filter by snapshot ID"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Maximum number of results"),
    ] = 100,
) -> AnchorListResponse:
    """
    Get anchor text distribution for a domain.

    Returns list of anchor texts with their occurrence counts,
    sorted by count in descending order.

    Args:
        domain: Target domain to analyze.
        db: Database session.
        current_user: Current authenticated user.
        snapshot_id: Optional snapshot ID to filter by.
        limit: Maximum number of results.

    Returns:
        List of anchors with counts.
    """
    query = text("""
        SELECT
            COALESCE(anchor, '') as anchor,
            COUNT(*) as count
        FROM link_facts
        WHERE target_domain = :domain
        AND (:snapshot_id IS NULL OR snapshot_id = :snapshot_id)
        GROUP BY anchor
        ORDER BY count DESC
        LIMIT :limit
    """)

    params = {
        "domain": domain,
        "snapshot_id": str(snapshot_id) if snapshot_id else None,
        "limit": limit,
    }
    result = await db.execute(query, params)
    rows = result.mappings().all()

    items = [
        AnchorResponse(
            anchor=row["anchor"],
            count=row["count"],
        )
        for row in rows
    ]

    return AnchorListResponse(items=items)


# =============================================================================
# Epic 3.5: New/Lost Detection
# =============================================================================


@links_router.get(
    "/domain/{domain}/new-lost",
    response_model=NewLostResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare snapshots for new/lost domains",
    description="Compare two snapshots to find new and lost referring domains.",
)
async def get_new_lost_domains(
    domain: str,
    db: DbSession,
    current_user: CurrentUser,
    snapshot_a: Annotated[
        UUID,
        Query(description="First snapshot ID (older)"),
    ],
    snapshot_b: Annotated[
        UUID,
        Query(description="Second snapshot ID (newer)"),
    ],
) -> NewLostResponse:
    """
    Compare snapshots to find new and lost referring domains.

    Compares two snapshots and returns:
    - new: Domains in snapshot_b but not in snapshot_a
    - lost: Domains in snapshot_a but not in snapshot_b

    Args:
        domain: Target domain to analyze.
        db: Database session.
        current_user: Current authenticated user.
        snapshot_a: First (older) snapshot ID.
        snapshot_b: Second (newer) snapshot ID.

    Returns:
        New and lost referring domains.
    """
    # Get domains in snapshot A
    query_a = text("""
        SELECT DISTINCT source_domain
        FROM link_facts
        WHERE target_domain = :domain
        AND snapshot_id = :snapshot_id
    """)

    result_a = await db.execute(query_a, {"domain": domain, "snapshot_id": str(snapshot_a)})
    domains_a = set(result_a.scalars().all())

    # Get domains in snapshot B
    result_b = await db.execute(query_a, {"domain": domain, "snapshot_id": str(snapshot_b)})
    domains_b = set(result_b.scalars().all())

    # Calculate new and lost
    new_domains = domains_b - domains_a
    lost_domains = domains_a - domains_b

    # Get details for new domains
    new_items: list[RefDomainResponse] = []
    if new_domains:
        new_query = text("""
            SELECT
                source_domain as ref_domain,
                COUNT(*) as backlinks,
                MIN(first_seen) as first_seen,
                MAX(last_seen) as last_seen
            FROM link_facts
            WHERE target_domain = :domain
            AND snapshot_id = :snapshot_id
            AND source_domain = ANY(:domains)
            GROUP BY source_domain
            ORDER BY backlinks DESC
        """)

        new_result = await db.execute(
            new_query,
            {
                "domain": domain,
                "snapshot_id": str(snapshot_b),
                "domains": list(new_domains),
            },
        )
        new_rows = new_result.mappings().all()

        new_items = [
            RefDomainResponse(
                ref_domain=row["ref_domain"],
                backlinks=row["backlinks"],
                first_seen=row.get("first_seen"),
                last_seen=row.get("last_seen"),
            )
            for row in new_rows
        ]

    # Get details for lost domains
    lost_items: list[RefDomainResponse] = []
    if lost_domains:
        lost_query = text("""
            SELECT
                source_domain as ref_domain,
                COUNT(*) as backlinks,
                MIN(first_seen) as first_seen,
                MAX(last_seen) as last_seen
            FROM link_facts
            WHERE target_domain = :domain
            AND snapshot_id = :snapshot_id
            AND source_domain = ANY(:domains)
            GROUP BY source_domain
            ORDER BY backlinks DESC
        """)

        lost_result = await db.execute(
            lost_query,
            {
                "domain": domain,
                "snapshot_id": str(snapshot_a),
                "domains": list(lost_domains),
            },
        )
        lost_rows = lost_result.mappings().all()

        lost_items = [
            RefDomainResponse(
                ref_domain=row["ref_domain"],
                backlinks=row["backlinks"],
                first_seen=row.get("first_seen"),
                last_seen=row.get("last_seen"),
            )
            for row in lost_rows
        ]

    return NewLostResponse(new=new_items, lost=lost_items)


# =============================================================================
# Epic 3.6: Competitive Analysis
# =============================================================================


@links_router.get(
    "/domain/{domain}/overlap",
    response_model=OverlapResponse,
    status_code=status.HTTP_200_OK,
    summary="Get shared referring domains",
    description="Find referring domains that link to both the target domain and competitors.",
)
async def get_domain_overlap(
    domain: str,
    db: DbSession,
    current_user: CurrentUser,
    competitors: Annotated[
        str,
        Query(description="Comma-separated list of competitor domains"),
    ],
) -> OverlapResponse:
    """
    Get referring domains shared with competitors.

    Finds referring domains that link to both the target domain
    and at least one competitor domain.

    Args:
        domain: Primary domain to analyze.
        db: Database session.
        current_user: Current authenticated user.
        competitors: Comma-separated list of competitor domains.

    Returns:
        Overlap analysis with shared referring domains.
    """
    competitor_list = [c.strip() for c in competitors.split(",") if c.strip()]

    if not competitor_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one competitor domain is required",
        )

    all_domains = [domain, *competitor_list]

    # Query for domains that link to multiple targets
    query = text("""
        SELECT
            source_domain as ref_domain,
            ARRAY_AGG(DISTINCT target_domain) as domains_linking_to,
            SUM(backlinks) as backlinks
        FROM (
            SELECT
                source_domain,
                target_domain,
                COUNT(*) as backlinks
            FROM link_facts
            WHERE target_domain = ANY(:domains)
            GROUP BY source_domain, target_domain
        ) sub
        GROUP BY source_domain
        HAVING COUNT(DISTINCT target_domain) > 1
        AND :primary_domain = ANY(ARRAY_AGG(DISTINCT target_domain))
        ORDER BY backlinks DESC
    """)

    result = await db.execute(
        query,
        {"domains": all_domains, "primary_domain": domain},
    )
    rows = result.mappings().all()

    shared_ref_domains = [
        {
            "ref_domain": row["ref_domain"],
            "domains_linking_to": row["domains_linking_to"],
            "backlinks": row["backlinks"],
        }
        for row in rows
    ]

    return OverlapResponse(
        domain=domain,
        competitors=competitor_list,
        shared_ref_domains=shared_ref_domains,
    )


@links_router.get(
    "/domain/{domain}/intersect",
    response_model=IntersectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get link building opportunities",
    description="Find referring domains that link to competitors but not to the target domain.",
)
async def get_domain_intersect(
    domain: str,
    db: DbSession,
    current_user: CurrentUser,
    competitors: Annotated[
        str,
        Query(description="Comma-separated list of competitor domains"),
    ],
) -> IntersectResponse:
    """
    Get link building opportunities.

    Finds referring domains that link to competitor domains
    but do NOT link to the primary domain.

    Args:
        domain: Primary domain to analyze.
        db: Database session.
        current_user: Current authenticated user.
        competitors: Comma-separated list of competitor domains.

    Returns:
        Intersect analysis with link building opportunities.
    """
    competitor_list = [c.strip() for c in competitors.split(",") if c.strip()]

    if not competitor_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one competitor domain is required",
        )

    # Query for domains that link to competitors but NOT to primary domain
    query = text("""
        SELECT
            source_domain as ref_domain,
            ARRAY_AGG(DISTINCT target_domain) as links_to_competitors,
            SUM(backlinks) as backlinks
        FROM (
            SELECT
                source_domain,
                target_domain,
                COUNT(*) as backlinks
            FROM link_facts
            WHERE target_domain = ANY(:competitors)
            GROUP BY source_domain, target_domain
        ) sub
        WHERE source_domain NOT IN (
            SELECT DISTINCT source_domain
            FROM link_facts
            WHERE target_domain = :primary_domain
        )
        GROUP BY source_domain
        ORDER BY backlinks DESC
    """)

    result = await db.execute(
        query,
        {"competitors": competitor_list, "primary_domain": domain},
    )
    rows = result.mappings().all()

    intersect_ref_domains = [
        {
            "ref_domain": row["ref_domain"],
            "links_to_competitors": row["links_to_competitors"],
            "backlinks": row["backlinks"],
        }
        for row in rows
    ]

    return IntersectResponse(
        domain=domain,
        competitors=competitor_list,
        intersect_ref_domains=intersect_ref_domains,
    )


# =============================================================================
# Epic 3.7: Project Backlinks
# =============================================================================


@projects_router.post(
    "/{project_id}/backlinks/import",
    response_model=ImportResponse,
    status_code=status.HTTP_200_OK,
    summary="Import backlinks from CSV",
    description="Import backlinks from a CSV file with columns: source_url, target_url, anchor (optional).",
)
async def import_backlinks_csv(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="CSV file with backlinks data")],
) -> ImportResponse:
    """
    Import backlinks from a CSV file.

    Expects CSV with columns:
    - source_url (required): Full URL of the linking page
    - target_url (required): Full URL being linked to
    - anchor (optional): Link anchor text

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.
        file: Uploaded CSV file.

    Returns:
        Import statistics with counts and errors.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Read and parse CSV
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = content.decode("latin-1")
        except UnicodeDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to decode file. Please use UTF-8 encoding.",
            ) from e

    reader = csv.DictReader(io.StringIO(text_content))

    # Validate required columns
    if reader.fieldnames is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or malformed",
        )

    required_columns = {"source_url", "target_url"}
    found_columns = set(reader.fieldnames)

    if not required_columns.issubset(found_columns):
        missing = required_columns - found_columns
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required columns: {', '.join(sorted(missing))}",
        )

    imported = 0
    errors = 0
    error_details: list[str] = []

    for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
        source_url = row.get("source_url", "").strip()
        target_url = row.get("target_url", "").strip()
        anchor = row.get("anchor", "").strip() if "anchor" in row else None

        # Validate URLs
        if not is_valid_url(source_url):
            errors += 1
            error_details.append(f"Row {row_num}: Invalid source_url '{source_url}'")
            continue

        if not is_valid_url(target_url):
            errors += 1
            error_details.append(f"Row {row_num}: Invalid target_url '{target_url}'")
            continue

        # Extract domains
        source_domain = extract_domain(source_url)
        target_domain = extract_domain(target_url)

        # Insert into database (using raw SQL for link_facts table)
        # In production, this would use proper ORM models
        insert_query = text("""
            INSERT INTO project_backlinks
            (project_id, source_url, source_domain, target_url, target_domain, anchor, created_at)
            VALUES (:project_id, :source_url, :source_domain, :target_url, :target_domain, :anchor, NOW())
            ON CONFLICT DO NOTHING
        """)

        try:
            await db.execute(
                insert_query,
                {
                    "project_id": str(project_id),
                    "source_url": source_url,
                    "source_domain": source_domain,
                    "target_url": target_url,
                    "target_domain": target_domain,
                    "anchor": anchor,
                },
            )
            imported += 1
        except Exception as e:
            errors += 1
            error_details.append(f"Row {row_num}: Database error - {e!s}")

    await db.commit()

    return ImportResponse(
        imported=imported,
        errors=errors,
        error_details=error_details[:100],  # Limit error details
    )


@projects_router.get(
    "/{project_id}/backlinks/overview",
    response_model=BacklinkOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project backlink overview",
    description="Get aggregated backlink statistics for a project.",
)
async def get_project_backlinks_overview(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> BacklinkOverviewResponse:
    """
    Get project backlink overview.

    Returns aggregated statistics from all backlink sources
    for the project.

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Backlink overview statistics.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    # Query for aggregated stats
    query = text("""
        SELECT
            COUNT(*) as total_backlinks,
            COUNT(DISTINCT source_domain) as unique_ref_domains,
            SUM(CASE WHEN flags->>'dofollow' = 'true' THEN 1 ELSE 0 END) as dofollow_count,
            SUM(CASE WHEN flags->>'dofollow' = 'false' OR flags->>'nofollow' = 'true' THEN 1 ELSE 0 END) as nofollow_count,
            MIN(first_seen) as first_seen,
            MAX(last_seen) as last_seen
        FROM project_backlinks
        WHERE project_id = :project_id
    """)

    result = await db.execute(query, {"project_id": str(project_id)})
    row = result.one_or_none()

    if row is None:
        return BacklinkOverviewResponse(
            total_backlinks=0,
            unique_ref_domains=0,
            dofollow_count=0,
            nofollow_count=0,
            first_seen=None,
            last_seen=None,
        )

    return BacklinkOverviewResponse(
        total_backlinks=row["total_backlinks"] or 0,
        unique_ref_domains=row["unique_ref_domains"] or 0,
        dofollow_count=row["dofollow_count"] or 0,
        nofollow_count=row["nofollow_count"] or 0,
        first_seen=row.get("first_seen"),
        last_seen=row.get("last_seen"),
    )


@projects_router.get(
    "/{project_id}/backlinks/anchors",
    response_model=AnchorListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project anchor distribution",
    description="Get anchor text distribution for all backlinks in a project.",
)
async def get_project_backlinks_anchors(
    project_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Maximum number of results"),
    ] = 100,
) -> AnchorListResponse:
    """
    Get project anchor distribution.

    Returns anchor text distribution from all backlink sources
    for the project.

    Args:
        project_id: Project UUID.
        db: Database session.
        current_user: Current authenticated user.
        limit: Maximum number of results.

    Returns:
        List of anchors with counts.
    """
    # Verify project ownership
    await get_user_project(db, project_id, current_user)

    query = text("""
        SELECT
            COALESCE(anchor, '') as anchor,
            COUNT(*) as count
        FROM project_backlinks
        WHERE project_id = :project_id
        GROUP BY anchor
        ORDER BY count DESC
        LIMIT :limit
    """)

    result = await db.execute(query, {"project_id": str(project_id), "limit": limit})
    rows = result.mappings().all()

    items = [
        AnchorResponse(
            anchor=row["anchor"],
            count=row["count"],
        )
        for row in rows
    ]

    return AnchorListResponse(items=items)
