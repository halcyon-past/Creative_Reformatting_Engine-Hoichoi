output "media_bucket" {
  value       = aws_s3_bucket.media.bucket
  description = "Set as CRE_S3_BUCKET."
}

output "queue_url" {
  value       = aws_sqs_queue.jobs.url
  description = "Set as CRE_SQS_QUEUE_URL."
}

output "dead_letter_queue_url" {
  value       = aws_sqs_queue.jobs_dlq.url
  description = "Renders that failed three times land here; drain after a bad deploy."
}

output "api_url" {
  value       = "http://${aws_lb.this.dns_name}"
  description = "Load balancer hostname for the API."
}

output "database_endpoint" {
  value       = aws_rds_cluster.this.endpoint
  description = "Aurora writer endpoint. Credentials live in Secrets Manager."
}

output "database_secret_arn" {
  value       = aws_secretsmanager_secret.db.arn
  description = "Secrets Manager ARN holding the database credentials."
}

output "ecs_cluster" {
  value = aws_ecs_cluster.this.name
}

output "runtime_environment" {
  description = "The environment that switches the app from local to AWS backends."
  value = {
    CRE_ENV             = var.environment
    CRE_STORAGE_BACKEND = "s3"
    CRE_QUEUE_BACKEND   = "sqs"
    CRE_S3_BUCKET       = aws_s3_bucket.media.bucket
    CRE_SQS_QUEUE_URL   = aws_sqs_queue.jobs.url
    CRE_AWS_REGION      = var.region
    CRE_DATABASE_HOST   = aws_rds_cluster.this.endpoint
    CRE_DATABASE_NAME   = var.db_name
  }
}
