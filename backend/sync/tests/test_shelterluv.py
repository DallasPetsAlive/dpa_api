import json
import os
import pytest

import requests_mock
from botocore import exceptions
from botocore.stub import Stubber

from ..src import pet_sync

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def test_get_shelterluv_pets():

    sample_pets = None
    pets = None

    with open(os.path.join(__location__, "resources/sample_shelterluv.json"), "r") as f:
        sample_pets = f.read()

    with Stubber(pet_sync.secrets_client) as stub:
        expected_params = {
            "SecretId": "shelterluv_api_key",
        }
        stub.add_response("get_secret_value", {"SecretString": "abc"}, expected_params)

        with requests_mock.Mocker() as requests_mocker:
            requests_mocker.get(
                "https://www.shelterluv.com/api/v1/animals?status_type=publishable&offset=0",
                text=sample_pets,
            )

            pets = pet_sync.get_shelterluv_pets()

            stub.assert_no_pending_responses()
            assert requests_mocker.call_count == 1

    sample_animals = json.loads(sample_pets)["animals"]
    assert pets == {
        sample_animals[0]["ID"]: sample_animals[0],
        sample_animals[1]["ID"]: sample_animals[1],
        sample_animals[2]["ID"]: sample_animals[2],
        sample_animals[3]["ID"]: sample_animals[3],
        sample_animals[4]["ID"]: sample_animals[4],
        sample_animals[5]["ID"]: sample_animals[5],
    }


def test_get_shelterluv_pets_bad_response():

    with Stubber(pet_sync.secrets_client) as stub:
        expected_params = {
            "SecretId": "shelterluv_api_key",
        }
        stub.add_response("get_secret_value", {"SecretString": "abc"}, expected_params)

        with requests_mock.Mocker() as requests_mocker:
            requests_mocker.get(
                "https://www.shelterluv.com/api/v1/animals?status_type=publishable&offset=0",
                status_code=500,
            )

            with pytest.raises(ValueError):
                pet_sync.get_shelterluv_pets()

            stub.assert_no_pending_responses()
            assert requests_mocker.call_count == 1


def test_get_shelterluv_pets_not_success():

    sample_pets = None

    with open(os.path.join(__location__, "resources/sample_shelterluv.json"), "r") as f:
        sample_pets = f.read()

    sample_pets = json.loads(sample_pets)
    sample_pets["success"] = 0
    sample_pets = json.dumps(sample_pets)

    with Stubber(pet_sync.secrets_client) as stub:
        expected_params = {
            "SecretId": "shelterluv_api_key",
        }
        stub.add_response("get_secret_value", {"SecretString": "abc"}, expected_params)

        with requests_mock.Mocker() as requests_mocker:
            requests_mocker.get(
                "https://www.shelterluv.com/api/v1/animals?status_type=publishable&offset=0",
                text=sample_pets,
            )

            with pytest.raises(ValueError):
                pet_sync.get_shelterluv_pets()

            stub.assert_no_pending_responses()
            assert requests_mocker.call_count == 1


def test_get_shelterluv_pets_no_animals():

    sample_pets = None

    with open(os.path.join(__location__, "resources/sample_shelterluv.json"), "r") as f:
        sample_pets = f.read()

    sample_pets = json.loads(sample_pets)
    sample_pets["total_count"] = "0"
    sample_pets = json.dumps(sample_pets)

    with Stubber(pet_sync.secrets_client) as stub:
        expected_params = {
            "SecretId": "shelterluv_api_key",
        }
        stub.add_response("get_secret_value", {"SecretString": "abc"}, expected_params)

        with requests_mock.Mocker() as requests_mocker:
            requests_mocker.get(
                "https://www.shelterluv.com/api/v1/animals?status_type=publishable&offset=0",
                text=sample_pets,
            )

            with pytest.raises(ValueError):
                pet_sync.get_shelterluv_pets()

            stub.assert_no_pending_responses()
            assert requests_mocker.call_count == 1


def test_parse_shelterluv_pets():

    sample_pets = None
    pets = None

    with open(os.path.join(__location__, "resources/sample_shelterluv.json"), "r") as f:
        sample_pets = f.read()

    sample_animals = json.loads(sample_pets)["animals"]

    pets = {
        sample_animals[0]["ID"]: sample_animals[0],
        sample_animals[1]["ID"]: sample_animals[1],
        sample_animals[2]["ID"]: sample_animals[2],
        sample_animals[3]["ID"]: sample_animals[3],
        sample_animals[4]["ID"]: sample_animals[4],
        sample_animals[5]["ID"]: sample_animals[5],
    }

    pets_parsed = pet_sync.parse_shelterluv_pets(pets)

    for petId in pets_parsed:
        original_id = petId[2:]
        assert original_id in pets

        pet = pets_parsed[petId]
        expected_pet = pets[original_id]

        assert pet["name"] == expected_pet["Name"]
        assert pet["description"] == expected_pet["Description"]
        assert pet["breed"] == expected_pet["Breed"]
        assert pet["ageMonths"] == expected_pet["Age"]
        assert pet["species"] == expected_pet["Type"].lower()
        assert pet["photos"] == expected_pet["Photos"]
        assert pet["coverPhoto"] == expected_pet["CoverPhoto"]
        assert pet["source"] == "shelterluv"
        assert pet["size"] in ["small", "medium", "large", "xlarge", None]
