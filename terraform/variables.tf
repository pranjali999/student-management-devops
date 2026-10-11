variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "project_name" {
  type    = string
  default = "student-mgmt"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "public_key_path" {
  type    = string
  default = "~/.ssh/id_rsa.pub"
}

variable "private_key_path" {
  type    = string
  default = "~/.ssh/id_rsa"
}

variable "allowed_cidr" {
  description = "CIDR allowed to reach SSH/Grafana/Prometheus. Set to your IP, e.g. 203.0.113.5/32"
  type        = string
  default     = "0.0.0.0/0"
}
