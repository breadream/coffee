from io import BytesIO
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import HTTPException
import pytest
import pyarrow.parquet as pq

from main import (
    fetch_data,
    process_result,
    remove_from_cache,
    add_to_cache,
    export_cache,
)
import vin_app.models as model
from vin_app.db import VinRecord


@pytest.mark.asyncio
async def test_fetch_data_happy_path():
    mock_http_client = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"Results": []}

    mock_http_client.get.return_value = mock_response

    with patch("main.http_client", mock_http_client):
        result = await fetch_data("testvinabcde12345")

    mock_http_client.get.assert_called_with(
        "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/testvinabcde12345?format=json"
    )
    assert result == {"Results": []}


@pytest.mark.asyncio
async def test_fetch_data_http_error():
    mock_http_client = AsyncMock()

    mock_http_client.get.side_effect = HTTPException(
        status_code=404, detail="Not found"
    )

    with patch("main.http_client", mock_http_client):
        with pytest.raises(HTTPException):
            await fetch_data("testvinabcde12345")


def test_process_result():
    data = {
        "Results": [
            {"Variable": "Make", "Value": "BMW"},
            {"Variable": "Model", "Value": "3"},
            {"Variable": "Model Year", "Value": "2023"},
            {"Variable": "Body Class", "Value": "Coupe"},
        ]
    }

    result = process_result(data)

    assert result == {
        "Make": "BMW",
        "Model": "3",
        "Model Year": "2023",
        "Body Class": "Coupe",
    }


def test_process_result_null_value():
    data = {
        "Results": [
            {"Variable": "Make", "Value": "BMW"},
            {"Variable": "Model", "Value": ""},
            {"Variable": "Model Year", "Value": "2023"},
            {"Variable": "Body Class", "Value": "Coupe"},
        ]
    }

    with pytest.raises(HTTPException) as exc_info:
        process_result(data)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "VIN not found"
    assert exc_info.value.headers == {
        "X-Error": "VIN doesn't exist or invalid VIN has been entered"
    }


@pytest.mark.asyncio
async def test_remove_from_cache(mock_session_dependency):
    mock_vin_delete_request = model.VinDeleteRequest(vin="testvinabcde12345")

    result = await remove_from_cache(
        vin_request=mock_vin_delete_request, db=mock_session_dependency
    )

    assert result.vin_requested == "testvinabcde12345"
    assert result.delete_success is True


@pytest.mark.asyncio
async def test_add_to_cache_existing_vin(mock_db_session_post):
    mock_vin_post_request = model.VinPostRequest(vin="testvinabcde12345")

    result = await add_to_cache(
        vin_request=mock_vin_post_request, db=mock_db_session_post
    )

    assert result.vin_requested == "testvinabcde12345"
    assert result.make == "BMW"
    assert result.model == "X5"
    assert result.model_year == "2022"
    assert result.body_class == "SUV"
    assert result.cached_result is True


@pytest.mark.asyncio
async def test_add_to_cache_new_vin(mock_db_session_no_data):
    mock_vin_post_request = model.VinPostRequest(vin="testvin12345abcde")

    with patch(
        "main.fetch_data",
        return_value={
            "Results": [
                {"Variable": "Make", "Value": "Audi"},
                {"Variable": "Model", "Value": "S7"},
                {"Variable": "Model Year", "Value": "2022"},
                {"Variable": "Body Class", "Value": "Sedan"},
            ]
        },
    ):
        result = await add_to_cache(
            vin_request=mock_vin_post_request, db=mock_db_session_no_data
        )

    assert result.vin_requested == "testvin12345abcde"
    assert result.make == "Audi"
    assert result.model == "S7"
    assert result.model_year == "2022"
    assert result.body_class == "Sedan"
    assert result.cached_result is False


@pytest.mark.asyncio
async def test_export_cache(mock_db_session):
    vin_records = [
        VinRecord(
            vin="VIN123", make="BMW", model="X5", model_year="2022", body_class="SUV"
        ),
        VinRecord(
            vin="VIN456", make="Audi", model="A4", model_year="2023", body_class="Sedan"
        ),
    ]

    for record in vin_records:
        mock_db_session.add(record)
    mock_db_session.commit()

    response = await export_cache(db=mock_db_session)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/octet-stream"
    assert (
        response.headers["Content-Disposition"]
        == "attachment; filename=vin_records.parquet"
    )
