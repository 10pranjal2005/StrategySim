
import sqlite3

from pathlib import Path
from flask import current_app, g


# ---------------------------------------------------------
# DATABASE PATH RESOLUTION
# ---------------------------------------------------------

def get_database_path():
    """
    Returns the absolute path of the SQLite database.

    Relative paths are resolved from the project root.
    """

    database_path = Path(
        current_app.config["DATABASE_PATH"]
    )

    if not database_path.is_absolute():
        project_root = Path(__file__).resolve().parents[2]
        database_path = project_root / database_path

    return database_path.resolve()


# ---------------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------------

def get_db():
    """
    Returns the current request's SQLite connection.

    A single connection is reused during the current
    Flask application context.
    """

    if "db" not in g:

        database_path = get_database_path()

        database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        connection = sqlite3.connect(
            database_path,
            detect_types=sqlite3.PARSE_DECLTYPES
        )

        # Return database rows as dictionary-like objects.
        connection.row_factory = sqlite3.Row

        # Enforce foreign key constraints.
        connection.execute("PRAGMA foreign_keys = ON")

        # Configure SQLite busy timeout.
        connection.execute("PRAGMA busy_timeout = 5000")

        g.db = connection

    return g.db


# ---------------------------------------------------------
# CLOSE DATABASE CONNECTION
# ---------------------------------------------------------

def close_db(error=None):
    """
    Closes the database connection at the end of
    the Flask application context.
    """

    database = g.pop("db", None)

    if database is not None:
        database.close()


# ---------------------------------------------------------
# DATABASE INITIALIZATION HOOK
# ---------------------------------------------------------

def init_app(app):
    """
    Registers database cleanup with the Flask application.
    """

    app.teardown_appcontext(close_db)


# ---------------------------------------------------------
# DATABASE TRANSACTION HELPER
# ---------------------------------------------------------

def execute_transaction(callback):
    """
    Executes a group of database operations inside
    a transaction.

    Parameters:
        callback: Function receiving the database connection.

    Returns:
        Result returned by the callback.

    Rolls back changes if an exception occurs.
    """

    database = get_db()

    try:
        with database:
            result = callback(database)

        return result

    except Exception:
        raise
