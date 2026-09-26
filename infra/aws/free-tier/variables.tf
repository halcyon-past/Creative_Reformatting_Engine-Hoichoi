variable "project" {
  type    = string
  default = "hoichoi-cre"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  description = "Free Tier applies per account, not per region; pick one near your users."
  type        = string
  default     = "us-east-1"
}

variable "image" {
  description = "ECR image URI for the backend (API + in-process worker)."
  type        = string
}

variable "web_image" {
  description = "ECR image URI for the nginx frontend."
  type        = string
}

variable "instance_type" {
  description = <<-EOT
    The Free Tier covers 750h/month of **t2.micro** in regions where t2.micro
    exists -- which includes us-east-1 -- and t3.micro only in regions where it
    does not. So in us-east-1 the free instance is t2.micro, and setting
    t3.micro here would quietly fall outside the allowance.

    t2.micro is 1 vCPU / 1GB. That is slow for CPU-bound rendering: expect
    several minutes for a 30s reel, and the 1GB is tight enough that swap is
    provisioned to stop the OOM killer taking the worker.

    First upgrade once evaluation is over is t3.small (2 vCPU / 2GB, ~$15/mo,
    not free). Nothing else in the stack changes.
  EOT
  type    = string
  default = "t3.micro"
}

variable "root_volume_gb" {
  description = "Free Tier allows 30GB of EBS in total across all volumes."
  type        = number
  default     = 30
}

variable "allowed_web_cidrs" {
  description = "Who may reach the UI. Narrow this before putting real content in."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ssh_cidrs" {
  description = <<-EOT
    Leave empty (the default) and use SSM Session Manager, which the instance
    profile already allows. Populating this opens port 22.
  EOT
  type    = list(string)
  default = []
}

variable "allowed_origins" {
  description = "CORS origins for the API."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "job_visibility_timeout" {
  description = <<-EOT
    Must exceed the slowest render or SQS redelivers work still in flight and
    the asset renders twice. A burstable t3.micro is slow, so this is generous.
  EOT
  type    = number
  default = 1800
}

variable "expire_masters_after_days" {
  description = <<-EOT
    Free Tier gives 5GB of S3, and master videos are hundreds of megabytes
    each. Masters are expired after this many days to keep under the ceiling;
    a variant can be re-rendered from a fresh upload. Set 0 to keep them, and
    watch the bill.
  EOT
  type    = number
  default = 7
}

variable "audit_retention_days" {
  description = "Audit rows carry IP addresses; they are purged past this age."
  type        = number
  default     = 90
}
