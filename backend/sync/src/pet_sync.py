import logging
from typing import Any, Dict, Optional

import boto3
import botocore
from cerealbox.dynamo import as_dynamodb_json, from_dynamodb_json


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

client = boto3.client("dynamodb")
table_name = "Pets"


def handler(_, __):
    # get the current list of pets
    current_pets = get_pets()

    logger.info("current_pets: %s", current_pets)


def get_pets() -> Optional[Dict[str, Any]]:
    pets = []

    try:
        response = client.scan(
            TableName=table_name,
            IndexName="SyncIndex",
        )

        if "Items" not in response:
            logger.error("No pets found")
            return None

        pets = response["Items"]

        while lastKey := response.get("LastEvaluatedKey"):
            response = client.scan(
                TableName=table_name,
                ExclusiveStartKey=lastKey,
            )
            pets.extend(response["Items"])
    except botocore.exceptions.ClientError:
        logger.exception("client error")
        raise

    formatted_pets = {
        "shelterluv": [],
        "airtable": [],
    }

    for pet in pets:
        formatted_pet = from_dynamodb_json(pet)
        if formatted_pet.get("source") == "shelterluv":
            formatted_pets["shelterluv"].append(formatted_pet)
        elif formatted_pet.get("source") == "airtable":
            formatted_pets["airtable"].append(formatted_pet)
        else:
            logger.error("Unknown pet source: %s", formatted_pet.get("source"))

    return formatted_pets
