resource "aws_secretsmanager_secret" "shelterluv_api_key" {
  name = "shelterluv_api_key"
}

data "aws_secretsmanager_secret_version" "shelterluv_api_key" {
  secret_id = aws_secretsmanager_secret.shelterluv_api_key.id
}

data "archive_file" "lambda_api_sync" {
  type = "zip"

  source_dir  = "${path.module}/../backend/sync/src"
  output_path = "${path.module}/sync.zip"
}

resource "aws_s3_object" "lambda_api_sync" {
  bucket = aws_s3_bucket.api_lambda_bucket.id

  key    = "sync.zip"
  source = data.archive_file.lambda_api_sync.output_path

  etag = filemd5(data.archive_file.lambda_api_sync.output_path)
}

resource "aws_iam_role" "sync_lambda_exec" {
  name = "sync_lambda_exec"

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

resource "aws_iam_role_policy_attachment" "sync_lambda_policy" {
  role       = aws_iam_role.sync_lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "dynamodb_pets_sync" {
  name = "dynamodb_pets_sync"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "dynamodb:DeleteItem",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
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

resource "aws_iam_role_policy_attachment" "db_sync_lambda_policy" {
  role       = aws_iam_role.sync_lambda_exec.name
  policy_arn = aws_iam_policy.dynamodb_pets_sync.arn
}

resource "aws_iam_policy" "api_sync_get_shelterluv_api_key" {
  name = "api_sync_get_shelterluv_api_key"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Effect = "Allow"
      Resource = [
        aws_secretsmanager_secret.shelterluv_api_key.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "secrets_lambda_policy" {
  role       = aws_iam_role.sync_lambda_exec.name
  policy_arn = aws_iam_policy.api_sync_get_shelterluv_api_key.arn
}

resource "aws_lambda_function" "dpa_api_lambda_sync" {
  function_name = "DPA-API-Sync"

  s3_bucket = aws_s3_bucket.api_lambda_bucket.id
  s3_key    = aws_s3_object.lambda_api_sync.key

  runtime = "python3.8"
  handler = "pet_sync.handler"

  source_code_hash = data.archive_file.lambda_api_sync.output_base64sha256

  role = aws_iam_role.sync_lambda_exec.arn

  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
  ]

  timeout = 30
}

resource "aws_cloudwatch_log_group" "dpa_api_lambda_sync_log_group" {
  name = "/aws/lambda/${aws_lambda_function.dpa_api_lambda_sync.function_name}"

  retention_in_days = 30
}
