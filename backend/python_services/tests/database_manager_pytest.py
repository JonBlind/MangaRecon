import pytest
from unittest.mock import patch, MagicMock
from backend.python_services.db_operations.db_manager import DatabaseManager
import psycopg2
import os


@pytest.fixture
def db_manager():
    """Create a DatabaseManager with a mocked connection"""
    with patch('psycopg2.connect') as mock_connect:
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection
        manager = DatabaseManager(
            db_name=os.getenv("DB_NAME_TEST"),
            db_user=os.getenv("DB_USER_TEST"),
            db_password=os.getenv("DB_PASSWORD_TEST"),
            db_host=os.getenv("DB_HOST_TEST"),
            db_port=os.getenv("DB_PORT_TEST")
        )
        return manager

@pytest.fixture
def mock_cursor(db_manager):
    """Create a mock cursor"""
    mock_cursor = MagicMock()
    db_manager.connection.cursor.return_value.__enter__.return_value = mock_cursor
    return mock_cursor

# Test that checks connection initalization
def test_initialization_success(mocker):
    mock_connect = mocker.patch("psycopg2.connect", autospec=True)
    mocker.patch("os.getenv", return_value="test_value")

    db_manager = DatabaseManager(os.getenv("DB_NAME_TEST"), os.getenv("DB_USER_TEST"), os.getenv("DB_PASSWORD_TEST"), os.getenv("DB_HOST_TEST"), os.getenv("DB_PORT_TEST"))

    mock_connect.assert_called_once()
    assert db_manager.connection is not None

# Test to check connection properly fails
def test_initialization_failure(mocker):
    mocker.patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Connection failed"))
    mocker.patch("os.getenv", return_value="test_value")

    db_manager = DatabaseManager(os.getenv("DB_NAME_TEST"), os.getenv("DB_USER_TEST"), os.getenv("DB_PASSWORD_TEST"), os.getenv("DB_HOST_TEST"), os.getenv("DB_PORT_TEST"))

    assert db_manager.connection is None

# Test the insert query constructor
def test_build_insert_query():
    db_manager = DatabaseManager(os.getenv("DB_NAME_TEST"), os.getenv("DB_USER_TEST"), os.getenv("DB_PASSWORD_TEST"), os.getenv("DB_HOST_TEST"), os.getenv("DB_PORT_TEST"))
    table = "profile"
    data = {"user_id": "5", "username": "testuser", "email": "test@example.com", "password_hash": "passwordhash", "password_salt": "salt"}

    query, params = db_manager._build_insert_query(table, data)

    assert query is not None
    assert params == ("5", "testuser", "test@example.com", "passwordhash", "salt")
    assert "INSERT INTO" in str(query)

# Test the update query constructor
def test_build_update_query():
    db_manager = DatabaseManager(os.getenv("DB_NAME_TEST"), os.getenv("DB_USER_TEST"), os.getenv("DB_PASSWORD_TEST"), os.getenv("DB_HOST_TEST"), os.getenv("DB_PORT_TEST"))
    table = "profile"
    data = {"username": "updateduser"}
    condition = "user_id = %s"

    query, params = db_manager._build_update_query(table, data, condition)

    assert query is not None
    assert params == ("updateduser",)
    assert "UPDATE" in str(query)

# Test the delete query constructor
def test_build_delete_query():
    db_manager = DatabaseManager(os.getenv("DB_NAME_TEST"), os.getenv("DB_USER_TEST"), os.getenv("DB_PASSWORD_TEST"), os.getenv("DB_HOST_TEST"), os.getenv("DB_PORT_TEST"))
    table = "profile"
    condition = "user_id = %s"

    query, params = db_manager._build_delete_query(table, condition)

    assert query is not None
    assert params == ()
    assert "DELETE FROM" in str(query)

# Test the input_data method
def test_input_data(db_manager, mock_cursor):
    table = "profile"
    data = {
        "user_id": 5,
        "username": "JohnDoe",
        "displayname": "DaRealJonDoe",
        "email": "john@example.com",
        "password_hash": "SuperSecurePasswordNeverWillBeCrackedForReal"
    }


    db_manager.input_data(data, table)

    mock_cursor.execute.assert_called_once()

    call_args = mock_cursor.execute.call_args
    query = call_args[0][0]
    params = call_args[0][1]

    query_str = str(query)
    
    assert "INSERT INTO" in query_str
    assert "profile" in query_str
    assert "VALUES" in query_str
    
    for column in data.keys():
        assert column in query_str
    
    placeholder_count = query_str.count("Placeholder()")
    assert placeholder_count == len(data), f"Expected {len(data)} placeholders, found {placeholder_count}"
    
    assert params == tuple(data.values()), f"Expected parameters {tuple(data.values())}, got {params}"
    
    db_manager.connection.commit.assert_called_once()


# Test the modify_data method
def test_modify_data(db_manager, mock_cursor):

    table = "profile"
    data = {
        "username": "UpdatedJohnDoe",
        "displayname": "UpdatedDaRealJonDoe",
        "email": "updated.john@example.com"
    }
    condition = "user_id = 5"

    db_manager.modify_data(data, table, condition)

    mock_cursor.execute.assert_called_once()

    call_args = mock_cursor.execute.call_args
    query = call_args[0][0]
    params = call_args[0][1]

    query_str = str(query)

    assert "UPDATE" in query_str
    assert "profile" in query_str
    assert "SET" in query_str
    assert "WHERE" in query_str
    
    for column in data.keys():
        assert column in query_str
    
    placeholder_count = query_str.count("Placeholder()")
    assert placeholder_count == len(data), f"Expected {len(data)} placeholders, found {placeholder_count}"
    
    assert params == tuple(data.values()), f"Expected parameters {tuple(data.values())}, got {params}"
    
    db_manager.connection.commit.assert_called_once()

# Test the remove_data method
def test_remove_data(db_manager, mock_cursor):

    table = "profile"
    condition = "user_id = 5"

    db_manager.remove_data(table, condition)

    mock_cursor.execute.assert_called_once()

    call_args = mock_cursor.execute.call_args
    query = call_args[0][0]
    params = call_args[0][1]

    query_str = str(query)
    
    assert "DELETE FROM" in query_str
    assert "profile" in query_str
    assert "WHERE" in query_str
    assert "user_id = 5" in query_str
    
    assert params == (), f"Expected no parameters, got {params}"
    
    db_manager.connection.commit.assert_called_once()

# Test the fetch_data method
def test_fetch_data(db_manager, mock_cursor):
    """Test fetching data from a table"""

    query = "SELECT * FROM profile WHERE user_id = %s"
    params = (5,)
    expected_results = [
        (5, "JohnDoe", "DaRealJonDoe", "john@example.com", "SuperSecurePasswordNeverWillBeCrackedForReal")
    ]
    mock_cursor.fetchall.return_value = expected_results


    results = db_manager.fetch_data(query, params)


    mock_cursor.execute.assert_called_once_with(query, params)
    mock_cursor.fetchall.assert_called_once()
    assert results == expected_results