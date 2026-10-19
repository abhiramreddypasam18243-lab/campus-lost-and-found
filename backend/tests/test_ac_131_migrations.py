from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_ac_131_alembic_vector_extension_migration() -> None:
    """AC-131 (start): Verify Alembic migration enables pgvector extension on upgrade."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()

    assert len(heads) == 1, "There should be exactly one migration head"
    head_rev = script.get_revision(heads[0])
    assert head_rev is not None
    assert head_rev.revision == "0001_initial"

    # Verify migration file content contains vector extension management
    migration_file = Path(head_rev.path)
    content = migration_file.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector;" in content
    assert "DROP EXTENSION IF EXISTS vector;" in content
