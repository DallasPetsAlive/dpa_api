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
