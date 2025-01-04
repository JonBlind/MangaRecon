import pytest
from unittest.mock import patch, MagicMock
from python_services.db_operations.db_manager import database_manager
import psycopg2

# Test that checks connection initalization
def test_initialization_success(mocker):
    mock_connect = mocker.patch("psycopg2.connect", autospec=True)
    mocker.patch("os.getenv", return_value="test_value")

    db_manager = database_manager()

    mock_connect.assert_called_once()
    assert db_manager.connection is not None

# Test to check connection properly fails
def test_initialization_failure(mocker):
    mocker.patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Connection failed"))
    mocker.patch("os.getenv", return_value="test_value")

    db_manager = database_manager()

    assert db_manager.connection is None

# Test the insert query constructor
def test_build_insert_query():
    db_manager = database_manager()
    table = "profile"
    data = {"user_id": "5", "username": "testuser", "email": "test@example.com", "password_hash": "passwordhash", "password_salt": "salt"}

    query, params = db_manager._build_insert_query(table, data)

    assert query is not None
    assert params == ("5", "testuser", "test@example.com", "passwordhash", "salt")
    assert "INSERT INTO" in str(query)

# Test the update query constructor
def test_build_update_query():
    db_manager = database_manager()
    table = "profile"
    data = {"username": "updateduser"}
    condition = "user_id = %s"

    query, params = db_manager._build_update_query(table, data, condition)

    assert query is not None
    assert params == ("updateduser",)
    assert "UPDATE" in str(query)

# Test the delete query constructor
def test_build_delete_query():
    db_manager = database_manager()
    table = "profile"
    condition = "user_id = %s"

    query, params = db_manager._build_delete_query(table, condition)

    assert query is not None
    assert params == ()
    assert "DELETE FROM" in str(query)

# Test query execution
def test_execute_query(mocker):
    mock_connection = MagicMock()
    mock_cursor = mock_connection.cursor.return_value.__enter__.return_value
    db_manager = database_manager()
    db_manager.connection = mock_connection

    mock_cursor.execute.return_value = None

    query = "SELECT * FROM profile WHERE user_id = %s"
    params = (1,)

    result = db_manager.execute_query(query, params)

    mock_cursor.execute.assert_called_once_with(query, params)
    mock_connection.commit.assert_called_once()
    assert result is True

# Test handling of connection errors
def test_connection_error(mocker):
    mocker.patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Connection failed"))
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "test" if key in ["DB_NAME", "DB_USER", "DB_PASSWORD"] else default)

    db_manager = database_manager()

    assert db_manager.connection is None
