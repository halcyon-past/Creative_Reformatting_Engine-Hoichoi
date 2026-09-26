###############################################################################
# Creative Reformatting Engine - AWS Free Tier deployment
#
# Everything here is chosen to stay inside the AWS Free Tier. That means a
# deliberately different shape from ../ (the scalable stack), because several
# services used there have no free tier at all:
#
#   scalable stack            free-tier stack           why
#   --------------------------------------------------------------------------
#   ECS Fargate               EC2 t3.micro              Fargate has no free tier;
#                                                       EC2 micro gives 750h/mo
#   Aurora Serverless v2      SQLite on EBS             Aurora has no free tier
#   NAT Gateway               public subnet             NAT is ~$32/mo, never free
#   Application Load Balancer nginx on the instance     ALB free hours expire and
#                                                       LCUs bill from day one
#   Secrets Manager           SSM Parameter Store       Secrets Manager is paid;
#                                                       Parameter Store standard
#                                                       is free
#
# Free Tier reality check, because "free" has edges:
#   * EC2 750h/month and EBS 30GB are **12 months from account creation**, not
#     perpetual. After that a t3.micro is roughly $7-8/month.
#   * S3 5GB, 20k GET, 2k PUT are also 12-month. Masters are large: a handful
#     of 280MB videos will exceed 5GB. The lifecycle rule below expires masters
#     to keep that in check -- tune it before you rely on it.
#   * SQS 1M requests/month is **always free**, so the queue genuinely costs
#     nothing at this scale.
#   * CloudWatch Logs 5GB ingest/month is always free.
#   * Data transfer out is 100GB/month free.
#
# The honest constraint: **t3.micro has 1GB of RAM**, and decoding 1080p video
# alongside the MediaPipe models is tight. The user-data below provisions 2GB
# of swap and pins worker concurrency to 1, which makes it work, but renders
# will be slow. For anything beyond evaluation use t3.small (not free tier) by
# setting `instance_type` -- nothing else changes.
#
# NOTE: terraform was not available in the environment this was authored in, so
# this configuration has NOT been through `terraform validate` or `plan`.
###############################################################################

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.60" }
  }
}

provider "aws" {
  region = var.region
}

locals {
  name = "${var.project}-${var.environment}"
  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    CostProfile = "free-tier"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

###############################################################################
# Network - public subnet only, so there is no NAT gateway to pay for
###############################################################################
resource "aws_vpc" "this" {
  cidr_block           = "10.50.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = local.name })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name}-igw" })
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.50.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${local.name}-public" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(local.tags, { Name = "${local.name}-public" })
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# S3 traffic is the bulk of the data movement and this keeps it off the public
# internet path entirely. Gateway endpoints are free.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]
  tags              = merge(local.tags, { Name = "${local.name}-s3" })
}

###############################################################################
# Security
###############################################################################
resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "Creative Reformatting Engine instance"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_web_cidrs
  }

  # SSH is opt-in and CIDR-scoped. Leave `ssh_cidrs` empty and use SSM Session
  # Manager instead -- the instance profile below already permits it, and it
  # avoids exposing port 22 at all.
  dynamic "ingress" {
    for_each = length(var.ssh_cidrs) > 0 ? [1] : []
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.ssh_cidrs
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

###############################################################################
# Media storage
###############################################################################
resource "aws_s3_bucket" "media" {
  bucket        = "${local.name}-media"
  force_destroy = var.environment != "prod"
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# Free Tier gives 5GB of S3. Masters are the big objects, so they are expired
# rather than kept: a variant can always be re-rendered from a re-upload, and
# blowing the 5GB ceiling is what turns this from free into a bill.
resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    id     = "expire-masters"
    status = var.expire_masters_after_days > 0 ? "Enabled" : "Disabled"
    filter { prefix = "cre/masters/" }
    expiration { days = max(var.expire_masters_after_days, 1) }
  }

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload { days_after_initiation = 3 }
  }
}

###############################################################################
# Queue - SQS is always free up to 1M requests/month
###############################################################################
resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600
  tags                      = local.tags
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${local.name}-jobs"
  visibility_timeout_seconds = var.job_visibility_timeout
  message_retention_seconds  = 345600
  # Long polling keeps the request count (and so the bill) near zero.
  receive_wait_time_seconds = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })
  tags = local.tags
}

###############################################################################
# IAM - instance profile scoped to this system's bucket and queue
###############################################################################
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${local.name}-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
  tags               = local.tags
}

