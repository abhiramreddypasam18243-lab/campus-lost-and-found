from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.matching import (
    DEFAULT_WEIGHTS,
    calculate_hybrid_score,
    calculate_text_score,
    calculate_time_score,
    determine_image_signal,
    generate_explanation,
    is_valid_candidate_pair,
    sort_candidates_deterministically,
)
from app.models.embeddings import ImageEmbedding, ModelRegistry, TextEmbedding
from app.models.matching import MatchCandidate, MatchFeedback
from app.models.report import ItemImage, ItemReport
from app.services.embeddings import CLIP_TEXT_MODEL_SUFFIX
from app.services.location import calculate_db_location_score
from app.services.notification import create_notification


def utc_now() -> datetime:
    return datetime.now(UTC)


def _dot_product(vec_a: list[float], vec_b: list[float]) -> float:
    return sum(a * b for a, b in zip(vec_a, vec_b, strict=False))


async def compute_matches_for_report(
    db: AsyncSession,
    report_id: uuid.UUID,
    weights: dict[str, float] | None = None,
    weights_version: str = "v1.0",
) -> list[MatchCandidate]:
    """Compute and persist multimodal match candidates for a given lost or found report (AC-51 to AC-65)."""
    target_stmt = select(ItemReport).where(ItemReport.id == report_id)
    target = (await db.execute(target_stmt)).scalar_one_or_none()
    if target is None or target.status != "open":
        return []

    is_lost = target.type == "lost"

    # Query candidate counterparts
    if is_lost:
        lost_report = target
        lower_bound = lost_report.window_start - timedelta(hours=6)
        upper_bound = lost_report.window_end + timedelta(days=30)

        cand_stmt = (
            select(ItemReport)
            .where(
                ItemReport.type == "found",
                ItemReport.status == "open",
                ItemReport.disposition.is_(None),
                ItemReport.reporter_id != lost_report.reporter_id,
                ItemReport.window_end >= lower_bound,
                ItemReport.window_start <= upper_bound,
            )
            .order_by(ItemReport.created_at.asc())
        )
        counterparts = list((await db.execute(cand_stmt)).scalars().all())
    else:
        found_report = target
        if found_report.disposition in ("reserved", "returned"):
            return []

        cand_stmt = (
            select(ItemReport)
            .where(
                ItemReport.type == "lost",
                ItemReport.status == "open",
                ItemReport.reporter_id != found_report.reporter_id,
                ItemReport.window_start <= found_report.window_end + timedelta(hours=6),
                ItemReport.window_end >= found_report.window_start - timedelta(days=30),
            )
            .order_by(ItemReport.created_at.asc())
        )
        counterparts = list((await db.execute(cand_stmt)).scalars().all())

    # Get active models for metadata recording
    active_reg_stmt = select(ModelRegistry).where(ModelRegistry.is_active.is_(True))
    active_models = list((await db.execute(active_reg_stmt)).scalars().all())
    model_versions = {m.model_type: f"{m.model_name}@{m.model_version}" for m in active_models}

    # Fetch dismissed pairs to honor permanent dismissal (AC-61)
    dismissed_stmt = select(MatchCandidate.lost_id, MatchCandidate.found_id).where(
        MatchCandidate.status == "dismissed"
    )
    dismissed_rows = (await db.execute(dismissed_stmt)).all()
    dismissed_pairs = {(r[0], r[1]) for r in dismissed_rows}

    persisted_candidates: list[MatchCandidate] = []

    for counterpart in counterparts:
        lost = target if is_lost else counterpart
        found = counterpart if is_lost else target

        # AC-56: Validate candidate constraints
        lost_dict = {
            "id": lost.id,
            "status": lost.status,
            "reporter_id": lost.reporter_id,
            "window_start": lost.window_start,
            "window_end": lost.window_end,
        }
        found_dict = {
            "id": found.id,
            "status": found.status,
            "reporter_id": found.reporter_id,
            "window_start": found.window_start,
            "window_end": found.window_end,
            "disposition": found.disposition,
        }
        if not is_valid_candidate_pair(lost_dict, found_dict, dismissed_pairs):
            continue

        # 1. Text signal (AC-51)
        lost_text_stmt = select(TextEmbedding).where(TextEmbedding.entity_id == lost.id)
        found_text_stmt = select(TextEmbedding).where(TextEmbedding.entity_id == found.id)
        lost_text_emb = (await db.execute(lost_text_stmt)).scalar_one_or_none()
        found_text_emb = (await db.execute(found_text_stmt)).scalar_one_or_none()

        # Every report has a title and description, so a missing text vector means its
        # embedding job has not run yet, not that the signal is unavailable. Skip the pair
        # until both exist: the later job re-scores it, so no premature score or notification
        # is produced from location and time alone.
        if lost_text_emb is None or found_text_emb is None:
            continue
        text_score: float | None = calculate_text_score(
            _dot_product(lost_text_emb.vector, found_text_emb.vector)
        )

        # 2. Image signal (AC-55)
        lost_img_stmt = (
            select(ImageEmbedding)
            .join(ItemImage, ImageEmbedding.entity_id == ItemImage.id)
            .where(ItemImage.report_id == lost.id)
        )
        found_img_stmt = (
            select(ImageEmbedding)
            .join(ItemImage, ImageEmbedding.entity_id == ItemImage.id)
            .where(ItemImage.report_id == found.id)
        )
        lost_img_embs = list((await db.execute(lost_img_stmt)).scalars().all())
        found_img_embs = list((await db.execute(found_img_stmt)).scalars().all())

        image_mode, has_image_signal = determine_image_signal(
            lost_has_photo=len(lost_img_embs) > 0,
            found_has_photo=len(found_img_embs) > 0,
        )

        image_score: float | None = None
        if has_image_signal:
            if image_mode == "image_to_image":
                max_cos = 0.0
                for l_emb in lost_img_embs:
                    for f_emb in found_img_embs:
                        if l_emb.vector is not None and f_emb.vector is not None:
                            cos = _dot_product(l_emb.vector, f_emb.vector)
                            if cos > max_cos:
                                max_cos = cos
                image_score = calculate_text_score(max_cos)
            else:
                # Text-to-image (spec 6.2): the CLIP text vector of the report without photos
                # against the other report's CLIP photo vectors, best pair. If that text vector
                # has not been computed yet the signal is missing (null), never guessed.
                text_side = found if lost_img_embs else lost
                photo_embs = lost_img_embs if lost_img_embs else found_img_embs
                clip_text_stmt = select(ImageEmbedding).where(
                    ImageEmbedding.entity_id == text_side.id,
                    ImageEmbedding.model_name.endswith(CLIP_TEXT_MODEL_SUFFIX),
                )
                clip_text_embs = list((await db.execute(clip_text_stmt)).scalars().all())
                if clip_text_embs:
                    image_score = calculate_text_score(
                        max(
                            _dot_product(t_emb.vector, p_emb.vector)
                            for t_emb in clip_text_embs
                            for p_emb in photo_embs
                        )
                    )

        # 3. Location signal (AC-18)
        location_score = await calculate_db_location_score(db, lost.location_id, found.location_id)

        # 4. Time signal (AC-52)
        time_score = calculate_time_score(
            lost.window_start, lost.window_end, found.window_start, found.window_end
        )

        # 5. Hybrid score & explanations (AC-53, AC-54, AC-59)
        signals = {
            "text": text_score,
            "image": image_score,
            "location": location_score,
            "time": time_score,
        }
        combined_score, score_bin, contributions = calculate_hybrid_score(
            signals, weights=weights or DEFAULT_WEIGHTS
        )

        # Time gap hours for plain-English explanation
        if found.window_start > lost.window_end:
            time_gap = (found.window_start - lost.window_end).total_seconds() / 3600.0
            is_after = True
        elif lost.window_start > found.window_end:
            time_gap = (lost.window_start - found.window_end).total_seconds() / 3600.0
            is_after = False
        else:
            time_gap = 0.0
            is_after = True

        explanations = generate_explanation(
            signals=signals,
            contributions=contributions,
            combined_score=combined_score,
            image_mode=image_mode,
            time_gap_hours=time_gap,
            is_time_after=is_after,
            location_score=location_score,
        )

        # Upsert MatchCandidate (AC-63, AC-64)
        cand_query = select(MatchCandidate).where(
            MatchCandidate.lost_id == lost.id,
            MatchCandidate.found_id == found.id,
            MatchCandidate.weights_version == weights_version,
        )
        existing_cand = (await db.execute(cand_query)).scalar_one_or_none()

        if existing_cand is not None:
            if existing_cand.status != "dismissed":
                existing_cand.text_score = text_score
                existing_cand.image_score = image_score
                existing_cand.location_score = location_score
                existing_cand.time_score = time_score
                existing_cand.combined_score = combined_score
                existing_cand.bin = score_bin
                existing_cand.explanation = explanations
                existing_cand.model_versions = model_versions
                existing_cand.updated_at = utc_now()
                persisted_candidates.append(existing_cand)
        else:
            new_cand = MatchCandidate(
                id=uuid.uuid4(),
                lost_id=lost.id,
                found_id=found.id,
                text_score=text_score,
                image_score=image_score,
                location_score=location_score,
                time_score=time_score,
                combined_score=combined_score,
                bin=score_bin,
                weights_version=weights_version,
                model_versions=model_versions,
                explanation=explanations,
                status="suggested",
            )
            db.add(new_cand)
            persisted_candidates.append(new_cand)

    await db.flush()

    # Each candidate must be tied to its own reports, not the loop's last counterpart.
    reports_by_id = {r.id: r for r in counterparts}
    reports_by_id[target.id] = target

    # Sort deterministically: score DESC, then found created_at ASC, then found ID ASC (AC-57)
    sortable = [
        {
            "candidate": c,
            "score": c.combined_score,
            "found_created_at": reports_by_id[c.found_id].created_at,
            "found_id": c.found_id,
        }
        for c in persisted_candidates
    ]
    sorted_dicts = sort_candidates_deterministically(sortable)
    ordered_candidates = [d["candidate"] for d in sorted_dicts]

    # AC-65: Notification created only for score >= 0.65 ranked in the top 3
    for cand in ordered_candidates[:3]:
        if cand.combined_score >= 0.65:
            # Notify the lost report owner
            lost_obj = reports_by_id[cand.lost_id]
            found_obj = reports_by_id[cand.found_id]
            event_key = f"match_suggested:{cand.lost_id}:{cand.found_id}"
            payload = {
                "category": found_obj.category,
                "title": found_obj.title,
                "found_id": str(cand.found_id),
                "lost_id": str(cand.lost_id),
                "score": cand.combined_score,
            }
            await create_notification(
                db=db,
                user_id=lost_obj.reporter_id,
                event_type="match_suggested",
                event_key=event_key,
                payload=payload,
            )

    return ordered_candidates


async def dismiss_candidate(
    db: AsyncSession, candidate_id: uuid.UUID, user_id: uuid.UUID, user_role: str = "user"
) -> MatchCandidate:
    """AC-61: Dismiss a match candidate permanently for the user."""
    stmt = select(MatchCandidate).options().where(MatchCandidate.id == candidate_id)
    candidate = (await db.execute(stmt)).scalar_one_or_none()
    if candidate is None:
        raise ValueError("candidate_not_found")

    # Verify authorization: only the reporter of the lost report or moderator/admin can dismiss
    lost_stmt = select(ItemReport).where(ItemReport.id == candidate.lost_id)
    lost_report = (await db.execute(lost_stmt)).scalar_one_or_none()
    if lost_report is None:
        raise ValueError("lost_report_not_found")

    if user_role not in ("moderator", "admin") and lost_report.reporter_id != user_id:
        raise ValueError("forbidden_or_not_found")

    candidate.status = "dismissed"
    candidate.updated_at = utc_now()

    feedback = MatchFeedback(
        id=uuid.uuid4(),
        candidate_id=candidate.id,
        user_id=user_id,
        action="dismissed",
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(candidate)
    return candidate
