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

resource "aws_lambda_function" "dpa_api_lambda_sync" {
  function_name = "DPA-API-Sync"

  s3_bucket = aws_s3_bucket.api_lambda_bucket.id
  s3_key    = aws_s3_object.lambda_api_sync.key

  runtime = "python3.8"
  handler = "pet_sync.handler"

  source_code_hash = data.archive_file.lambda_api_sync.output_base64sha256

  role = aws_iam_role.api_lambda_exec.arn

  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
  ]
}

resource "aws_cloudwatch_log_group" "dpa_api_lambda_sync_log_group" {
  name = "/aws/lambda/${aws_lambda_function.dpa_api_lambda_sync.function_name}"

  retention_in_days = 30
}
