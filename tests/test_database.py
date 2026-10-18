from sqlalchemy import text
from backend.app.core.database import check_db_connection, Base
from backend.app.models.job import Job
from backend.app.models.history import ExecutionHistory
from backend.app.models.audit import AuditLog


def test_database_table_metadata():
    """Verify that ORM models define all required tables and primary keys."""
    table_names = Base.metadata.tables.keys()
    assert "jobs" in table_names
    assert "execution_history" in table_names
    assert "audit_logs" in table_names

    # Check primary keys
    assert "id" in Base.metadata.tables["jobs"].columns
    assert "history_id" in Base.metadata.tables["execution_history"].columns
    assert "audit_id" in Base.metadata.tables["audit_logs"].columns


def test_session_connectivity(db_session):
    """Verify that the test database session can execute raw queries."""
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1
