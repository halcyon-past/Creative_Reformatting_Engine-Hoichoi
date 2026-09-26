variable "project" {
  description = "Project slug used to name every resource."
  type        = string
  default     = "hoichoi-cre"
}

variable "environment" {
  description = "Deployment environment (dev | staging | prod)."
  type        = string
  default     = "dev"
}

variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["ap-south-1a", "ap-south-1b"]
}

variable "image" {
  description = "ECR image URI for the backend (API and worker share it)."
  type        = string
}

variable "allowed_origins" {
  description = "Origins permitted by CORS on the API and the media bucket."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "certificate_arn" {
  description = "ACM certificate for the ALB listener. Empty means HTTP only (dev)."
  type        = string
  default     = ""
}

# --- job handling ---------------------------------------------------------- #
variable "job_visibility_timeout" {
  description = <<-EOT
    Seconds a job stays invisible after a worker picks it up. Must exceed the
    slowest render or SQS will redeliver work still in flight and the same
    asset will be processed twice. 90s of source at 10fps analysis plus a
    full-rate render sits comfortably inside 15 minutes.
  EOT
  type    = number
  default = 900
}

# --- sizing ---------------------------------------------------------------- #
variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "api_min_count" {
  type    = number
  default = 1
}

variable "api_max_count" {
  type    = number
  default = 4
}

variable "worker_cpu" {
  description = "Renders are CPU-bound; 2 vCPU is the practical floor for HD."
  type        = number
  default     = 2048
}

variable "worker_memory" {
  description = "Must hold decoded HD frames plus the MediaPipe models."
  type        = number
  default     = 4096
}

variable "worker_min_count" {
  description = "Zero is viable: jobs queue until a task starts, at the cost of cold-start latency."
  type        = number
  default     = 1
}

variable "worker_max_count" {
  type    = number
  default = 10
}

variable "db_min_capacity" {
  type    = number
  default = 0.5
}

variable "db_max_capacity" {
  type    = number
  default = 4
}

# --- database -------------------------------------------------------------- #
variable "db_name" {
  type    = string
  default = "cre"
}

variable "db_username" {
  type    = string
  default = "cre_app"
}

variable "db_engine_version" {
  type    = string
  default = "16.4"
}

# --- worker ---------------------------------------------------------------- #
variable "worker_concurrency" {
  description = <<-EOT
    Jobs a single worker task processes in parallel. Renders are CPU-bound, so
    keep this at or below the task's vCPU count or the jobs simply contend.
  EOT
  type    = number
  default = 2
}
