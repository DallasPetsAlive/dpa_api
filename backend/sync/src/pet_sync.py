import logging
import requests
from typing import Any, Dict, Optional

import boto3
import botocore
from cerealbox.dynamo import as_dynamodb_json, from_dynamodb_json


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

dynamodb_client = boto3.client("dynamodb")
table_name = "Pets"

secrets_client = boto3.client("secretsmanager")


def handler(_, __):
    # get the current list of pets
    current_pets = get_pets()

    logger.info("current_pets: %s", current_pets)

    shelterluv_pets = get_shelterluv_pets()
    shelterluv_pets = parse_shelterluv_pets(shelterluv_pets)

    current_shelterluv_pets = current_pets["shelterluv"]

    update_shelterluv_pets(shelterluv_pets, current_shelterluv_pets)


def get_pets() -> Optional[Dict[str, Any]]:
    pets = []

    try:
        response = dynamodb_client.scan(
            TableName=table_name,
            IndexName="SyncIndex",
        )

        if "Items" not in response:
            logger.error("No pets found")
            return None

        pets = response["Items"]

        while lastKey := response.get("LastEvaluatedKey"):
            response = dynamodb_client.scan(
                TableName=table_name,
                IndexName="SyncIndex",
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
            raise ValueError("Unknown pet source")

    return formatted_pets


def get_shelterluv_pets() -> Dict[str, Any]:
    response = secrets_client.get_secret_value(SecretId="shelterluv_api_key")
    shelterluv_api_key = response["SecretString"]

    headers = {"x-api-key": shelterluv_api_key}
    offset = 0
    animals_dict = {}

    while 1:
        url = (
            "https://www.shelterluv.com/api/v1/"
            + "animals?status_type=publishable&offset="
            + str(offset)
        )
        response = requests.get(url, headers=headers)

        # check http response code
        if response.status_code != 200:
            logger.error(
                "Invalid response code from Shelterluv {}".format(response.status_code)
            )
            raise ValueError("Invalid response code from Shelterluv")

        response_json = response.json()

        if response_json["success"] != 1:
            logger.error("Invalid response from Shelterluv {}".format(response_json))
            raise ValueError("Invalid response from Shelterluv")

        total_count = response_json["total_count"]

        if total_count == "0":
            logger.error("No animals found from Shelterluv")
            raise ValueError("No animals found from Shelterluv")

        # add each animal to the dict
        for animal in response_json["animals"]:
            id = animal["ID"]
            if id in animals_dict:
                continue

            animals_dict[id] = animal

        # check for more animals
        if response_json["has_more"]:
            offset += 100
        else:
            break

    # we should have all the animals now
    if str(animals_dict.__len__()) != str(total_count):
        logger.error("something went wrong, missing animals from shelterluv")

    return animals_dict


def parse_shelterluv_pets(animals_dict: Dict[str, Any]) -> Dict[str, Any]:
    animals = {}
    for id, animal in animals_dict.items():
        sl_id = "SL" + id
        size = animal["Size"].lower()

        if "small" in size:
            size = "small"
        elif "medium" in size:
            size = "medium"
        elif "large" in size and "x" not in size:
            size = "large"
        elif "large" in size:
            size = "xlarge"
        else:
            size = None

        animals[sl_id] = {
            "id": sl_id,
            "internalId": id,
            "name": animal["Name"],
            "species": animal["Type"].lower(),
            "sex": animal["Sex"].lower(),
            "ageMonths": animal["Age"],
            "breed": animal["Breed"],
            "color": animal["Color"],
            "description": animal["Description"],
            "size": size,
            "coverPhoto": animal["CoverPhoto"],
            "photos": animal["Photos"],
            "videos": animal["Videos"],
            "status": animal["Status"].lower(),
            "source": "shelterluv",
        }
    return animals


def update_shelterluv_pets(
    shelterluv_pets: Dict[str, Any], current_shelterluv_pets: Dict[str, Any]
) -> None:
    current_ids = [pet["id"] for pet in current_shelterluv_pets]

    for id, pet in shelterluv_pets.items():
        if id not in current_ids:
            add_pet(pet)
        else:
            # update_pet(pet)
            current_ids.remove(id)

    for id in current_ids:
        delete_pet(id)


def add_pet(pet: Dict[str, Any]) -> None:
    logger.info("Adding pet: %s", pet.get("id"))
    pet_ddb = as_dynamodb_json(pet)
    logger.info(pet_ddb)
    try:
        dynamodb_client.put_item(
            TableName=table_name,
            Item=pet_ddb["M"],
        )
    except botocore.exceptions.ClientError:
        logger.exception("client error")
        raise


def delete_pet(id: str) -> None:
    logger.info("Deleting pet: %s", id)
    try:
        dynamodb_client.delete_item(
            TableName=table_name,
            Key={
                "id": {"S": id},
            },
        )
    except botocore.exceptions.ClientError:
        logger.exception("client error")
        raise
