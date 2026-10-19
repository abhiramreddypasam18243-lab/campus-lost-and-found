import uuid

from app.services.notification import render_notification_content


def test_ac_71_notification_email_privacy_canaries() -> None:
    """AC-71: Match and claim emails contain no private details or claim evidence;

    handover code appears only for the approved claimant.
    """
    canary_private_details = "CANARY_SECRET_ENGRAVING_12345"
    canary_claim_evidence = "CANARY_SECRET_CLAIM_EVIDENCE_XYZ"
    handover_code = "SAFE-9876"

    # 1. Match notification
    match_payload = {
        "title": "Blue Umbrella",
        "category": "umbrella",
        "match_id": str(uuid.uuid4()),
        # Malicious / accidental injection of private details into event payload
        "private_details": canary_private_details,
    }
    match_subject, match_body = render_notification_content("match_suggested", match_payload)
    assert canary_private_details not in match_subject
    assert canary_private_details not in match_body

    # 2. Claim update notification
    claim_payload = {
        "found_title": "MacBook Pro",
        "claim_status": "approved",
        "claim_evidence": canary_claim_evidence,
    }
    claim_subject, claim_body = render_notification_content("claim_update", claim_payload)
    assert canary_claim_evidence not in claim_subject
    assert canary_claim_evidence not in claim_body

    # 3. Handover notification: for approved claimant, code appears
    handover_payload_claimant = {
        "found_title": "MacBook Pro",
        "handover_code": handover_code,
        "is_claimant": True,
    }
    _, claimant_body = render_notification_content("handover_ready", handover_payload_claimant)
    assert handover_code in claimant_body

    # For non-claimant (e.g. finder notification), handover code must NEVER appear
    handover_payload_finder = {
        "found_title": "MacBook Pro",
        "handover_code": handover_code,
        "is_claimant": False,
    }
    _, finder_body = render_notification_content("handover_ready", handover_payload_finder)
    assert handover_code not in finder_body
