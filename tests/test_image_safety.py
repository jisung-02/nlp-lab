"""Regression checks for failed image edits and bounded upload reads."""

import io

import pytest
from fastapi import Request, UploadFile
from PIL import Image
from sqlmodel import Session, select

from app.core.constants import HOME_HERO_IMAGE_POST_SLUG
from app.main import create_app
from app.models.post import Post
from app.routers import admin_member, admin_post
from app.services.image_service import ImageTooLargeError, optimize_image_bytes
from tests.helpers import extract_csrf_token
from tests.test_admin_auth import _login_cookies


def _hero_request():
    app = create_app()
    return Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("testserver", 80),
            "headers": [],
            "root_path": "",
            "path": "/",
            "router": app.router,
        }
    )


@pytest.mark.parametrize("operation", ["delete", "rename"])
def test_failed_upload_restores_existing_image(tmp_path, monkeypatch, operation):
    monkeypatch.setattr(admin_post, "_HERO_IMAGE_DIR", tmp_path)
    original = tmp_path / "original.png"
    original.write_bytes(b"original bytes")
    url = "/static/images/hero/original.png"
    _, error = admin_post._resolve_home_hero_content(
        request=_hero_request(),
        raw_content=url,
        hero_image_existing_urls=[url] if operation == "rename" else [],
        hero_image_filenames=["renamed.png"] if operation == "rename" else [],
        hero_image_remove_urls=[url] if operation == "delete" else [],
        hero_image_files=[UploadFile(filename="bad.txt", file=io.BytesIO(b"invalid"))],
    )
    assert error is not None
    assert original.read_bytes() == b"original bytes"
    assert not (tmp_path / "renamed.png").exists()


def test_invalid_post_after_image_edit_restores_files_and_database(
    app_and_engine, tmp_path, monkeypatch
):
    app, engine = app_and_engine
    monkeypatch.setattr(admin_post, "_HERO_IMAGE_DIR", tmp_path)
    original = tmp_path / "original.png"
    original.write_bytes(b"original bytes")
    url = "/static/images/hero/original.png"
    with Session(engine) as session:
        post = Post(title="Hero", slug=HOME_HERO_IMAGE_POST_SLUG, content=url)
        session.add(post)
        session.commit()
        post_id = post.id
    client = _login_cookies(app)
    csrf = extract_csrf_token(client.get("/admin/posts").text)
    response = client.post(
        f"/admin/posts/{post_id}/update",
        data={
            "title": "x" * 201,
            "slug": HOME_HERO_IMAGE_POST_SLUG,
            "content": url,
            "hero_image_remove_urls": url,
            "csrf_token": csrf,
        },
    )
    assert response.status_code == 400
    assert original.read_bytes() == b"original bytes"
    with Session(engine) as session:
        assert session.exec(select(Post)).one().content == url


class BoundedStream(io.BytesIO):
    def read(self, size=-1):
        assert 0 <= size <= 8 * 1024 * 1024 + 1
        return super().read(size)


def test_oversize_uploads_use_bounded_reads(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_post, "_HERO_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(admin_member, "_MEMBER_PHOTO_DIR", tmp_path)
    data = b"x" * (8 * 1024 * 1024 + 2)
    for save in (
        admin_member._save_member_photo_file,
        lambda upload: admin_post._save_hero_image_files([upload]),
    ):
        _, error = save(UploadFile(filename="large.png", file=BoundedStream(data)))
        assert error is not None
    assert not list(tmp_path.iterdir())


def test_image_pixel_budget_and_thumbnail(monkeypatch):
    image = Image.new("RGB", (1200, 600), "blue")
    content = io.BytesIO()
    image.save(content, format="JPEG", quality=95)
    optimized = optimize_image_bytes(content.getvalue(), max_dimension=300)
    with Image.open(io.BytesIO(optimized)) as small:
        assert max(small.size) <= 300
    monkeypatch.setattr("app.services.image_service._MAX_IMAGE_PIXELS", 100)
    with pytest.raises(ImageTooLargeError):
        optimize_image_bytes(content.getvalue())
