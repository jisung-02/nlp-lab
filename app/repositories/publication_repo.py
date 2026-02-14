"""Database access helpers for publications."""

from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.models.publication import Publication


def list_publications(session: Session) -> Sequence[Publication]:
    """Return all publications sorted for admin listing."""

    return session.exec(
        select(Publication).order_by(col(Publication.year).desc(), col(Publication.id).desc())
    ).all()


def get_publication_by_id(session: Session, publication_id: int) -> Publication | None:
    """Return publication by primary key."""

    return session.get(Publication, publication_id)


def create_publication(session: Session, publication: Publication) -> Publication:
    """Persist a new publication."""

    session.add(publication)
    session.commit()
    session.refresh(publication)
    return publication


def update_publication(session: Session, publication: Publication) -> Publication:
    """Persist an updated publication."""

    session.add(publication)
    session.commit()
    session.refresh(publication)
    return publication


def delete_publication(session: Session, publication: Publication) -> None:
    """Hard-delete a publication."""

    session.delete(publication)
    session.commit()


def has_publications_for_project(session: Session, project_id: int) -> bool:
    """Return whether at least one publication references the project."""

    publication_id = session.exec(
        select(Publication.id).where(col(Publication.related_project_id) == project_id).limit(1)
    ).first()
    return publication_id is not None
