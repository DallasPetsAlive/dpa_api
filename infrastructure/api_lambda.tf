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
    }]
  })
}

resource "aws_iam_role_policy_attachment" "api_lambda_policy" {
  role       = aws_iam_role.api_lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "dynamodb_pets_get_list" {
  name = "dynamodb_pets_get_list"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "dynamodb:Query",
        "dynamodb:GetItem",
        "dynamodb:Scan",
      ]
      Effect = "Allow"
      Resource = [
        aws_dynamodb_table.pets-table.arn,
        "${aws_dynamodb_table.pets-table.arn}/index/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "db_lambda_policy" {
  role       = aws_iam_role.api_lambda_exec.name
  policy_arn = aws_iam_policy.dynamodb_pets_get_list.arn
}

data "archive_file" "lambda_layer" {
  type = "zip"

  source_dir  = "${path.module}/layer/"
  output_path = "${path.module}/layer.zip"
}

resource "aws_s3_object" "lambda_layer" {
  bucket = aws_s3_bucket.api_lambda_bucket.id

  key    = "layer.zip"
  source = data.archive_file.lambda_layer.output_path

  # uncomment this to update layer in s3
  # etag = filemd5(data.archive_file.lambda_layer.output_path)
}

resource "aws_lambda_layer_version" "lambda_layer" {
  layer_name = "api_layer"

  s3_bucket = aws_s3_bucket.api_lambda_bucket.id
  s3_key    = aws_s3_object.lambda_layer.key

  compatible_runtimes = ["python3.8"]

  # source_code_hash = data.archive_file.lambda_layer.output_base64sha256
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = "${aws_api_gateway_rest_api.dpa_api.id}"
  parent_id   = "${aws_api_gateway_rest_api.dpa_api.root_resource_id}"
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = "${aws_api_gateway_rest_api.dpa_api.id}"
  resource_id   = "${aws_api_gateway_resource.proxy.id}"
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id = "${aws_api_gateway_rest_api.dpa_api.id}"
  resource_id = "${aws_api_gateway_method.proxy.resource_id}"
  http_method = "${aws_api_gateway_method.proxy.http_method}"

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "${aws_lambda_function.dpa_api_lambda.invoke_arn}"
}

resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "dpa_api_errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = "1"
  treat_missing_data  = "notBreaching"

  alarm_actions = [
    data.aws_sns_topic.default_alarms.arn,
  ]

  dimensions = {
    FunctionName = aws_lambda_function.dpa_api_lambda.function_name
  }
}
