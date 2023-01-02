import pytest
from botocore import exceptions
from botocore.stub import Stubber

from ..src import pet_sync


def test_get_pets():
    with Stubber(pet_sync.dynamodb_client) as stub:
        first_scan_response = {
            "Items": [
                {
                    "source": {"S": "shelterluv"},
                    "name": {"S": "Socks"},
                },
                {
                    "source": {"S": "airtable"},
                    "name": {"S": "Fido"},
                },
            ],
            "LastEvaluatedKey": {
                "source": {"S": "airtable"},
                "name": {"S": "Fido"},
            },
        }
        first_expected_params = {
            "TableName": "Pets",
            "IndexName": "SyncIndex",
        }
        stub.add_response("scan", first_scan_response, first_expected_params)

        second_scan_response = {
            "Items": [
                {
                    "source": {"S": "airtable"},
                    "name": {"S": "Petey"},
                },
                {
                    "source": {"S": "shelterluv"},
                    "name": {"S": "Joey"},
                },
            ],
        }
        second_expected_params = {
            "TableName": "Pets",
            "IndexName": "SyncIndex",
            "ExclusiveStartKey": {
                "source": {"S": "airtable"},
                "name": {"S": "Fido"},
            },
        }

        stub.add_response("scan", second_scan_response, second_expected_params)

        pets = pet_sync.get_pets()

        stub.assert_no_pending_responses()

        assert pets == {
            "shelterluv": [
                {
                    "source": "shelterluv",
                    "name": "Socks",
                },
                {
                    "source": "shelterluv",
                    "name": "Joey",
                },
            ],
            "airtable": [
                {
                    "source": "airtable",
                    "name": "Fido",
                },
                {
                    "source": "airtable",
                    "name": "Petey",
                },
            ],
        }


def test_get_pets_bad_source():
    with Stubber(pet_sync.dynamodb_client) as stub:
        scan_response = {
            "Items": [
                {
                    "source": {"S": "blah"},
                    "name": {"S": "Socks"},
                },
                {
                    "source": {"S": "airtable"},
                    "name": {"S": "Fido"},
                },
            ],
        }
        expected_params = {
            "TableName": "Pets",
            "IndexName": "SyncIndex",
        }
        stub.add_response("scan", scan_response, expected_params)

        with pytest.raises(ValueError):
            pet_sync.get_pets()

        stub.assert_no_pending_responses()


def test_get_pets_dynamodb_error():
    with Stubber(pet_sync.dynamodb_client) as stub:
        stub.add_client_error("scan")

        with pytest.raises(exceptions.ClientError):
            pet_sync.get_pets()

        stub.assert_no_pending_responses()


def test_get_pets_none_found():
    with Stubber(pet_sync.dynamodb_client) as stub:
        scan_response = {}
        expected_params = {
            "TableName": "Pets",
            "IndexName": "SyncIndex",
        }
        stub.add_response("scan", scan_response, expected_params)

        assert pet_sync.get_pets() == None

        stub.assert_no_pending_responses()
