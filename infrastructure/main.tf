terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "4.40.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2.0"
    }
  }

  backend "s3" {
    bucket  = "dallas-pets-alive-terraform"
    key     = "dpa_api.tfstate"
    region  = "us-east-2"
  }
}

data "aws_sns_topic" "default_alarms" {
  name = "Default_CloudWatch_Alarms_Topic"
}

resource "aws_secretsmanager_secret" "shelterluv_api_key" {
  name = "shelterluv_api_key"
}

resource "aws_secretsmanager_secret" "airtable_personal_access_token" {
  name = "airtable_personal_access_token"
}

resource "aws_secretsmanager_secret" "airtable_base" {
  name = "airtable_base"
}
