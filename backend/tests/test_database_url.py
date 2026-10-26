from app.db.database import normalize_database_url


def test_managed_postgres_url_uses_installed_psycopg_driver():
    url = normalize_database_url("postgresql://app:secret@db.example:5432/interviewos")

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db.example"
    assert url.database == "interviewos"


def test_legacy_postgres_scheme_uses_installed_psycopg_driver():
    url = normalize_database_url("postgres://app:secret@db.example:5432/interviewos")

    assert url.drivername == "postgresql+psycopg"


def test_explicit_other_driver_is_preserved():
    url = normalize_database_url("sqlite+pysqlite:///:memory:")

    assert url.drivername == "sqlite+pysqlite"
