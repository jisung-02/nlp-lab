"""Project domain services."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError
from sqlmodel import Session

from app.models.project import Project
from app.repositories import project_repo, publication_repo
from app.schemas.project import ProjectCreateInput, ProjectUpdateInput


def parse_project_create_input(
    *,
    title: str,
    title_en: str | None,
    slug: str,
    summary: str,
    summary_en: str | None,
    description: str,
    description_en: str | None,
    status: str,
    start_date: str,
    end_date: str | None,
) -> ProjectCreateInput | None:
    """Return validated create payload or ``None``."""

    fallback_title = title_en.strip() if isinstance(title_en, str) else ""
    fallback_summary = summary_en.strip() if isinstance(summary_en, str) else ""
    fallback_description = description_en.strip() if isinstance(description_en, str) else ""
    resolved_title = title.strip() or fallback_title
    resolved_summary = summary.strip() or fallback_summary
    resolved_description = description.strip() or fallback_description

    try:
        return ProjectCreateInput.model_validate(
            {
                "title": resolved_title,
                "title_en": title_en,
                "slug": slug,
                "summary": resolved_summary,
                "summary_en": summary_en,
                "description": resolved_description,
                "description_en": description_en,
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
    except ValidationError:
        return None


def parse_project_update_input(
    *,
    title: str,
    title_en: str | None,
    slug: str,
    summary: str,
    summary_en: str | None,
    description: str,
    description_en: str | None,
    status: str,
    start_date: str,
    end_date: str | None,
) -> ProjectUpdateInput | None:
    """Return validated update payload or ``None``."""

    fallback_title = title_en.strip() if isinstance(title_en, str) else ""
    fallback_summary = summary_en.strip() if isinstance(summary_en, str) else ""
    fallback_description = description_en.strip() if isinstance(description_en, str) else ""
    resolved_title = title.strip() or fallback_title
    resolved_summary = summary.strip() or fallback_summary
    resolved_description = description.strip() or fallback_description

    try:
        return ProjectUpdateInput.model_validate(
            {
                "title": resolved_title,
                "title_en": title_en,
                "slug": slug,
                "summary": resolved_summary,
                "summary_en": summary_en,
                "description": resolved_description,
                "description_en": description_en,
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
    except ValidationError:
        return None


def list_projects(session: Session) -> Sequence[Project]:
    """Return projects for admin listing."""

    return project_repo.list_projects(session)


def create_project(
    session: Session,
    input_data: ProjectCreateInput,
) -> tuple[Project | None, str | None]:
    """Create a project or return an error message."""

    if project_repo.get_project_by_slug(session, input_data.slug) is not None:
        return None, "이미 사용 중인 slug입니다."

    project = Project(
        title=input_data.title,
        title_en=input_data.title_en,
        slug=input_data.slug,
        summary=input_data.summary,
        summary_en=input_data.summary_en,
        description=input_data.description,
        description_en=input_data.description_en,
        status=input_data.status,
        start_date=input_data.start_date,
        end_date=input_data.end_date,
    )
    return project_repo.create_project(session, project), None


def update_project(
    session: Session,
    project_id: int,
    input_data: ProjectUpdateInput,
) -> tuple[Project | None, str | None]:
    """Update a project or return an error message."""

    project = project_repo.get_project_by_id(session, project_id)
    if project is None:
        return None, "프로젝트를 찾을 수 없습니다."

    duplicate_project = project_repo.get_project_by_slug(session, input_data.slug)
    if duplicate_project is not None and duplicate_project.id != project.id:
        return None, "이미 사용 중인 slug입니다."

    project.title = input_data.title
    project.title_en = input_data.title_en
    project.slug = input_data.slug
    project.summary = input_data.summary
    project.summary_en = input_data.summary_en
    project.description = input_data.description
    project.description_en = input_data.description_en
    project.status = input_data.status
    project.start_date = input_data.start_date
    project.end_date = input_data.end_date

    return project_repo.update_project(session, project), None


def delete_project(session: Session, project_id: int) -> str | None:
    """Delete a project or return an error message."""

    project = project_repo.get_project_by_id(session, project_id)
    if project is None:
        return "프로젝트를 찾을 수 없습니다."

    if publication_repo.has_publications_for_project(session, project_id):
        return "연결된 논문이 있어 프로젝트를 삭제할 수 없습니다."

    project_repo.delete_project(session, project)
    return None
