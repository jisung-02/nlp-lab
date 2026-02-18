"""Publication domain services."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError
from sqlmodel import Session

from app.models.project import Project
from app.models.publication import Publication
from app.repositories import project_repo, publication_repo
from app.schemas.publication import PublicationCreateInput, PublicationUpdateInput


def parse_publication_create_input(
    *,
    title: str,
    title_en: str | None,
    authors: str,
    authors_en: str | None,
    venue: str,
    venue_en: str | None,
    year: str,
    link: str | None,
    related_project_id: str | None,
) -> PublicationCreateInput | None:
    """Return validated create payload or ``None``."""

    fallback_title = title_en.strip() if isinstance(title_en, str) else ""
    fallback_authors = authors_en.strip() if isinstance(authors_en, str) else ""
    fallback_venue = venue_en.strip() if isinstance(venue_en, str) else ""
    resolved_title = title.strip() or fallback_title
    resolved_authors = authors.strip() or fallback_authors
    resolved_venue = venue.strip() or fallback_venue

    try:
        return PublicationCreateInput.model_validate(
            {
                "title": resolved_title,
                "title_en": title_en,
                "authors": resolved_authors,
                "authors_en": authors_en,
                "venue": resolved_venue,
                "venue_en": venue_en,
                "year": year,
                "link": link,
                "related_project_id": related_project_id,
            }
        )
    except ValidationError:
        return None


def parse_publication_update_input(
    *,
    title: str,
    title_en: str | None,
    authors: str,
    authors_en: str | None,
    venue: str,
    venue_en: str | None,
    year: str,
    link: str | None,
    related_project_id: str | None,
) -> PublicationUpdateInput | None:
    """Return validated update payload or ``None``."""

    fallback_title = title_en.strip() if isinstance(title_en, str) else ""
    fallback_authors = authors_en.strip() if isinstance(authors_en, str) else ""
    fallback_venue = venue_en.strip() if isinstance(venue_en, str) else ""
    resolved_title = title.strip() or fallback_title
    resolved_authors = authors.strip() or fallback_authors
    resolved_venue = venue.strip() or fallback_venue

    try:
        return PublicationUpdateInput.model_validate(
            {
                "title": resolved_title,
                "title_en": title_en,
                "authors": resolved_authors,
                "authors_en": authors_en,
                "venue": resolved_venue,
                "venue_en": venue_en,
                "year": year,
                "link": link,
                "related_project_id": related_project_id,
            }
        )
    except ValidationError:
        return None


def list_publications(session: Session) -> Sequence[Publication]:
    """Return publications for admin listing."""

    return publication_repo.list_publications(session)


def list_projects_for_publications(session: Session) -> Sequence[Project]:
    """Return project options for publication linkage."""

    return project_repo.list_projects(session)


def create_publication(
    session: Session,
    input_data: PublicationCreateInput,
) -> tuple[Publication | None, str | None]:
    """Create a publication or return an error message."""

    if input_data.related_project_id is not None:
        related_project = project_repo.get_project_by_id(session, input_data.related_project_id)
        if related_project is None:
            return None, "연결할 프로젝트를 찾을 수 없습니다."

    publication = Publication(
        title=input_data.title,
        title_en=input_data.title_en,
        authors=input_data.authors,
        authors_en=input_data.authors_en,
        venue=input_data.venue,
        venue_en=input_data.venue_en,
        year=input_data.year,
        link=input_data.link,
        related_project_id=input_data.related_project_id,
    )
    return publication_repo.create_publication(session, publication), None


def update_publication(
    session: Session,
    publication_id: int,
    input_data: PublicationUpdateInput,
) -> tuple[Publication | None, str | None]:
    """Update a publication or return an error message."""

    publication = publication_repo.get_publication_by_id(session, publication_id)
    if publication is None:
        return None, "논문을 찾을 수 없습니다."

    if input_data.related_project_id is not None:
        related_project = project_repo.get_project_by_id(session, input_data.related_project_id)
        if related_project is None:
            return None, "연결할 프로젝트를 찾을 수 없습니다."

    publication.title = input_data.title
    publication.title_en = input_data.title_en
    publication.authors = input_data.authors
    publication.authors_en = input_data.authors_en
    publication.venue = input_data.venue
    publication.venue_en = input_data.venue_en
    publication.year = input_data.year
    publication.link = input_data.link
    publication.related_project_id = input_data.related_project_id

    return publication_repo.update_publication(session, publication), None


def delete_publication(session: Session, publication_id: int) -> str | None:
    """Delete a publication or return an error message."""

    publication = publication_repo.get_publication_by_id(session, publication_id)
    if publication is None:
        return "논문을 찾을 수 없습니다."

    publication_repo.delete_publication(session, publication)
    return None
