from botocore.stub import Stubber

import dpa_api

def test_get_pet():
    with Stubber(dpa_api.client) as stubber:
        # Set up a stubbed response
        response = {
            "Item": {
                "id": {"S": "1"},
                "name": {"S": "Fido"},
                "species": {"S": "Dog"},
                "breed": {"S": "Golden Retriever"},
                "age": {"N": "2"},
            }
        }
        expected_params = {
            "TableName": dpa_api.table_name,
            "Key": {"petId": {"N": "1"}},
        }
        stubber.add_response("get_item", response, expected_params)

        # Call the service, which will send the request to the mocked instance
        response = dpa_api.get_pet(1)

        # If no error is raised, then assertion passes
        assert response == {
            "id": "1",
            "name": "Fido",
            "species": "Dog",
            "breed": "Golden Retriever",
            "age": 2,
        }

        stubber.assert_no_pending_responses()


def test_list_pets():
    with Stubber(dpa_api.client) as stubber:
        # Set up a stubbed response
        response = {
            "Items": [
                {
                    "id": {"S": "1"},
                    "name": {"S": "Fido"},
                    "species": {"S": "Dog"},
                    "breed": {"S": "Golden Retriever"},
                    "age": {"N": "2"},
                },
                {
                    "id": {"S": "2"},
                    "name": {"S": "Garfield"},
                    "species": {"S": "Cat"},
                    "breed": {"S": "Tabby"},
                    "age": {"N": "3"},
                },
            ]
        }
        expected_params = {"TableName": dpa_api.table_name}
        stubber.add_response("scan", response, expected_params)

        # Call the service, which will send the request to the mocked instance
        response = dpa_api.get_pets()

        # If no error is raised, then assertion passes
        assert response == [
            {
                "id": "1",
                "name": "Fido",
                "species": "Dog",
                "breed": "Golden Retriever",
                "age": 2,
            },
            {
                "id": "2",
                "name": "Garfield",
                "species": "Cat",
                "breed": "Tabby",
                "age": 3,
            },
        ]

        stubber.assert_no_pending_responses()


def test_list_pets_species():
    with Stubber(dpa_api.client) as stubber:
        # Set up a stubbed response
        response = {
            "Items": [
                {
                    "id": {"S": "1"},
                    "name": {"S": "Fido"},
                    "species": {"S": "Dog"},
                    "breed": {"S": "Golden Retriever"},
                    "age": {"N": "2"},
                },
                {
                    "id": {"S": "3"},
                    "name": {"S": "Petunia"},
                    "species": {"S": "Dog"},
                    "breed": {"S": "Beagle"},
                    "age": {"N": "3"},
                },
            ]
        }
        expected_params = {
            "TableName": "Pets",
            "IndexName": "SpeciesIndex",
            "KeyConditionExpression": "species = :species",
            "ExpressionAttributeValues": {":species": {"S": "Dog"}},
        }
        stubber.add_response("query", response, expected_params)

        # Call the service, which will send the request to the mocked instance
        response = dpa_api.get_pets("Dog")

        # If no error is raised, then assertion passes
        assert response == [
            {
                "id": "1",
                "name": "Fido",
                "species": "Dog",
                "breed": "Golden Retriever",
                "age": 2,
            },
            {
                "id": "3",
                "name": "Petunia",
                "species": "Dog",
                "breed": "Beagle",
                "age": 3,
            },
        ]

        stubber.assert_no_pending_responses()
