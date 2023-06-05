from io import BytesIO
import logging

import httpx
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.openapi.docs import get_swagger_ui_html
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse

import vin_app.models as model
from vin_app.db import VinRecord, get_db


KEY_ATTRS = {"Make", "Model", "Model Year", "Body Class"}
ATTRS_COUNT = len(KEY_ATTRS)
app = FastAPI()
http_client = httpx.AsyncClient()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def fetch_data(vin: str) -> dict:
    """
    Fetch data from external API (vPIC)

    Args:
        vin (str): Vehicle Identification Number.

    Returns:
        dict: A dictionary with the vehicle data.
    """
    vpic_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
    try:
        # Make an asynchronous GET request to the vPIC API
        response = await http_client.get(vpic_url)
        response.raise_for_status()
        data = response.json()

        logger.info(f"Successfully decoded VIN: '{vin}' via vPIC API")
        return data
    except (
        httpx.HTTPError,
        httpx.RequestError,
    ) as e:
        logger.exception(f"Error occurred during VIN decoding for VIN: {vin}")
        raise HTTPException(
            status_code=500, detail="Error occurred during VIN decoding"
        ) from e


def process_result(data: dict) -> dict | None:
    """
    Filter out key attribute values from the raw data

    Args:
        data (dict): The input data dictionary, expected to have a 'Results' key with
                     data related to VINs.

    Returns:
        dict: A dictionary with filtered VIN data.
    """
    logger.debug("Processing VIN data...")
    results = data.get("Results", [])
    attr_filled_count = 0
    filtered_data = {}
    for item in results:
        # if a key attribute is found, populate the filtered_data dictionary
        if item["Variable"] in KEY_ATTRS:
            if item["Value"]:
                filtered_data[item["Variable"]] = item["Value"]
                attr_filled_count += 1
            else:
                # if 'null' is found for a key attribute, it implies the VIN data is not present or invalid.
                logger.warning(f"Empty value found for {item['Variable']}")
                raise HTTPException(
                    status_code=404,
                    detail="VIN not found",
                    headers={
                        "X-Error": "VIN doesn't exist or invalid VIN has been entered"
                    },
                )
            # if all required key attributes are populated, stop iteration and return the filtered data
            if attr_filled_count == ATTRS_COUNT:
                logger.debug("VIN data successfully processed")
                return filtered_data


@app.post("/lookup", response_model=model.VinPostResponse)
async def add_to_cache(
    vin_request: model.VinPostRequest, db: Session = Depends(get_db)
):
    """
    Endpoint to look up a VIN and add it to the database if not already present.

    Args:
        vin_request (model.VinPostRequest): The input VIN to be looked up.
        db (Session): The database session, injected via dependency injection.

    Returns:
        model.VinPostResponse: The response model containing VIN details.
    """
    logger.info("Received VIN lookup request")

    # Tracker to see data was found in cache.
    is_data_cached = False
    # Query the database for the VIN.
    cached_vin = db.query(VinRecord).filter(VinRecord.vin == vin_request.vin).first()
    # If the VIN is present in the cache, return it and update the is_data_cached flag.
    if cached_vin:
        logger.info("VIN found in cache")
        is_data_cached = True
        return model.VinPostResponse(
            vin_requested=vin_request.vin,
            make=cached_vin.make,
            model=cached_vin.model,
            model_year=cached_vin.model_year,
            body_class=cached_vin.body_class,
            cached_result=is_data_cached,
        )

    logger.info("Fetching data from external API")
    # If the VIN was not in the cache, fetch data from the external API.
    data = await fetch_data(vin_request.vin)
    filtered_data = process_result(data)

    # Create a new VIN record with the fetched data.
    logger.info("Creating new VIN record")
    new_vin = VinRecord(
        vin=vin_request.vin,
        make=filtered_data.get("Make"),
        model=filtered_data.get("Model"),
        model_year=filtered_data.get("Model Year"),
        body_class=filtered_data.get("Body Class"),
    )

    logger.info("Adding new VIN record to the cache")
    # Add the new VIN record to the database and commit the changes.
    db.add(new_vin)
    db.commit()

    # Return the new VIN data.
    return model.VinPostResponse(
        vin_requested=vin_request.vin,
        make=new_vin.make,
        model=new_vin.model,
        model_year=new_vin.model_year,
        body_class=new_vin.body_class,
        cached_result=is_data_cached,
    )


@app.delete("/remove", response_model=model.VinDeleteResponse)
async def remove_from_cache(
    vin_request: model.VinDeleteRequest, db: Session = Depends(get_db)
):
    """
    Endpoint to remove a VIN entry from the database if present.

    Args:
        vin_request (model.VinDeleteRequest): The request payload of the VIN to delete.
        db (Session): SQLAlchemy Session object for database transaction.

    Returns:
        model.VinDeleteResponse: A response model containing the VIN requested for deletion and the success status.
    """
    logger.info("Received VIN deletion request")

    # Query the database for the VIN requested for deletion.
    cached_vin = db.query(VinRecord).filter(VinRecord.vin == vin_request.vin).first()
    # If no record found, return a response indicating deletion was unsuccessful.
    if not cached_vin:
        logger.warning("VIN not found in the cache")
        return model.VinDeleteResponse(
            vin_requested=vin_request.vin, delete_success=False
        )

    logger.info("Deleting VIN record from the cache")
    # Delete the VIN record from the database and commit the transaction.
    db.delete(cached_vin)
    db.commit()

    logger.info("VIN record removed successfully")
    # Return a response indicating the deletion was successful.
    return model.VinDeleteResponse(vin_requested=vin_request.vin, delete_success=True)


@app.get("/export")
async def export_cache(db: Session = Depends(get_db)) -> Response:
    """
    Endpoint to export the entire database as a parquet binary file.

    Args:
        db (Session): SQLAlchemy Session object for database transactions, fetched from Depends(get_db).

    Returns:
        Response: FastAPI Response object containing the binary content of the parquet file.
    """
    logger.info("Exporting VIN records as Parquet file")

    # Fetch all VIN records from the database.
    vin_records = db.query(VinRecord).all()

    # Create a list of dictionaries, with each dictionary representing a VIN record.
    # This list will be used to create a DataFrame.
    data = [
        {
            "vin": record.vin,
            "make": record.make,
            "model": record.model,
            "model_year": record.model_year,
            "body_class": record.body_class,
        }
        for record in vin_records
    ]
    # Create a pandas DataFrame from the data.
    df = pd.DataFrame(data)

    # Convert DataFrame to Parquet format
    buffer = BytesIO()
    table = pa.Table.from_pandas(df)
    pq.write_table(table, buffer)

    # Prepare response with Parquet file
    response = Response(content=buffer.getvalue())
    # per https://www.rfc-editor.org/rfc/rfc2046.txt
    response.headers["Content-Type"] = "application/octet-stream"
    # treat the response as a downloadable file with the filename "vin_records.parquet"
    response.headers["Content-Disposition"] = "attachment; filename=vin_records.parquet"
    logger.info("Export completed successfully")

    return response


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Default endpoint that redirects the user to the Swagger UI.

    Returns:
        HTMLResponse: An HTMLResponse object that represents the Swagger UI page.
    """
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
