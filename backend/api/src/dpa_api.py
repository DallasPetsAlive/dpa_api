import logging
from typing import Optional

import botocore
import boto3

from cerealbox.dynamo import from_dynamodb_json
from fastapi import FastAPI, HTTPException
from mangum import Mangum

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

app = FastAPI()

client = boto3.client("dynamodb")
table_name = "Pets"


@app.get("/pet/{pet_id}")
def get_pet(pet_id: int):
    try:
        response = client.get_item(
            TableName=table_name,
            Key={"petId": {"N": str(pet_id)}},
        )
    except botocore.exceptions.ClientError:
        logger.exception("client error")
    else:
        if pet := response.get("Item"):
            return from_dynamodb_json(pet)
        else:
            raise HTTPException(status_code=404, detail="Pet not found")


@app.get("/pets")
def get_pets(species: Optional[str] = None, api_fields: Optional[bool] = False):
    try:
        data = []
        if species:
            index_name = "SpeciesIndex"

            response = client.query(
                TableName=table_name,
                IndexName=index_name,
                KeyConditionExpression="species = :species",
                ExpressionAttributeValues={":species": {"S": species}},
            )

            if "Items" not in response:
                raise HTTPException(status_code=404, detail="No pets found")

            data = response["Items"]

            while lastKey := response.get("LastEvaluatedKey"):
                response = client.query(
                    TableName=table_name,
                    IndexName=index_name,
                    KeyConditionExpression="species = :species",
                    ExpressionAttributeValues={":species": {"S": species}},
                    ExclusiveStartKey=lastKey,
                )
                data.extend(response["Items"])
        else:
            response = client.scan(
                TableName=table_name,
            )

            if "Items" not in response:
                raise HTTPException(status_code=404, detail="No pets found")

            data = response["Items"]

            while lastKey := response.get("LastEvaluatedKey"):
                response = client.scan(
                    TableName=table_name,
                    ExclusiveStartKey=lastKey,
                )
                data.extend(response["Items"])

        formatted_data = []

        for item in data:
            formatted_data.append(from_dynamodb_json(item))

        if api_fields:
            trimmed_data = []
            for item in formatted_data:
                trimmed_data.append(
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "species": item.get("species"),
                        "sex": item.get("sex"),
                        "breed": item.get("breed"),
                        "color": item.get("color"),
                        "age": item.get("age"),
                    }
                )
            return trimmed_data

        return formatted_data
    except botocore.exceptions.ClientError:
        logger.exception("client error")
        raise


@app.middleware("http")
async def cors_handler(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


handler = Mangum(app, lifespan="off")
