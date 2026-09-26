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
  default     = "ap-south-1"
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
    t3.micro is the Free Tier instance (750h/month for 12 months). It has 1GB
    of RAM, which is genuinely tight for 1080p video plus the vision models --
    swap is provisioned to compensate, but renders are slow. t3.small doubles
    the memory and is the first thing to change once evaluation is over; it is
    not free.
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
