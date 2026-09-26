output "app_url" {
  value       = "http://${aws_eip.app.public_ip}"
  description = "The UI and API. Put CloudFront in front of it for TLS if needed."
}

output "instance_id" {
  value       = aws_instance.app.id
  description = "Connect with: aws ssm start-session --target <this>"
}

output "media_bucket" {
  value = aws_s3_bucket.media.bucket
}

output "queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "dead_letter_queue_url" {
  value = aws_sqs_queue.jobs_dlq.url
}

output "free_tier_notes" {
  description = "What is free, for how long, and what to watch."
  value = {
    always_free = "SQS (1M req/mo), CloudWatch alarms (10), S3 gateway endpoint"
    twelve_months_only = "EC2 750h/mo, EBS 30GB, S3 5GB + 20k GET + 2k PUT"
    watch = join("; ", [
      "S3 5GB fills fast with video masters - see expire_masters_after_days",
      "t3.micro has 1GB RAM; swap is provisioned but renders are slow",
      "CPU credits deplete under sustained rendering - see the cpu-credits alarm",
      "Free Tier EC2/EBS/S3 expire 12 months after account creation",
    ])
  }
}
