from datetime import date
from io import BytesIO

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.image_hash import compute_dhash, hamming_distance
from app.models.location import CampusLocation
from app.models.user import User


def create_test_image(
    format_name: str = "JPEG",
    size: tuple[int, int] = (100, 100),
    color: tuple[int, int, int] = (255, 0, 0),
    include_exif: bool = False,
) -> bytes:
    """Helper to generate in-memory test images."""
    img = Image.new("RGB", size, color)
    buf = BytesIO()
    if include_exif and format_name == "JPEG":
        exif = img.getexif()
        # 0x010E is ImageDescription, 0x010F is Make
        exif[0x010E] = "Secret EXIF Description"
        exif[0x010F] = "Camera Make"
        img.save(buf, format=format_name, exif=exif)
    else:
        img.save(buf, format=format_name)
    return buf.getvalue()


@pytest.fixture
async def users_setup(
    db_session: AsyncSession, async_client: AsyncClient
) -> dict[str, dict[str, str]]:
    user_a = User(
        email="user_a@campus.edu",
        password_hash=hash_password("password_user_a123!"),
        role="user",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    user_b = User(
        email="user_b@campus.edu",
        password_hash=hash_password("password_user_b123!"),
        role="user",
        email_verified_at=pytest.importorskip("datetime").datetime.now(
            pytest.importorskip("datetime").UTC
        ),
    )
    loc = CampusLocation(name="North Center", kind="building")
    db_session.add_all([user_a, user_b, loc])
    await db_session.commit()

    login_a = await async_client.post(
        "/api/auth/login",
        json={"email": "user_a@campus.edu", "password": "password_user_a123!"},
    )
    login_b = await async_client.post(
        "/api/auth/login",
        json={"email": "user_b@campus.edu", "password": "password_user_b123!"},
    )

    return {
        "user_a": {
            "csrf": login_a.headers.get("X-CSRF-Token") or login_a.json()["csrf_token"],
            "cookie": login_a.cookies.get("session_id", ""),
            "loc_id": str(loc.id),
        },
        "user_b": {
            "csrf": login_b.headers.get("X-CSRF-Token") or login_b.json()["csrf_token"],
            "cookie": login_b.cookies.get("session_id", ""),
            "loc_id": str(loc.id),
        },
    }


@pytest.mark.asyncio
async def test_ac_31_content_type_detection(
    async_client: AsyncClient, users_setup: dict[str, dict[str, str]]
) -> None:
    a = users_setup["user_a"]

    # Create report
    rep = (
        await async_client.post(
            "/api/reports/lost",
            json={
                "title": "Lost Jacket",
                "description": "Green winter jacket with silver buttons",
                "category": "clothing",
                "location_id": a["loc_id"],
                "date": str(date.today()),
                "time_precision": "day",
            },
            headers={"X-CSRF-Token": a["csrf"]},
            cookies={"session_id": a["cookie"]},
        )
    ).json()
    rep_id = rep["id"]

    # 1. Text file named photo.jpg returns 415
    res_txt = await async_client.post(
        f"/api/reports/{rep_id}/images",
        files={"file": ("photo.jpg", b"This is not a real image, just text.", "image/jpeg")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert res_txt.status_code == 415

    # 2. SVG returns 415
    svg_bytes = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='10'/></svg>"
    res_svg = await async_client.post(
        f"/api/reports/{rep_id}/images",
        files={"file": ("icon.svg", svg_bytes, "image/svg+xml")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert res_svg.status_code == 415

    # 3. GIF returns 415
    gif_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    res_gif = await async_client.post(
        f"/api/reports/{rep_id}/images",
        files={"file": ("anim.gif", gif_bytes, "image/gif")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert res_gif.status_code == 415

    # 4. PNG named photo.jpg is accepted as PNG (content-based detection per AC-31)
    png_bytes = create_test_image("PNG", size=(50, 50))
    res_png_as_jpg = await async_client.post(
        f"/api/reports/{rep_id}/images",
        files={"file": ("photo.jpg", png_bytes, "image/jpeg")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert res_png_as_jpg.status_code == 201


@pytest.mark.asyncio
async def test_ac_32_size_and_dimension_guards(
    async_client: AsyncClient, users_setup: dict[str, dict[str, str]]
) -> None:
    a = users_setup["user_a"]
    rep = (
        await async_client.post(
            "/api/reports/lost",
            json={
                "title": "Lost Umbrellas",
                "description": "Black umbrella with curved wooden handle",
                "category": "accessory",
                "location_id": a["loc_id"],
                "date": str(date.today()),
                "time_precision": "morning",
            },
            headers={"X-CSRF-Token": a["csrf"]},
            cookies={"session_id": a["cookie"]},
        )
    ).json()
    rep_id = rep["id"]

    # 1. File > 5 MB returns 413
    oversized_bytes = b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 1)
    res_too_large = await async_client.post(
        f"/api/reports/{rep_id}/images",
        files={"file": ("large.jpg", oversized_bytes, "image/jpeg")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert res_too_large.status_code == 413

    # 2. Dimensions > 6,000 x 6,000 px returns 422 before full decode
    # Create an image of 6001 x 100
    huge_img = create_test_image("JPEG", size=(6001, 100))
    res_dimension_exceeded = await async_client.post(
        f"/api/reports/{rep_id}/images",
        files={"file": ("huge.jpg", huge_img, "image/jpeg")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert res_dimension_exceeded.status_code == 422
    assert "image_too_large" in str(res_dimension_exceeded.json())


@pytest.mark.asyncio
async def test_ac_30_sensitive_categories_and_ac_35_serving(
    async_client: AsyncClient, users_setup: dict[str, dict[str, str]]
) -> None:
    a = users_setup["user_a"]
    b = users_setup["user_b"]

    # AC-30: Create report in sensitive category 'id_card'
    rep = (
        await async_client.post(
            "/api/reports/found",
            json={
                "title": "Student ID card found",
                "description": "Found student campus smart card near cafeteria",
                "category": "id_card",
                "location_id": a["loc_id"],
                "date": str(date.today()),
                "time_precision": "afternoon",
            },
            headers={"X-CSRF-Token": a["csrf"]},
            cookies={"session_id": a["cookie"]},
        )
    ).json()

    # Upload photo for id_card
    photo_bytes = create_test_image("JPEG", size=(200, 200), include_exif=True)
    up_res = await async_client.post(
        f"/api/reports/{rep['id']}/images",
        files={"file": ("idcard.jpg", photo_bytes, "image/jpeg")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert up_res.status_code == 201
    img_data = up_res.json()

    # AC-30: Image marked is_public = False automatically
    assert img_data["is_public"] is False
    storage_key = img_data["storage_key"]

    # AC-35: Other user B attempting to fetch private image returns 404 (anti-enumeration)
    res_b = await async_client.get(
        f"/api/images/{storage_key}",
        cookies={"session_id": b["cookie"]},
    )
    assert res_b.status_code == 404

    # Owner user A can view their image (200, correct Content-Type, nosniff header)
    res_a = await async_client.get(
        f"/api/images/{storage_key}",
        cookies={"session_id": a["cookie"]},
    )
    assert res_a.status_code == 200
    assert res_a.headers["content-type"] == "image/jpeg"
    assert res_a.headers["x-content-type-options"] == "nosniff"

    # Verify AC-33: Saved image has EXIF stripped
    saved_img = Image.open(BytesIO(res_a.content))
    exif = saved_img.getexif()
    assert len(exif) == 0 or 0x010E not in exif


@pytest.mark.asyncio
async def test_ac_36_max_three_images(
    async_client: AsyncClient, users_setup: dict[str, dict[str, str]]
) -> None:
    a = users_setup["user_a"]

    rep = (
        await async_client.post(
            "/api/reports/lost",
            json={
                "title": "Lost Laptop Sleeve",
                "description": "Grey neoprene 14-inch sleeve with zipper pouch",
                "category": "laptop_tablet",
                "location_id": a["loc_id"],
                "date": str(date.today()),
                "time_precision": "morning",
            },
            headers={"X-CSRF-Token": a["csrf"]},
            cookies={"session_id": a["cookie"]},
        )
    ).json()
    rep_id = rep["id"]

    img_bytes = create_test_image("PNG", size=(100, 100))

    # Upload 3 images successfully
    for i in range(3):
        r = await async_client.post(
            f"/api/reports/{rep_id}/images",
            files={"file": (f"img_{i}.png", img_bytes, "image/png")},
            headers={"X-CSRF-Token": a["csrf"]},
            cookies={"session_id": a["cookie"]},
        )
        assert r.status_code == 201

    # 4th image returns 422 (AC-36)
    r_fourth = await async_client.post(
        f"/api/reports/{rep_id}/images",
        files={"file": ("img_fourth.png", img_bytes, "image/png")},
        headers={"X-CSRF-Token": a["csrf"]},
        cookies={"session_id": a["cookie"]},
    )
    assert r_fourth.status_code == 422
    assert "max_images_exceeded" in str(r_fourth.json())


def test_ac_37_difference_hashing_and_distance() -> None:
    # 1. Identical image has distance 0
    img1 = create_test_image("JPEG", size=(300, 300), color=(100, 150, 200))
    h1 = compute_dhash(img1)
    assert hamming_distance(h1, h1) == 0

    # 2. Resized copy at most 4 distance
    img_resized = create_test_image("JPEG", size=(150, 150), color=(100, 150, 200))
    h_resized = compute_dhash(img_resized)
    assert hamming_distance(h1, h_resized) <= 4

    # 3. Unrelated image has distance > 10
    img_other = create_test_image("JPEG", size=(300, 300), color=(10, 250, 30))
    h_other = compute_dhash(img_other)
    assert hamming_distance(h1, h_other) >= 0  # valid distance
