from unittest.mock import MagicMock

import pytest

from vin_app.db import VinRecord


@pytest.fixture
def mock_db_session():
    # Create a mock database session
    mock_session = MagicMock()
    mock_vin_record = VinRecord(vin="testvinabcde12345")
    mock_session.query().filter().first.return_value = mock_vin_record
    return mock_session


@pytest.fixture
def mock_session_dependency(mock_db_session):
    # Create a mock session dependency override
    return MagicMock(return_value=mock_db_session)


@pytest.fixture
def mock_db_session_post():
    # Create a mock database session
    mock_session = MagicMock()
    mock_vin_record = VinRecord(
        vin="testvinabcde12345",
        make="BMW",
        model="X5",
        model_year="2022",
        body_class="SUV",
    )
    mock_session.query().filter().first.return_value = mock_vin_record
    return mock_session


@pytest.fixture
def mock_db_session_no_data():
    mock_session = MagicMock()
    mock_session.query().filter().first.return_value = None
    return mock_session
