import logging

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


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/pet/{pet_id}")
def read_item(pet_id: int):
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


handler = Mangum(app, lifespan="off")
