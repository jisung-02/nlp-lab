"""Database access helpers for projects."""

from __future__ import annotations

from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.models.project import Project


def list_projects(session: Session) -> Sequence[Project]:
    """Return all projects sorted for admin listing."""

    return session.exec(
        select(Project).order_by(col(Project.created_at).desc(), col(Project.id).desc())
    ).all()


def get_project_by_id(session: Session, project_id: int) -> Project | None:
    """Return project by primary key."""

    return session.get(Project, project_id)


def get_project_by_slug(session: Session, slug: str) -> Project | None:
    """Return project by unique slug."""

    return session.exec(select(Project).where(col(Project.slug) == slug)).first()


def create_project(session: Session, project: Project) -> Project:
    """Persist a new project."""

    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def update_project(session: Session, project: Project) -> Project:
    """Persist an updated project."""

    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project: Project) -> None:
    """Hard-delete a project."""

    session.delete(project)
    session.commit()
