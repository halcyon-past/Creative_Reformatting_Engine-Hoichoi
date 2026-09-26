###############################################################################
# Creative Reformatting Engine - AWS topology
#
# Migrating from local is a configuration change, not a rewrite: the ports in
# cre.ports are already satisfied by S3, SQS and SQLAlchemy adapters, so the
# same container image runs in both places with different environment.
#
#   local                         aws
#   -----------------------------------------------------------------
#   LocalStorage (data/)     ->   S3 + CloudFront
#   InMemoryQueue (threads)  ->   SQS (+ DLQ)
#   SQLite file              ->   Aurora Serverless v2 PostgreSQL
#   in-process worker        ->   separate ECS service, scaled on queue depth
#
# Kept deliberately in one file: the security groups are shared between the
# compute and database tiers, and splitting those across modules produces a
# dependency cycle rather than clearer code.
#
# NOTE: terraform is not installed in the environment this was authored in, so
# this configuration has NOT been run through `terraform validate` or `plan`.
# Review it before applying.
###############################################################################

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.60" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
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
  }
  az_count = length(var.availability_zones)
}

###############################################################################
# Network
###############################################################################
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = local.name })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name}-igw" })
}

resource "aws_subnet" "public" {
  count                   = local.az_count
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${local.name}-public-${count.index}" })
}

resource "aws_subnet" "private" {
  count             = local.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 100)
  availability_zone = var.availability_zones[count.index]
  tags              = merge(local.tags, { Name = "${local.name}-private-${count.index}" })
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${local.name}-nat" })
}

# A single NAT gateway: workers only egress to pull images and reach AWS APIs,
# so the cost of one per AZ is not justified until this is multi-AZ critical.
resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  depends_on    = [aws_internet_gateway.this]
  tags          = merge(local.tags, { Name = "${local.name}-nat" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(local.tags, { Name = "${local.name}-public" })
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }
  tags = merge(local.tags, { Name = "${local.name}-private" })
}

resource "aws_route_table_association" "public" {
  count          = local.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = local.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# S3 traffic is the bulk of this system's data movement; a gateway endpoint
# keeps masters and renders off the NAT gateway entirely.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  tags              = merge(local.tags, { Name = "${local.name}-s3" })
}

###############################################################################
# Security groups (shared by compute and data tiers)
###############################################################################
resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Public ingress to the API load balancer"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  dynamic "ingress" {
    for_each = var.certificate_arn == "" ? [] : [1]
    content {
      description = "HTTPS"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "service" {
  name        = "${local.name}-service"
  description = "ECS tasks for the API and the renderers"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags

  ingress {
    description     = "API traffic from the load balancer"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name        = "${local.name}-db"
  description = "Aurora, reachable only from the ECS tasks"
  vpc_id      = aws_vpc.this.id
  tags        = local.tags

  ingress {
    description     = "PostgreSQL"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.service.id]
  }
}

###############################################################################
# Media storage
###############################################################################
resource "aws_s3_bucket" "media" {
  bucket = "${local.name}-media"
  tags   = local.tags
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

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  # Masters are large and rarely re-read once their variants exist, but they
  # must stay retrievable: regenerating a single variant re-reads the master.
  rule {
    id     = "masters-to-infrequent-access"
    status = "Enabled"
    filter { prefix = "cre/masters/" }
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = var.allowed_origins
    max_age_seconds = 3600
  }
}

###############################################################################
# Job queue
###############################################################################
resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days
  tags                      = local.tags
}

resource "aws_sqs_queue" "jobs" {
  name = "${local.name}-jobs"

  # Must exceed the slowest render, or SQS redelivers work that is still in
  # flight and the same asset gets processed twice.
  visibility_timeout_seconds = var.job_visibility_timeout
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20 # long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })

  tags = local.tags
}

###############################################################################
# Database
###############################################################################
resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db" {
  name = "${local.name}-db"
  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    dbname   = var.db_name
  })
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name}-db"
  subnet_ids = aws_subnet.private[*].id
  tags       = local.tags
}

resource "aws_rds_cluster" "this" {
  cluster_identifier     = "${local.name}-db"
  engine                 = "aurora-postgresql"
  engine_mode            = "provisioned"
  engine_version         = var.db_engine_version
  database_name          = var.db_name
  master_username        = var.db_username
  master_password        = random_password.db.result
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.database.id]
  storage_encrypted      = true

  backup_retention_period = var.environment == "prod" ? 14 : 3
  deletion_protection     = var.environment == "prod"
  skip_final_snapshot     = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${local.name}-final" : null

  serverlessv2_scaling_configuration {
    min_capacity = var.db_min_capacity
    max_capacity = var.db_max_capacity
  }

  tags = local.tags
}

resource "aws_rds_cluster_instance" "this" {
  identifier         = "${local.name}-db-1"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version
  tags               = local.tags
}

###############################################################################
# IAM
###############################################################################
data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-db-secret"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.db.arn]
    }]
  })
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.tags
}

# Scoped to this system's own bucket and queue: the task can move media and
# consume jobs, and nothing else.
resource "aws_iam_role_policy" "task" {
  name = "cre-runtime"
  role = aws_iam_role.task.id
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
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.db.arn]
      },
    ]
  })
}

###############################################################################
# Compute
###############################################################################
resource "aws_ecs_cluster" "this" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name}/api"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name}/worker"
  retention_in_days = 30
  tags              = local.tags
}

