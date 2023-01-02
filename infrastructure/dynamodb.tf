resource "aws_dynamodb_table" "pets-table" {
  name           = "Pets"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "species"
    type = "S"
  }

  attribute {
    name = "internalId"
    type = "S"
  }

  global_secondary_index {
    name               = "SpeciesIndex"
    hash_key           = "species"
    projection_type    = "ALL"
  }

  global_secondary_index {
    name               = "SyncIndex"
    hash_key           = "internalId"
    projection_type    = "INCLUDE"
    non_key_attributes = ["source"]
  }
}
