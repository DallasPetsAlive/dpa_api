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
        "dynamodb:BatchWriteItem",
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
        aws_secretsmanager_secret.airtable_personal_access_token.arn,
        aws_secretsmanager_secret.airtable_base.arn,
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

resource "aws_cloudwatch_metric_alarm" "sync_api_errors" {
  alarm_name          = "dpa_api_sync_errors"
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
    FunctionName = aws_lambda_function.dpa_api_lambda_sync.function_name
  }
}

resource "aws_cloudwatch_event_rule" "sync_api_event_rule" {
  name        = "sync_api_event_rule"
  description = "invoke API sync hourly"

  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "sync_api_event_target" {
  rule      = aws_cloudwatch_event_rule.sync_api_event_rule.name
  target_id = "invoke_sync_api"

  arn = aws_lambda_function.dpa_api_lambda_sync.arn
}

resource "aws_lambda_permission" "sync_api_invocation" {
  statement_id  = "allow_cloudwatch_event_to_invoke_sync_api"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dpa_api_lambda_sync.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.sync_api_event_rule.arn
}