# Enables Session Manager, so SSH can stay closed.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "runtime" {
  name = "cre-runtime"
  role = aws_iam_role.instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${aws_s3_bucket.media.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [aws_s3_bucket.media.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage",
          "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility",
        ]
        Resource = [aws_sqs_queue.jobs.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = ["${aws_cloudwatch_log_group.app.arn}:*"]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "${local.name}-instance"
  role = aws_iam_role.instance.name
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/cre/${local.name}"
  retention_in_days = 7 # keeps ingest inside the always-free 5GB
  tags              = local.tags
}

###############################################################################
# Compute - one t3.micro running the stack under docker compose
###############################################################################
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

locals {
  user_data = <<-BASH
    #!/bin/bash
    set -euxo pipefail

    dnf update -y
    dnf install -y docker git
    systemctl enable --now docker

    # t3.micro has 1GB of RAM. Decoding 1080p video with the vision models
    # loaded will exceed that, and the OOM killer takes the worker with it.
    # Swap is slow but it is the difference between "slow" and "crashes".
    if [ ! -f /swapfile ]; then
      dd if=/dev/zero of=/swapfile bs=1M count=2048
      chmod 600 /swapfile
      mkswap /swapfile
      swapon /swapfile
      echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi

    curl -sSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" \
      -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    mkdir -p /opt/cre /data
    cat > /opt/cre/.env <<'ENVEOF'
    CRE_ENV=${var.environment}
    CRE_DEBUG=false
    CRE_STORAGE_BACKEND=s3
    CRE_QUEUE_BACKEND=sqs
    CRE_REPOSITORY_BACKEND=sqlite
    CRE_S3_BUCKET=${aws_s3_bucket.media.bucket}
    CRE_S3_PREFIX=cre/
    CRE_SQS_QUEUE_URL=${aws_sqs_queue.jobs.url}
    CRE_AWS_REGION=${var.region}
    CRE_DATA_DIR=/data
    CRE_MODEL_DIR=/opt/cre/models
    CRE_ALLOW_MODEL_DOWNLOAD=0
    CRE_SPEC_FILE=/opt/cre/specs/platform_specs.yaml
    # One render at a time: 1GB of RAM will not hold two.
    CRE_WORKER_CONCURRENCY=1
    # Cheaper analysis so a render finishes in reasonable time on a burstable CPU.
    CRE_ANALYSIS_FPS=6
    CRE_MAX_REEL_SOURCE_SECONDS=60
    # nginx on this box is the only proxy in front of the app.
    CRE_TRUSTED_PROXY_HOPS=1
    CRE_AUDIT_RETENTION_DAYS=${var.audit_retention_days}
    CRE_CORS_ORIGINS=${join(",", var.allowed_origins)}
    ENVEOF

    aws ecr get-login-password --region ${var.region} \
      | docker login --username AWS --password-stdin ${split("/", var.image)[0]}

    docker run -d --restart always --name cre-api \
      --env-file /opt/cre/.env -v /data:/data -p 8000:8000 \
      --log-driver awslogs \
      --log-opt awslogs-region=${var.region} \
      --log-opt awslogs-group=${aws_cloudwatch_log_group.app.name} \
      --log-opt awslogs-stream=api \
      ${var.image}

    # The API hosts the worker in-process here: a second container would not
    # fit in 1GB, and at this scale one renderer is the honest capacity.
    docker run -d --restart always --name cre-web \
      -p 80:80 --link cre-api:api \
      --log-driver awslogs \
      --log-opt awslogs-region=${var.region} \
      --log-opt awslogs-group=${aws_cloudwatch_log_group.app.name} \
      --log-opt awslogs-stream=web \
      ${var.web_image}
  BASH
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name
  user_data              = local.user_data
  user_data_replace_on_change = true

  root_block_device {
    # Free Tier allows 30GB of EBS across all volumes.
    volume_size           = var.root_volume_gb
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  metadata_options {
    http_tokens   = "required" # IMDSv2 only
    http_endpoint = "enabled"
  }

  tags = merge(local.tags, { Name = local.name })
}

# Free while attached to a running instance, and it keeps the address stable
# across stop/start.
resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
  tags     = merge(local.tags, { Name = local.name })
}

###############################################################################
# Alarms - 10 alarms are always free
###############################################################################
resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "${local.name}-dlq-not-empty"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "A render failed three times and was parked in the DLQ."
  dimensions          = { QueueName = aws_sqs_queue.jobs_dlq.name }
  tags                = local.tags
}

# Burstable instances stop bursting when credits run out, which on t3.micro
# shows up as renders suddenly taking many times longer.
resource "aws_cloudwatch_metric_alarm" "cpu_credits" {
  alarm_name          = "${local.name}-cpu-credits-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUCreditBalance"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 20
  alarm_description   = "CPU credits nearly exhausted; renders will crawl."
  dimensions          = { InstanceId = aws_instance.app.id }
  tags                = local.tags
}
