from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from vin_app.db import SessionLocal, VinRecord
import vin_app.models as model
from vin_app.http_client import http_client

app = FastAPI()


@app.post("/lookup", response_model=model.VinPostResponse)
async def lookup_vin(vin_request: model.VinPostRequest):
    db = SessionLocal()
    is_data_cached = False

    cached_vin = db.query(VinRecord).filter(VinRecord.vin == vin_request.vin).first()
    if cached_vin:
        is_data_cached = True
        return model.VinPostResponse(
            vin_requested=vin_request.vin,
            make=cached_vin.make,
            model=cached_vin.model,
            model_year=cached_vin.model_year,
            body_class=cached_vin.body_class,
            cached_result=is_data_cached,
        )

    try:
        vpic_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin_request.vin}?format=json"
        response = await http_client.get(vpic_url)
        response.raise_for_status()
        data = response.json()
    except (http_client.HttpError, http_client.JSONDecodeError, http_client.RequestException) as e:
        raise HTTPException(status_code=500, detail="Error occurred during VIN decoding") from e

    results = data.get("Results", [])
    filtered_data = {item["Variable"]: item["Value"] for item in results if item["Variable"] in key_attributes}

    new_vin = VinRecord(
        vin=vin_request.vin,
        make=filtered_data.get("Make"),
        model=filtered_data.get("Model"),
        model_year=filtered_data.get("Model Year"),
        body_class=filtered_data.get("Body Class"),
    )
    db.add(new_vin)
    db.commit()

    return model.VinPostResponse(
        vin_requested=vin_request.vin,
        make=new_vin.make,
        model=new_vin.model,
        model_year=new_vin.model_year,
        body_class=new_vin.body_class,
        cached_result=is_data_cached,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

