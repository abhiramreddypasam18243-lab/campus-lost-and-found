"""Endpoints the web client needs (spec 9 and 11): own reports, CSRF refresh, profile,
claim form (D-20), handover desk list, verification email and the email outbox."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.security import hash_token
from app.models.claims import Claim
from app.models.handover import Handover
from app.models.location import CampusLocation
from app.models.notifications import Notification
from app.models.report import ItemReport
from app.models.user import Session, User
from app.services import mailer
from app.services.outbox import deliver_pending_emails

settings = get_settings()
CANARY = "CANARY_PRIVATE_DETAIL_5f2c"

SessionFactory = async_sessionmaker(
    bind=create_async_engine(settings.DATABASE_URL, poolclass=NullPool),
    class_=AsyncSession,
    expire_on_commit=False,
)


async def make_user(db: AsyncSession, email: str, role: str = "user") -> tuple[User, str, str]:
    user = User(
        email=email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fakehash",
        role=role,
        status="active",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()
    raw_sid, raw_csrf = f"sess_{uuid.uuid4()}", f"csrf_{uuid.uuid4()}"
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_token(raw_sid),
            csrf_token_hash=hash_token(raw_csrf),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    await db.commit()
    return user, raw_sid, raw_csrf


def as_user(client: AsyncClient, sid: str) -> AsyncClient:
    client.cookies.set("session_id", sid)
    return client


async def make_report(
    db: AsyncSession, reporter: User, kind: str = "found", status: str = "open", **kw: Any
) -> ItemReport:
    loc = CampusLocation(name=f"Library {uuid.uuid4().hex[:6]}", kind="building")
    db.add(loc)
    await db.flush()
    now = datetime.now(UTC)
    report = ItemReport(
        type=kind,
        status=status,
        title=kw.get("title", "Blue steel water bottle"),
        description="Dark blue insulated bottle with a dented base",
        category="bottle",
        location_id=loc.id,
        reporter_id=reporter.id,
        window_start=now - timedelta(hours=2),
        window_end=now - timedelta(hours=1),
        time_precision="exact",
        private_details=CANARY,
        verification_prompts=kw.get("prompts", ["What sticker is inside the lid?"]),
    )
    db.add(report)
    await db.commit()
    return report


@pytest.mark.asyncio
async def test_reports_mine_returns_only_own_reports(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    alice, sid_a, _ = await make_user(db_session, "alice@campus.edu")
    bob, _, _ = await make_user(db_session, "bob@campus.edu")
    mine = await make_report(db_session, alice, kind="lost", title="Alice lost flask")
    await make_report(db_session, bob, title="Bob found bottle")

    res = await as_user(async_client, sid_a).get("/api/reports/mine")
    assert res.status_code == 200
    assert [r["id"] for r in res.json()] == [str(mine.id)]

    async_client.cookies.clear()
    assert (await async_client.get("/api/reports/mine")).status_code == 401


@pytest.mark.asyncio
async def test_csrf_refresh_rotates_the_session_token(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, sid, old_csrf = await make_user(db_session, "carol@campus.edu")
    client = as_user(async_client, sid)

    res = await client.get("/api/auth/csrf")
    assert res.status_code == 200
    new_csrf = res.json()["csrf_token"]
    assert new_csrf != old_csrf

    body = {"notify_match_email": False}
    stale = await client.patch("/api/me", json=body, headers={"X-CSRF-Token": old_csrf})
    assert stale.status_code == 403
    fresh = await client.patch("/api/me", json=body, headers={"X-CSRF-Token": new_csrf})
    assert fresh.status_code == 200
    assert fresh.json()["notify_match_email"] is False

    async_client.cookies.clear()
    assert (await async_client.get("/api/auth/csrf")).status_code == 401


@pytest.mark.asyncio
async def test_patch_me_rejects_unknown_fields(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, sid, csrf = await make_user(db_session, "dave@campus.edu")
    res = await as_user(async_client, sid).patch(
        "/api/me", json={"role": "admin"}, headers={"X-CSRF-Token": csrf}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_claim_form_shows_prompts_but_never_private_details(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    finder, sid_f, _ = await make_user(db_session, "finder@campus.edu")
    _, sid_o, _ = await make_user(db_session, "owner@campus.edu")
    found = await make_report(db_session, finder, prompts=["What sticker is inside the lid?", " "])
    pending = await make_report(db_session, finder, status="pending_review")

    res = await as_user(async_client, sid_o).get(f"/api/found/{found.id}/claim-form")
    assert res.status_code == 200
    data = res.json()
    assert data["verification_prompts"] == ["What sticker is inside the lid?"]
    assert set(data) == {"found_id", "title", "category", "building", "verification_prompts"}
    assert CANARY not in res.text

    assert (await async_client.get(f"/api/found/{pending.id}/claim-form")).status_code == 404
    # The finder cannot claim their own item.
    res_own = await as_user(async_client, sid_f).get(f"/api/found/{found.id}/claim-form")
    assert res_own.status_code == 404


@pytest.mark.asyncio
async def test_handover_desk_list_is_staff_only_and_has_no_code(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    finder, _, _ = await make_user(db_session, "finder2@campus.edu")
    claimant, sid_c, _ = await make_user(db_session, "claimant@campus.edu")
    _, sid_m, _ = await make_user(db_session, "mod@campus.edu", role="moderator")
    found = await make_report(db_session, finder, status="reserved")
    claim = Claim(found_id=found.id, claimant_id=claimant.id, evidence="x" * 25, status="approved")
    db_session.add(claim)
    await db_session.flush()
    hmac_value = "ab" * 32
    db_session.add(
        Handover(
            claim_id=claim.id,
            code_hmac=hmac_value,
            issued_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=48),
        )
    )
    await db_session.commit()

    assert (await as_user(async_client, sid_c).get("/api/mod/handovers")).status_code == 403

    res = await as_user(async_client, sid_m).get("/api/mod/handovers")
    assert res.status_code == 200
    [item] = res.json()
    assert item["claim_id"] == str(claim.id)
    assert item["attempts_left"] == 5
    assert item["is_locked"] is False
    assert hmac_value not in res.text
    assert "code" not in " ".join(item)


@pytest.mark.asyncio
async def test_ac_02_registration_emails_a_working_verification_link(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[str, str, str]] = []

    async def fake_send(to: str, subject: str, body: str, message_id: str | None = None) -> None:
        sent.append((to, subject, body))

    monkeypatch.setattr(mailer, "send_email", fake_send)
    res = await async_client.post(
        "/api/auth/register",
        json={"email": "newbie@campus.edu", "password": "a-long-enough-password"},
    )
    assert res.status_code == 201
    [(to, _, body)] = sent
    assert to == "newbie@campus.edu"
    match = re.search(r"#/verify\?token=([A-Za-z0-9_\-%]+)", body)
    assert match is not None

    verify = await async_client.post("/api/auth/verify-email", json={"token": match.group(1)})
    assert verify.status_code == 200
    again = await async_client.post("/api/auth/verify-email", json={"token": match.group(1)})
    assert again.status_code == 410


@pytest.mark.asyncio
async def test_ac_69_70_72_outbox_delivery(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _, _ = await make_user(db_session, "eve@campus.edu")
    rows = {
        "ok": Notification(
            user_id=user.id,
            event_type="claim_update",
            event_key="k-ok",
            payload={"found_title": "Bottle", "claim_status": "approved"},
            email_queued=True,
            message_id="<k-ok@campus.edu>",
        ),
        "optout": Notification(
            user_id=user.id,
            event_type="match_suggested",
            event_key="k-optout",
            payload={"title": "Bottle", "category": "bottle"},
            email_queued=False,
            message_id="<k-optout@campus.edu>",
        ),
        "fail": Notification(
            user_id=user.id,
            event_type="claim_update",
            event_key="k-fail",
            payload={"found_title": "Bag", "claim_status": "rejected"},
            email_queued=True,
            message_id="<k-fail@campus.edu>",
        ),
    }
    db_session.add_all(rows.values())
    await db_session.commit()

    sent: list[str | None] = []

    async def fake_send(to: str, subject: str, body: str, message_id: str | None = None) -> None:
        if "Bag" in subject:
            raise ConnectionRefusedError
        sent.append(message_id)

    monkeypatch.setattr("app.services.outbox.send_email", fake_send)
    await deliver_pending_emails(SessionFactory)

    assert sent == ["<k-ok@campus.edu>"]
    db_session.expire_all()
    by_key = {
        n.event_key: n for n in (await db_session.execute(select(Notification))).scalars().all()
    }
    assert by_key["k-ok"].status == "sent"
    assert by_key["k-optout"].status == "in_app_only"
    assert by_key["k-fail"].status == "pending"
    assert by_key["k-fail"].attempts == 1
    assert by_key["k-fail"].last_error == "ConnectionRefusedError"