locals {
  # The single switch that moves the application from local backends to AWS.
  common_environment = [
    { name = "CRE_ENV", value = var.environment },
    { name = "CRE_DEBUG", value = "false" },
    { name = "CRE_STORAGE_BACKEND", value = "s3" },
    { name = "CRE_QUEUE_BACKEND", value = "sqs" },
    { name = "CRE_REPOSITORY_BACKEND", value = "sqlite" },
    { name = "CRE_S3_BUCKET", value = aws_s3_bucket.media.bucket },
    { name = "CRE_S3_PREFIX", value = "cre/" },
    { name = "CRE_SQS_QUEUE_URL", value = aws_sqs_queue.jobs.url },
    { name = "CRE_AWS_REGION", value = var.region },
    { name = "CRE_DATA_DIR", value = "/data" },
    { name = "CRE_MODEL_DIR", value = "/opt/cre/models" },
    { name = "CRE_ALLOW_MODEL_DOWNLOAD", value = "0" },
    { name = "CRE_SPEC_FILE", value = "/opt/cre/specs/platform_specs.yaml" },
    { name = "CRE_CORS_ORIGINS", value = join(",", var.allowed_origins) },
  ]

  db_secrets = [
    { name = "CRE_DB_USERNAME", valueFrom = "${aws_secretsmanager_secret.db.arn}:username::" },
    { name = "CRE_DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.db.arn}:password::" },
  ]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  tags                     = local.tags

  container_definitions = jsonencode([{
    name      = "api"
    image     = var.image
    essential = true
    command   = ["uvicorn", "cre.main:app", "--host", "0.0.0.0", "--port", "8000"]
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = concat(local.common_environment, [
      # The API enqueues work; the worker service consumes it.
      { name = "CRE_WORKER_CONCURRENCY", value = "0" },
      { name = "CRE_DATABASE_HOST", value = aws_rds_cluster.this.endpoint },
      { name = "CRE_DATABASE_NAME", value = var.db_name },
    ])
    secrets = local.db_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  tags                     = local.tags

  container_definitions = jsonencode([{
    name      = "worker"
    image     = var.image
    essential = true
    command   = ["python", "-m", "cre.worker.entrypoint"]
    environment = concat(local.common_environment, [
      { name = "CRE_WORKER_CONCURRENCY", value = tostring(var.worker_concurrency) },
      { name = "CRE_DATABASE_HOST", value = aws_rds_cluster.this.endpoint },
      { name = "CRE_DATABASE_NAME", value = var.db_name },
    ])
    secrets = local.db_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

###############################################################################
# Load balancer
###############################################################################
resource "aws_lb" "this" {
  name               = substr("${local.name}-alb", 0, 32)
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 300 # large uploads
  tags               = local.tags
}

resource "aws_lb_target_group" "api" {
  name        = substr("${local.name}-api", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"
  tags        = local.tags

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  deregistration_delay = 30
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  # With a certificate configured, plain HTTP only exists to redirect.
  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [1] : []
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.api.arn
    }
  }

  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [] : [1]
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}

resource "aws_lb_listener" "https" {
  count             = var.certificate_arn == "" ? 0 : 1
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

###############################################################################
# Services
###############################################################################
resource "aws_ecs_service" "api" {
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_min_count
  launch_type     = "FARGATE"
  tags            = local.tags

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.service.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 60
  depends_on                        = [aws_lb_listener.http]

  lifecycle {
    ignore_changes = [desired_count] # autoscaling owns this
  }
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_min_count
  launch_type     = "FARGATE"
  tags            = local.tags

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.service.id]
  }

  lifecycle {
    ignore_changes = [desired_count]
  }
}

###############################################################################
# Autoscaling
###############################################################################
resource "aws_appautoscaling_target" "api" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.api_min_count
  max_capacity       = var.api_max_count
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${local.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.api.service_namespace
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 60
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_target" "worker" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.worker_min_count
  max_capacity       = var.worker_max_count
}

# Renders are bursty and CPU-bound: by the time CPU rises the queue is already
# deep, so the worker tier scales on backlog per task instead.
resource "aws_appautoscaling_policy" "worker_queue_depth" {
  name               = "${local.name}-worker-backlog"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.worker.service_namespace
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension

  target_tracking_scaling_policy_configuration {
    customized_metric_specification {
      metrics {
        id    = "backlog"
        label = "Visible messages per running task"
        expression = "IF(tasks > 0, visible / tasks, visible)"
        return_data = true
      }
      metrics {
        id          = "visible"
        return_data = false
        metric_stat {
          metric {
            namespace   = "AWS/SQS"
            metric_name = "ApproximateNumberOfMessagesVisible"
            dimensions {
              name  = "QueueName"
              value = aws_sqs_queue.jobs.name
            }
          }
          stat = "Average"
        }
      }
      metrics {
        id          = "tasks"
        return_data = false
        metric_stat {
          metric {
            namespace   = "ECS/ContainerInsights"
            metric_name = "RunningTaskCount"
            dimensions {
              name  = "ClusterName"
              value = aws_ecs_cluster.this.name
            }
            dimensions {
              name  = "ServiceName"
              value = aws_ecs_service.worker.name
            }
          }
          stat = "Average"
        }
      }
    }
    # Roughly two queued jobs per worker before adding capacity.
    target_value       = 2
    scale_in_cooldown  = 600 # slow to scale in: renders are long
    scale_out_cooldown = 60
  }
}

###############################################################################
# Alarms
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

resource "aws_cloudwatch_metric_alarm" "queue_backlog" {
  alarm_name          = "${local.name}-queue-backlog"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 1800 # 30 minutes
  alarm_description   = "Jobs are waiting far longer than a render should take."
  dimensions          = { QueueName = aws_sqs_queue.jobs.name }
  tags                = local.tags
}
