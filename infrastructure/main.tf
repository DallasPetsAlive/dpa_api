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

resource "aws_apigatewayv2_api" "dpa_api" {
  name          = "dpa_api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "lambda" {
  api_id = aws_apigatewayv2_api.dpa_api.id

  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gw.arn

    format = jsonencode({
      requestId               = "$context.requestId"
      sourceIp                = "$context.identity.sourceIp"
      requestTime             = "$context.requestTime"
      protocol                = "$context.protocol"
      httpMethod              = "$context.httpMethod"
      resourcePath            = "$context.resourcePath"
      routeKey                = "$context.routeKey"
      status                  = "$context.status"
      responseLength          = "$context.responseLength"
      integrationErrorMessage = "$context.integrationErrorMessage"
      }
    )
  }
}

resource "aws_apigatewayv2_integration" "dpa_api" {
  api_id = aws_apigatewayv2_api.dpa_api.id

  integration_uri    = aws_lambda_function.dpa_api_lambda.invoke_arn
  integration_type   = "AWS_PROXY"
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "get_pet" {
  api_id = aws_apigatewayv2_api.dpa_api.id

  route_key = "GET /pet/{pet_id}"
  target    = "integrations/${aws_apigatewayv2_integration.dpa_api.id}"
}

resource "aws_apigatewayv2_route" "get_root" {
  api_id = aws_apigatewayv2_api.dpa_api.id

  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.dpa_api.id}"
}

resource "aws_cloudwatch_log_group" "api_gw" {
  name = "/aws/api_gw/${aws_apigatewayv2_api.dpa_api.name}"

  retention_in_days = 30
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dpa_api_lambda.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.dpa_api.execution_arn}/*/*"
}

data "archive_file" "lambda_api" {
  type = "zip"

  source_dir  = "${path.module}/../backend/api/src"
  output_path = "${path.module}/api.zip"
}

resource "aws_s3_bucket" "api_lambda_bucket" {
  bucket = "dpa-api-lambda"
}

resource "aws_s3_object" "lambda_api" {
  bucket = aws_s3_bucket.api_lambda_bucket.id

  key    = "api.zip"
  source = data.archive_file.lambda_api.output_path

  etag = filemd5(data.archive_file.lambda_api.output_path)
}

resource "aws_lambda_function" "dpa_api_lambda" {
  function_name = "DPA-API"

  s3_bucket = aws_s3_bucket.api_lambda_bucket.id
  s3_key    = aws_s3_object.lambda_api.key

  runtime = "python3.8"
  handler = "dpa_api.handler"

  source_code_hash = data.archive_file.lambda_api.output_base64sha256

  role = aws_iam_role.api_lambda_exec.arn

  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
  ]
}

resource "aws_cloudwatch_log_group" "dpa_api_lambda_log_group" {
  name = "/aws/lambda/${aws_lambda_function.dpa_api_lambda.function_name}"

  retention_in_days = 30
}

resource "aws_iam_role" "api_lambda_exec" {
  name = "api_lambda_exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Sid    = ""
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_lambda_policy" {
  role       = aws_iam_role.api_lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "archive_file" "lambda_layer" {
  type = "zip"

  source_dir  = "${path.module}/../venv/"
  output_path = "${path.module}/layer.zip"
}

resource "aws_s3_object" "lambda_layer" {
  bucket = aws_s3_bucket.api_lambda_bucket.id

  key    = "layer.zip"
  source = data.archive_file.lambda_layer.output_path

  etag = filemd5(data.archive_file.lambda_layer.output_path)
}

resource "aws_lambda_layer_version" "lambda_layer" {
  layer_name = "api_layer"

  s3_bucket = aws_s3_bucket.api_lambda_bucket.id
  s3_key    = aws_s3_object.lambda_layer.key

  compatible_runtimes = ["python3.8"]

  source_code_hash = data.archive_file.lambda_layer.output_base64sha256
}
