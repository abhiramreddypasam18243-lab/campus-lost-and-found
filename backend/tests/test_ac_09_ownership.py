import uuid

from app.domain.access import can_access_resource


def test_ac_09_ownership_domain_logic() -> None:
    """AC-09 (SEC4): User B cannot access User A's resource; Moderators/Admins can."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    mod = uuid.uuid4()
    admin = uuid.uuid4()

    # User A accesses own resource -> True
    assert can_access_resource(resource_owner_id=user_a, actor_id=user_a, actor_role="user") is True

    # User B accesses User A's resource -> False (will trigger 404 in API router)
    assert can_access_resource(resource_owner_id=user_a, actor_id=user_b, actor_role="user") is False

    # Moderator accesses User A's resource -> True
    assert can_access_resource(resource_owner_id=user_a, actor_id=mod, actor_role="moderator") is True

    # Admin accesses User A's resource -> True
    assert can_access_resource(resource_owner_id=user_a, actor_id=admin, actor_role="admin") is True
