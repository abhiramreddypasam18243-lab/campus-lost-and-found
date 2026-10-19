import uuid


def can_access_resource(
    resource_owner_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
) -> bool:
    """Check if an actor has permission to access a private resource.

    Rule (SEC4 & AC-09):
    - Admins and moderators can access resources for operational review.
    - Standard users can ONLY access their own resources.
    - If unauthorized, caller MUST raise 404 (not 403) to prevent ID enumeration.
    """
    if actor_role in ("admin", "moderator"):
        return True
    return resource_owner_id == actor_id
