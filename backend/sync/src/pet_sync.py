import json
import logging
import requests
from typing import Any, Dict, List, Optional

import boto3
import botocore
from cerealbox.dynamo import from_dynamodb_json


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb_client = boto3.client("dynamodb")
table_name = "Pets"

dynamodb_resource = boto3.resource("dynamodb")
pets_table = dynamodb_resource.Table(table_name)

secrets_client = boto3.client("secretsmanager")


def handler(_, __):
    # get the current list of pets
    current_pets = get_pets()

    api_shelterluv_pets = get_shelterluv_pets()
    api_shelterluv_pets = parse_shelterluv_pets(api_shelterluv_pets)

    dynamodb_shelterluv_pets = current_pets["shelterluv"]

    update_pets(api_shelterluv_pets, dynamodb_shelterluv_pets)

    api_airtable_pets = get_new_digs_pets()
    api_airtable_pets = parse_new_digs_pets(api_airtable_pets)

    dynamodb_airtable_pets = current_pets["airtable"]

    update_pets(api_airtable_pets, dynamodb_airtable_pets)


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
        try:
            sl_id = "SL" + id
            size = animal["Size"].lower()

            if "small" in size:
                size = "Small"
            elif "medium" in size:
                size = "Medium"
            elif "large" in size and "x" not in size:
                size = "Large"
            elif "large" in size:
                size = "Extra-Large"
            else:
                size = None

            age_months = animal["Age"]
            age = None
            if age_months <= 9:
                age = "Baby"
            elif age_months <= 24:
                age = "Young"
            elif age_months <= 96:
                age = "Adult"
            else:
                age = "Senior"

            adopt_link = "https://www.shelterluv.com/matchme/adopt/DPA-A-" + id

            video_link = None
            if len(animal["Videos"]) > 0:
                video_link = animal["Videos"][0].get("YoutubeUrl")

            species = animal["Type"].lower()
            if species == "rabbit, domestic":
                species = "rabbit"

            breed = animal["Breed"]
            if species == "pig":
                breed = "Pig"

            location = "DPA"
            if animal.get("CurrentLocation") and not animal.get("InFoster"):
                location = "HSDC"

            animals[sl_id] = {
                "id": sl_id,
                "internalId": id,
                "name": animal["Name"],
                "species": species,
                "sex": animal["Sex"],
                "age": age,
                "breed": breed,
                "color": animal["Color"],
                "description": animal["Description"],
                "size": size,
                "coverPhoto": animal["CoverPhoto"],
                "photos": animal["Photos"],
                "video": video_link,
                "status": animal["Status"].lower(),
                "source": "shelterluv",
                "adoptLink": adopt_link,
                "location": location,
            }
        except Exception:
            logger.exception(f"Error parsing shelterluv animal {animal}")
    return animals


def get_new_digs_pets() -> List[Dict[str, Any]]:
    response = secrets_client.get_secret_value(
        SecretId="airtable_personal_access_token"
    )
    airtable_api_key = response["SecretString"]

    response = secrets_client.get_secret_value(SecretId="airtable_base")
    airtable_base = response["SecretString"]

    url = "https://api.airtable.com/v0/" + airtable_base + "/Pets"
    headers = {"Authorization": "Bearer " + airtable_api_key}

    offset = None
    quit = False
    pets_list = []

    while not quit:
        params = {}
        if offset:
            params = {"offset": offset}

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != requests.codes.ok:
            logger.error("Airtable response: ")
            logger.error(response)
            logger.error("URL: " + url)
            logger.error("Headers: " + str(headers))
            return

        airtable_response = response.json()

        if not airtable_response.get("offset"):
            quit = True
        else:
            offset = airtable_response["offset"]

        pets_list += airtable_response["records"]

    return pets_list


def parse_new_digs_pets(animals_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    animals = {}
    for animal in animals_list:
        try:
            fields = animal["fields"]
            if fields["Status"] != "Published - Available for Adoption":
                continue

            at_id = "AT" + str(fields["Pet ID - do not edit"])
            size = fields["Pet Size"].lower()

            if "small" in size:
                size = "Small"
            elif "medium" in size:
                size = "Medium"
            elif "large" in size and "x" not in size:
                size = "Large"
            elif "large" in size:
                size = "Extra-Large"
            else:
                size = None

            breed = fields.get("Breed - Dog")
            color = fields.get("Color - Dog")
            if not breed:
                breed = fields.get("Breed - Cat")
                color = fields.get("Color - Cat")
            if not breed:
                breed = fields.get("Breed - Other Species")
                color = fields.get("Color - Other Species")

            photos = [photo.get("filename") for photo in fields.get("Pictures")]
            filename_map = fields.get("PictureMap-DoNotModify", "")
            filename_map = json.loads(filename_map)

            final_photos = []
            for photo in photos:
                if photo in filename_map:
                    final_photos.append(filename_map[photo])
                else:
                    final_photos.append(photo)

            photos = [
                "https://dpa-media.s3.us-east-2.amazonaws.com/new-digs-photos/"
                + animal["id"]
                + "/"
                + photo.replace(" ", "_")
                for photo in final_photos
            ]

            interested_in = "Dogs"
            species = fields.get("Pet Species")
            if species == "Cat":
                interested_in = "Cats"
            elif species != "Dog":
                interested_in = "Other"

            adopt_link = (
                "https://airtable.com/shrJ4gbiSeSsgJyd8?prefill_Applied%20For="
                + animal["id"]
                + "&prefill_I%27m+interested+in+adopting+this+type+of+pet:="
                + interested_in
            )

            animals[at_id] = {
                "id": at_id,
                "internalId": animal["id"],
                "name": fields["Pet Name"],
                "species": fields["Pet Species"].lower(),
                "sex": fields["Sex"],
                "age": fields["Pet Age"],
                "breed": breed,
                "color": color,
                "description": fields.get("Public Description"),
                "size": size,
                "coverPhoto": fields.get("ThumbnailURL", ""),
                "photos": photos,
                "status": "adoptable",
                "source": "airtable",
                "adoptLink": adopt_link,
                "video": fields.get("Youtube Video"),
                "location": "New Digs",
            }
        except Exception:
            logger.exception(f"Error parsing airtable animal {animal}")
    return animals


def update_pets(api_pets: Dict[str, Any], dynamodb_pets: Dict[str, Any]) -> None:
    deleted_pets = 0
    updated_pets = 0

    ids_to_delete = [pet["id"] for pet in dynamodb_pets]

    for ddb_pet in dynamodb_pets:
        if ddb_pet["id"] in api_pets:
            ids_to_delete.remove(ddb_pet["id"])

    with pets_table.batch_writer() as batch:
        for id in ids_to_delete:
            batch.delete_item(Key={"id": id})
            deleted_pets += 1

        for pet in api_pets.values():
            batch.put_item(Item=pet)
            updated_pets += 1

    logger.info("Deleted %s pets", deleted_pets)
    logger.info("Updated/added %s pets", updated_pets)

    assert updated_pets == len(api_pets)
