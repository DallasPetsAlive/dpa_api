resource "aws_dynamodb_table" "pets-table" {
  name           = "Pets"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "petId"

  attribute {
    name = "petId"
    type = "N"
  }

  attribute {
    name = "species"
    type = "S"
  }

  global_secondary_index {
    name               = "SpeciesIndex"
    hash_key           = "species"
    projection_type    = "ALL"
  }
}
