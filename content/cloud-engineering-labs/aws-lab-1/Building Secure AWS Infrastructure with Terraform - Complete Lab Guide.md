---
title: "Building Secure AWS Infrastructure with Terraform - Complete Lab Guide"
date: 2025-05-27
tags: ["AWS", "EC2", "VPC", "bastion", "jumpbox", "powershell", "bash", "terraform", "infrastructure-as-code", "network automation", "cloud deployment"]
cloud_provider: "AWS"
categories: ["Cloud Engineering Labs"]
draft: false
---
## Overview

This document summarizes the technical work completed to build, configure, and automate a secure AWS VPC lab using Terraform. It covers manual and automated infrastructure deployment steps, with detailed explanations for each Terraform configuration component, designed to help replicate the setup at any time in the future.

---

## Objectives

- Build a segmented AWS VPC network with public and private subnets.
    
- Launch EC2 instances in both public and private subnets.
    
- Secure access using Security Groups.
    
- Enable VPC Flow Logs for traffic monitoring.
    
- Manage the infrastructure using Terraform, with variables and data sources referencing existing AWS resources.
    

---

## Prerequisites

- An AWS Free Tier account.
    
- AWS CLI installed and configured (`aws configure`) with IAM user access keys.
    
- Terraform installed on the local workstation.
    
- An existing VPC created manually in AWS.
    
- An EC2 SSH Key Pair created in AWS (with the `.pem` file downloaded and stored securely).
    

---

## Terraform Project Structure

```
/terraform-vpc-lab
  ├── provider.tf
  ├── variables.tf
  ├── data.tf
  ├── locals.tf
  ├── main.tf
  ├── outputs.tf
  ├── terraform.tfvars
  ├── deploy-terraform.ps1
  └── user-data
	  ├── private-userdata.sh
	  └── public-userdata.sh
```

Each file has a specific purpose, described in detail below.

---

## provider.tf

```hcl
provider "aws" {
  region = "us-east-1"
}
```

**Explanation:**

- Defines the AWS provider Terraform will use.
    
- Sets the default AWS region to `us-west-1`. This can be adjusted or turned into a configurable variable if needed.
    

---

## variables.tf

The variables.tf file defines **all the input variables** your Terraform configuration uses, making it:

- Flexible
- Resusable
- Easier to manage across environments (dev, staging, prod) By declaring variables here we avoid hardcoding values in `main.tf` or other resource files.

```hcl
# variables.tf - defines and validates variables
variable "vpc_cidr" {
  description = "CIDR block for the new VPC"
  type        = string
  default     = "10.0.0.0/16"
  
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

# defines which AWS Availability zone to deploy into
variable "availability_zone" {
  description = "The AWS Availability Zone"
  type        = string
  default     = "us-west-1a"

# regex validation to ensure the format matches AWS AZ patterns
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9][a-z]$", var.availability_zone))
    error_message = "Availability zone must be in the format like 'us-west-1a'."
  }
}

# Defines the IP range for the public subnet
variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.0.1.0/24"

# CIDR validation check
  validation {
    condition     = can(cidrhost(var.public_subnet_cidr, 0))
    error_message = "Public subnet CIDR must be a valid IPv4 CIDR block."
  }
}

# Defines the IP range for the private subnet
variable "private_subnet_cidr" {
  description = "CIDR block for the private subnet"
  type        = string
  default     = "10.0.2.0/24"

# CIDR validation check
  validation {
    condition     = can(cidrhost(var.private_subnet_cidr, 0))
    error_message = "Private subnet CIDR must be a valid IPv4 CIDR block."
  }
}

# Specifies the name of the EC2 SSH key pair used for connecting to instances.
variable "key_name" {
  description = "The name of the EC2 SSH key pair"
  type        = string
}

# Used in security group rules to restrict SSH access
# requires a /32 CIDR notation
variable "home_ip" {
  description = "Your home public IP address with /32 mask (e.g., 203.0.113.1/32)"
  type        = string

# Regex validation to ensure proper format
  validation {
    condition     = can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/32$", var.home_ip))
    error_message = "Home IP must be a valid IPv4 address with /32 mask (e.g., 203.0.113.1/32)."
  }
}

# Used for tagging AWS resources for identification
# Helps track whick resources belong to whick project
variable "project_name" {
  description = "Name of the project for resource tagging"
  type        = string
  default     = "terraform-vpc-demo"
}

# Tags resources or configures settings per environment
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

# Ensures only use valid environment names
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

# Controls the size of the EC2 instances
# Below is freet-tier eligible
variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

# Controls whether DNS hostnames is enabled for the VPC
# Belowis set to true - best practice
variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames in the VPC"
  type        = bool
  default     = true
}

# Controls whether DNS support is enabled for the VPC
# Below set to true - best practice
variable "enable_dns_support" {
  description = "Enable DNS support in the VPC"
  type        = bool
  default     = true
}
```

**Explanation:**

- Defines all required input variables, including the VPC, subnet CIDRs, key pair name, and the home public IP address for secure SSH access.
- Modular and adaptable to different setups.
- Safter through built-in validation blocks.
- Easier to manage across environments by externalizing critical settings.

---

## terraform.tfvars

```hcl
# terraform.tfvars - define sensitive values
key_name            = "AWS_key_name"
home_ip             = "publicIP/32"
project_name        = "project name"
environment         = "dev"
vpc_cidr            = "10.0.0.0/16"
public_subnet_cidr  = "10.0.1.0/24"
private_subnet_cidr = "10.0.2.0/24"
availability_zone   = "us-west-1a"
instance_type       = "t2.micro"
```

**Explanation:**

- Provides actual values for the variables defined in `variables.tf`.
    
- This file is automatically loaded by Terraform and should be excluded from version control for sensitive values.
    

---

## data.tf

This file defines Terraform data sources, which allows the ability to query AWS for existing dynamic information that is not created or managed directly, such as available regions, caller identity, AMI IDs, or availability zones.

These values can be used throughout Terraform configurations for dynamic, up-to-date references.

```hcl
# data.tf - Centralize data sources
# Fetches the AWS region that Terraform is currently operating in
# Useful to reference the region dynamically in resources or outputs without hardcoding var.region everwhere
data "aws_region" "current" {}

# Returns details about the active AWS identity: AWS account ID, Amazon Resource Name (ARN), User ID
# Useful for tagging, auditing, or conditional logic tied to the current account
data "aws_caller_identity" "current" {}

# Returns a list of available AZs in the current region
# Can be used to distribute resources across zones for HA
# below is only including AZs in the "available" state
data "aws_availability_zones" "available" {
  state = "available"
}

# Looks up the most recent official Amazon Linux 2 AMI
# Ensures that EC2 instances are always built from the latest Amazon-maintained AMI, reducing the need to hardcode AMI IDs
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"] # HVM-based, general-purpose SSD, 64-bit
  }
  
  filter {
    name   = "virtualization-type" # sets virtualization type to HVM
    values = ["hvm"]
  }
}
```

**Explanation:**

- Uses Terraform's `data` sources to reference existing AWS resources without Terraform managing or creating them.
- Makes Terraform configuration more dynamic and adaptable.
- Reduce hardcoding of values that might change between regions, accounts, or over time.
- Help ensure that the infrastructure always targets the correct, most up-to-date AWS resources.

---

## locals.tf

The `locals` block in Terrraform defines **computed values** or **constants** that can be reused throughout the configuration. The **computed values** and **constants** help reduce repetition, centralize logic, and make configurations easier to maintain. These are like reusable variables, but they can include computed or derived values (not just user-provided inputs).

```hcl
# locals.tf - Define reusable values and computed tags
# `locals {` starts the block
locals {
  # Common tags to apply to all resources
  # Defines a reusable map of tags
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    CreatedAt   = timestamp() # Computed at runtime using current runtime stamp
  }

  # Resource naming convention
  # Useful for consistent resource names or tags across environments
  name_prefix = "${var.project_name}-${var.environment}"
  
  # Computed values
  # These locals make it easier to refer to the values without repeating longer expressions
  vpc_cidr = var.vpc_cidr                 # references the variable block
  region   = data.aws_region.current.name # references the data block
}
```

**Explanation:**

- Defines local values to standardize instance naming across the configuration.
- Can apply the `local.common_tags` to all taggable resources, ensuring consistency across infrastructure.
- Code consistency (single place to define tag maps or name patterns)
- Maintainability (change once, propagate everywhere)
- Readability (clear, descriptive references)

---

## main.tf

This is the **core infrastructure definition** file in Terraform. It contains all the resource blocks to define and build AWS network, security, compute resources, logging, and permissions.

**Key sections explained:**

### VPC Creation

```hcl
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = var.enable_dns_hostnames
  enable_dns_support   = var.enable_dns_support
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}
```

- Creates a new VPC using the specified CIDR block and DNS settings.
- Applies consistent tags merged from local common tags.

### Internet Gateway

```hcl
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}
```

- Attaches an internet gateway to the new VPC, enabling internet access for public resources.

### Subnets

```hcl
# Create public subnet
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-subnet"
    Type = "Public"
  })
}
  
# Create private subnet
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = var.availability_zone
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-subnet"
    Type = "Private"
  })
}
```

- Creates a public subnet and a private subnet in the specified availability zone.
- The public subnet allows public IP assignments; the private one does not.

### Elastic IP and NAT Gateway

```hcl
# Allocate Elastic IP for NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-eip"
  })

  depends_on = [aws_internet_gateway.main]
}
  
# Create NAT Gateway in public subnet
resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-gateway"
  })

  depends_on = [aws_internet_gateway.main]
}
```

- Allocates a static Elastic IP and attaches it to a NAT Gateway in the public subnet, allowing private subnet instances to access the internet outbound.

### Route Tables

```hcl
# Create public route table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-rt"
    Type = "Public"
  })
}

# Associate public route table with public subnet
resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Create private route table (via NAT Gateway)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id # Changed from data.aws_vpc.existing.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-rt"
    Type = "Private"
  })
}

# Associate private route table with private subnet
resource "aws_route_table_association" "private_assoc" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}
```

- Creates a public route table with a default route to the internet gateway.
    
- Creates a private route table with a default route to the NAT gateway.
    
- Associates the correct route table with each subnet.
    

### Security Groups

```hcl
# Create Security Group for public EC2
resource "aws_security_group" "public_sg" {
  name_prefix = "${local.name_prefix}-public-"
  description = "Security group for public EC2 instances - allows SSH from specified IP"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    description = "SSH from home IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.home_ip]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-sg"
    Type = "Public"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Create Security Group for private EC2
resource "aws_security_group" "private_sg" {
  name_prefix = "${local.name_prefix}-private-"
  description = "Security group for private EC2 instances - allows SSH from public subnet"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "SSH from public subnet"
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [aws_security_group.public_sg.id]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-sg"
    Type = "Private"
  })

  lifecycle {
    create_before_destroy = true
  }
}
```

- Public SG allows SSH access only from the specified home IP.
    
- Private SG allows SSH access only from the public instance SG (used as a bastion host).
    

### EC2 Instances

```hcl
# Launch EC2 in public subnet
resource "aws_instance" "public_ec2" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.public_sg.id]

  user_data = base64encode(templatefile("${path.module}/user-data/public-userdata.sh", {
    hostname = "${local.name_prefix}-public"
  }))

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-ec2"
    Type = "Public"
    Role = "Bastion"
  })
}

# Launch EC2 in private subnet
resource "aws_instance" "private_ec2" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.private.id
  key_name               = var.key_name

  vpc_security_group_ids = [aws_security_group.private_sg.id]

  user_data = base64encode(templatefile("${path.module}/user-data/private-userdata.sh", {
    hostname = "${local.name_prefix}-private"
  }))

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-ec2"
    Type = "Private"
    Role = "Backend"
  })
}
```

- Launches an EC2 instance in the public subnet (Amazon Linux 2), serving as a bastion or jump host.
    
- Launches an EC2 instance in the private subnet (Amazon Linux 2), serving as a backend node.
    
- Both use user data scripts (`public-userdata.sh`, `private-userdata.sh`) and consistent tagging.
    

### CloudWatch Log Group for VPC Flow Logs

```hcl
# Create CloudWatch Log Group for VPC Flow Logs
resource "aws_cloudwatch_log_group" "vpc_logs" {
  name              = "/aws/vpc/flowlogs/${local.name_prefix}"
  retention_in_days = 7

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc-flow-logs"
  })
}
```

- Creates a CloudWatch log group to hold the VPC Flow Logs, with a 7-day retention period.

### IAM Role and Policy for VPC Flow Logs

```hcl
# Create IAM role for flow logs
resource "aws_iam_role" "flow_logs_role" {
  name_prefix = "${local.name_prefix}-flow-logs-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "vpc-flow-logs.amazonaws.com"
      }
    }]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-flow-logs-role"
  })
}

  

# Create custom IAM policy for flow logs
resource "aws_iam_role_policy" "flow_logs_policy" {
  name_prefix = "${local.name_prefix}-flow-logs-"
  role        = aws_iam_role.flow_logs_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ],
        Resource = "${aws_cloudwatch_log_group.vpc_logs.arn}:*"
      }
    ]
  })
}
```

- Creates an IAM role with permissions for VPC Flow Logs to push data to CloudWatch Logs.

### Enable VPC Flow Logs

```hcl
# Enable VPC Flow Logs
resource "aws_flow_log" "vpc_flow_logs" {
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.vpc_logs.arn
  traffic_type         = "ALL"
  vpc_id               = aws_vpc.main.id # Changed from data.aws_vpc.existing.id
  iam_role_arn         = aws_iam_role.flow_logs_role.arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc-flow-logs"
  })
}
```

- Enables detailed traffic logging on the VPC, writing all traffic data (accepted and rejected) to CloudWatch Logs.

**Explanation:**

- Uses `locals` for consistent naming and tags.
- Applies merge patterns for reusable tag blocks.
- Includes lifecycle rules (like create_before_destroy) for safer updates.

---

## outputs.tf

The `outputs.tf` file defines what Terraform will print after `terraform apply` finishes. This helps to get key resource, IDs, IPs, and metadata. It makes it easier to connect or interact with deployed resources. It can also feed outputs into other Terraform modules or systems.

```hcl
# outputs.tf

# Outputs VPC Information
# Useful for confirming network foundation and account context
output "vpc_info" {
  description = "Information about the created VPC"
  value = {
    vpc_id     = aws_vpc.main.id              
    vpc_cidr   = aws_vpc.main.cidr_block      
    igw_id     = aws_internet_gateway.main.id
    region     = data.aws_region.current.name
    account_id = data.aws_caller_identity.current.account_id
  }
}

# Outputs Subnet Information
# Helps verify where subnets landed
output "subnet_info" {
  description = "Information about created subnets"
  value = {
    public_subnet = {
      id         = aws_subnet.public.id
      cidr_block = aws_subnet.public.cidr_block
      az         = aws_subnet.public.availability_zone
    }
    private_subnet = {
      id         = aws_subnet.private.id
      cidr_block = aws_subnet.private.cidr_block
      az         = aws_subnet.private.availability_zone
    }
  }
}

# Outputs Security Group Information
# Useful to reference or modify SGs later
output "security_group_info" {
  description = "Information about created security groups"
  value = {
    public_sg_id  = aws_security_group.public_sg.id
    private_sg_id = aws_security_group.private_sg.id
  }
}

# Outputs EC2 Instance Information
# Critical for connecting, troubleshooting, or automating follow-up tasks
output "instance_info" {
  description = "Information about EC2 instances"
  value = {
    public_instance = {
      id         = aws_instance.public_ec2.id
      public_ip  = aws_instance.public_ec2.public_ip
      private_ip = aws_instance.public_ec2.private_ip
      ami_id     = aws_instance.public_ec2.ami
    }
    private_instance = {
      id         = aws_instance.private_ec2.id
      private_ip = aws_instance.private_ec2.private_ip
      ami_id     = aws_instance.private_ec2.ami
    }
  }
}

# Outputs NAT Gateway Information
# Helps confirm NAT setup and outbound address
output "nat_gateway_info" {
  description = "Information about NAT Gateway"
  value = {
    nat_gateway_id = aws_nat_gateway.nat.id
    elastic_ip     = aws_eip.nat.public_ip
  }
}

# Outputs VPC Flow Logs Information
# Useful to pull logs, configure alerts, or analyze traffic
output "flow_logs_info" {

  description = "Information about VPC Flow Logs"
  value = {
    log_group_name = aws_cloudwatch_log_group.vpc_logs.name
    log_group_arn  = aws_cloudwatch_log_group.vpc_logs.arn
  }
}

# Outputs SSH Command Shortcuts
# Improves usability, especially for fast testing or handover
output "ssh_commands" {
  description = "SSH commands to connect to instances"
  value = {
    public_instance  = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${aws_instance.public_ec2.public_ip}"
    private_instance = "ssh -i ~/.ssh/${var.key_name}.pem -o ProxyJump=ec2-user@${aws_instance.public_ec2.public_ip} ec2-user@${aws_instance.private_ec2.private_ip}"
  }
}
```

**Explanation:**

- Well-organized and grouped outputs.
- Includes useful operational details (IPs, IDs, names)
- Provides ready-to-use SSH access tips

**Possible Improvements**

- Add sensitive = true to hide any sensitive values (like internal IPs or commands) from Terraform CLI output.
- Provide outputs formatted as maps or lists. Will be useful for scaling to multiple instances or subnets.

---

## User Data Scripts

User data scripts are executed when EC2 instances boot for the first time. They provide a way to customize the instance configuration, install software, and set up initial system state. Both the public and private instances use bash scripts that perform similar initialization tasks.

### public-userdata.sh

```bash
#!/bin/bash
# user-data/public-userdata.sh
yum update -y
yum install -y htop tree wget curl

# Set hostname
hostnamectl set-hostname ${hostname}
echo "127.0.0.1 ${hostname}" >> /etc/hosts

# Install CloudWatch agent
yum install -y amazon-cloudwatch-agent

# Create a welcome message
cat > /etc/motd << 'EOF'
*****************************************************
*  Welcome to the Public EC2 Instance (Bastion)    *
*  This instance has internet access and can       *
*  be used to access private instances             *
*****************************************************
EOF

# Log instance startup
echo "$(date): Public instance ${hostname} started successfully" >> /var/log/terraform-deployment.log
```

**Explanation:**

- Updates system packages to latest versions for security.
- Installs essential system administration tools (htop for process monitoring, tree for directory visualization, wget and curl for downloads).
- Sets a dynamic hostname using the variable passed from Terraform's templatefile function.
- Configures the hostname in /etc/hosts for proper local name resolution.
- Installs the CloudWatch agent for monitoring and log collection.
- Creates a Message of the Day (MOTD) that displays when users SSH into the instance, clearly identifying it as a bastion host.
- Logs the successful startup to a local file for troubleshooting and audit purposes.

### private-userdata.sh

```bash
#!/bin/bash
# user-data/private-userdata.sh
yum update -y
yum install -y htop tree wget curl

# Set hostname
hostnamectl set-hostname ${hostname}
echo "127.0.0.1 ${hostname}" >> /etc/hosts

# Install CloudWatch agent
yum install -y amazon-cloudwatch-agent

# Create a welcome message
cat > /etc/motd << 'EOF'
*****************************************************
*  Welcome to the Private EC2 Instance             *
*  This instance is in a private subnet and        *
*  accessible only through the bastion host        *
*****************************************************
EOF

# Log instance startup
echo "$(date): Private instance ${hostname} started successfully" >> /var/log/terraform-deployment.log
```

**Explanation:**

- Performs identical system initialization tasks as the public instance script.
- Uses the same package management and tool installation approach.
- Sets the hostname dynamically using the Terraform-provided variable.
- Installs CloudWatch agent for consistent monitoring across both instances.
- Creates a distinct MOTD that identifies this as a private instance accessible only through the bastion host.
- Logs startup information to the same log file format for consistent operational tracking.

### Integration with Terraform

Both user data scripts are referenced in the main.tf file using Terraform's templatefile function:

```hcl
user_data = base64encode(templatefile("${path.module}/user-data/public-userdata.sh", {
  hostname = "${local.name_prefix}-public"
}))
```

The templatefile function allows Terraform to substitute variables into the scripts at deployment time. The hostname variable is populated with the project name and environment prefix, ensuring consistent naming across the infrastructure. The base64encode function is required because AWS expects user data to be base64 encoded.

These scripts establish a baseline configuration for both instances, ensuring they have the necessary tools for administration and monitoring while clearly identifying their role in the infrastructure through the welcome messages.

---

## Deployment Workflow Utilizing Terraform Commands

1. Initialize the Terraform project:
    
    ```hcl
    terraform init
    ```
    
2. Format the configuration:
    
    ```hcl
    terraform fmt
    ```
    
3. Validate the configuration:
    
    ```hcl
    terraform validate
    ```
    
4. Review the execution plan:
    
    ```hcl
    terraform plan
    ```
    
5. Apply the configuration to deploy resources:
    
    ```hcl
    terraform apply
    ```
    
6. When finished, clean up resources:
    
    ```hcl
    terraform destroy
    ```
    

---

## Deployment Workflow Utilizing PowerShell Script

This script is designed to automate and safeguard the Terraform deployment workflow. It ensures prerequisites, verifies configuration, assists the user, and executes Terraform commands in a structured, safe order.

```powershell
# Terraform Deployment Script

# ==========================================
# 1. PREREQUISITES CHECK
# ==========================================

Write-Host "Checking Terraform installation..." -ForegroundColor Yellow
terraform --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Terraform not found! Install from: https://www.terraform.io/downloads" -ForegroundColor Red
    exit 1
}

Write-Host "Checking AWS CLI..." -ForegroundColor Yellow
aws --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: AWS CLI not found! Install from: https://aws.amazon.com/cli/" -ForegroundColor Red
    exit 1
}

Write-Host "Checking AWS credentials..." -ForegroundColor Yellow
aws sts get-caller-identity
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: AWS credentials not configured! Run: aws configure" -ForegroundColor Red
    exit 1
}
  
# ==========================================
# 2. PROJECT SETUP
# ==========================================

Write-Host "Checking project directory..." -ForegroundColor Yellow
$CurrentDir = Split-Path -Leaf (Get-Location)
Write-Host "Current directory: $CurrentDir" -ForegroundColor Green

# Go up one level if we're in user-data directory
if ($CurrentDir -eq "user-data") {
    Set-Location ".."
    $CurrentDir = Split-Path -Leaf (Get-Location)
    Write-Host "Moved up to: $CurrentDir" -ForegroundColor Green
}

# Verify Terraform files exist
$TerraformFiles = @("main.tf", "variables.tf", "outputs.tf", "provider.tf", "data.tf", "locals.tf")
$MissingFiles = @()

foreach ($file in $TerraformFiles) {
    if (-not (Test-Path $file)) {
        $MissingFiles += $file
    }
} 

if ($MissingFiles.Count -gt 0) {
    Write-Host "ERROR: Missing Terraform files: $($MissingFiles -join ', ')" -ForegroundColor Red
    Write-Host "Make sure you're in the correct directory with your .tf files!" -ForegroundColor Red
    exit 1
}

Write-Host "SUCCESS: All Terraform files found" -ForegroundColor Green
  
# Check if terraform.tfvars exists
if (-not (Test-Path "terraform.tfvars")) {
    Write-Host "Creating terraform.tfvars template..." -ForegroundColor Yellow
    $TerraformVars = @"
# terraform.tfvars - Customize these values for your environment

# Required variables (you MUST set these)
key_name = "your-key-pair-name"              # Replace with your EC2 key pair name
home_ip  = "203.0.113.1/32"                 # Replace with your public IP + /32

# Optional customizations
project_name         = "tillynet-vpc-lab"
environment         = "dev"
vpc_cidr            = "10.0.0.0/16"
public_subnet_cidr  = "10.0.1.0/24"
private_subnet_cidr = "10.0.2.0/24"
availability_zone   = "us-west-1a"
instance_type       = "t2.micro"

# DNS settings
enable_dns_hostnames = true
enable_dns_support   = true
"@

    $TerraformVars | Out-File -FilePath "terraform.tfvars" -Encoding UTF8
    Write-Host "SUCCESS: Created terraform.tfvars template" -ForegroundColor Green
    Write-Host "IMPORTANT: Edit terraform.tfvars with your actual values before proceeding!" -ForegroundColor Red
}

# Check user-data directory
if (-not (Test-Path "user-data")) {
    Write-Host "ERROR: user-data directory not found!" -ForegroundColor Red
    exit 1
}

$UserDataFiles = @("user-data/public-userdata.sh", "user-data/private-userdata.sh")
foreach ($file in $UserDataFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "ERROR: Missing user-data script: $file" -ForegroundColor Red
        exit 1
    }
}
Write-Host "SUCCESS: User-data scripts found" -ForegroundColor Green
  
# ==========================================
# 3. GET PUBLIC IP
# ========================================== 

Write-Host "Getting your public IP address..." -ForegroundColor Yellow
try {
    $PublicIP = (Invoke-RestMethod -Uri "https://ifconfig.me/ip" -TimeoutSec 10).Trim()
    Write-Host "SUCCESS: Your public IP: $PublicIP" -ForegroundColor Green
    Write-Host "Make sure terraform.tfvars has: home_ip = `"$PublicIP/32`"" -ForegroundColor Cyan
    
    # Check if terraform.tfvars needs updating
    $TfVarsContent = Get-Content "terraform.tfvars" -Raw
    if ($TfVarsContent -match "203\.0\.113\.1/32") {
        Write-Host "WARNING: terraform.tfvars still has placeholder IP - update it!" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "ERROR: Could not get public IP. Get it from: https://whatismyipaddress.com/" -ForegroundColor Red
}

# ==========================================
# 4. TERRAFORM DEPLOYMENT
# ==========================================

Write-Host "`nSTARTING TERRAFORM DEPLOYMENT" -ForegroundColor Magenta
Write-Host "======================================" -ForegroundColor Magenta

# Function to run Terraform commands
function Invoke-TerraformCommand {
    param(
        [string]$Command,
        [string]$Description
    )
    Write-Host "`n$Description" -ForegroundColor Yellow
    Write-Host "Running: terraform $Command" -ForegroundColor Gray
    
    $StartTime = Get-Date
    Invoke-Expression "terraform $Command"
    $EndTime = Get-Date
    $Duration = $EndTime - $StartTime
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "SUCCESS: $Description completed (took $($Duration.TotalSeconds) seconds)" -ForegroundColor Green
        return $true
    } else {
        Write-Host "ERROR: $Description failed!" -ForegroundColor Red
        Write-Host "Check the output above for error details." -ForegroundColor Red
        return $false
    }
}

# Pre-deployment validation
Write-Host "`nValidating configuration..." -ForegroundColor Yellow
$TfVarsContent = Get-Content "terraform.tfvars" -Raw
if ($TfVarsContent -match "your-key-pair-name") {
    Write-Host "ERROR: terraform.tfvars still has placeholder key_name!" -ForegroundColor Red
    Write-Host "Create a key pair in AWS Console: EC2 -> Key Pairs -> Create" -ForegroundColor Yellow
    exit 1
}

# Step 1: Initialize
if (-not (Invoke-TerraformCommand "init" "Initializing Terraform")) {
    exit 1
}
  
# Step 2: Validate
if (-not (Invoke-TerraformCommand "validate" "Validating Terraform configuration")) {
    exit 1
}

# Step 3: Format
Invoke-TerraformCommand "fmt" "Formatting Terraform code"

# Step 4: Plan
Write-Host "`nCreating Terraform plan..." -ForegroundColor Yellow
Write-Host "This shows what resources will be created (NEW VPC + subnets + EC2s)." -ForegroundColor Gray
if (-not (Invoke-TerraformCommand "plan -out=tfplan" "Planning deployment")) {
    exit 1
}

# Step 5: Confirm
Write-Host "`nReady to deploy infrastructure?" -ForegroundColor Yellow
Write-Host "This will create a NEW VPC with all resources (NAT Gateway costs about $32/month)." -ForegroundColor Red
Write-Host "Resources to be created:" -ForegroundColor Cyan
Write-Host "- New VPC (10.0.0.0/16)" -ForegroundColor White
Write-Host "- Internet Gateway" -ForegroundColor White
Write-Host "- Public and Private Subnets" -ForegroundColor White
Write-Host "- NAT Gateway (about $32/month)" -ForegroundColor White
Write-Host "- 2 EC2 instances (t2.micro - free tier)" -ForegroundColor White
Write-Host "- Security Groups, Route Tables, VPC Flow Logs" -ForegroundColor White

$Confirmation = Read-Host "Type 'yes' to proceed with deployment"

if ($Confirmation -eq "yes") {
    # Step 6: Apply
    if (Invoke-TerraformCommand "apply tfplan" "Applying Terraform plan") {
        Write-Host "`nDEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
        Write-Host "======================================" -ForegroundColor Green
        
        # Show outputs
        Write-Host "`nInfrastructure Details:" -ForegroundColor Cyan
        terraform output

        # Cleanup
        Remove-Item "tfplan" -ErrorAction SilentlyContinue
        Write-Host "`nNext Steps:" -ForegroundColor Yellow
        Write-Host "1. Check AWS Console to see created resources" -ForegroundColor White
        Write-Host "2. Use SSH commands from output to connect to instances" -ForegroundColor White
        Write-Host "3. Test connectivity: Public -> Private instance" -ForegroundColor White
        Write-Host "4. When done testing, run: terraform destroy" -ForegroundColor White
        Write-Host "`nUseful AWS Console Links:" -ForegroundColor Yellow
        Write-Host "- VPC Dashboard: https://console.aws.amazon.com/vpc/" -ForegroundColor White
        Write-Host "- EC2 Dashboard: https://console.aws.amazon.com/ec2/" -ForegroundColor White
        Write-Host "- CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/" -ForegroundColor White
    }
} else {
    Write-Host "Deployment cancelled by user." -ForegroundColor Red
    Remove-Item "tfplan" -ErrorAction SilentlyContinue
}

# ==========================================
# 5. HELPFUL COMMANDS
# ==========================================

Write-Host "`nUSEFUL TERRAFORM COMMANDS:" -ForegroundColor Magenta
Write-Host "======================================" -ForegroundColor Magenta
Write-Host "terraform show           # Show current state" -ForegroundColor White
Write-Host "terraform output         # Show outputs again" -ForegroundColor White
Write-Host "terraform state list     # List all resources" -ForegroundColor White
Write-Host "terraform plan           # Plan changes" -ForegroundColor White
Write-Host "terraform apply          # Apply changes" -ForegroundColor White
Write-Host "terraform destroy        # Delete all resources" -ForegroundColor White

Write-Host "`nTROUBLESHOOTING:" -ForegroundColor Magenta
Write-Host "======================================" -ForegroundColor Magenta
Write-Host "- Error about credentials: Run 'aws configure'" -ForegroundColor White
Write-Host "- Error about regions: Check availability_zone variable" -ForegroundColor White
Write-Host "- Error about key pairs: Create key pair in EC2 console first" -ForegroundColor White
Write-Host "- Error about permissions: Ensure your AWS user has admin rights" -ForegroundColor White

Write-Host "`nDeployment script completed!" -ForegroundColor Green
```

### 1. Prerequisite Checks

Checks if:

- Terraform is installed (`terraform --version`)
- AWS CLI is installed (`aws --version`)
- AWS CLI credentials are configured (`aws sts get-caller-identity`)

If any of these checks fail, the script exits early to prevent wasted runs.

- Prevents runtime errors later by confirming the local environment is ready.

### 2. Project Directory Setup

- Checks if you're inside the `terraform-vpc-lab` directory.
- If you're in the `user-data` subfolder, moves up one level.
- Verifies critical Terraform files are present (`main.tf`, `variables.tf`, etc.).
- Creates a `terraform.tfvars` template if it doesn't exist, reminding the user to fill in actual values.

Prevents mistakes from running Terraform in the wrong folder or with missing config.

### 3. Public IP Check

- Retrieves the users current public IP using an external API `https://ifconfig.me/ip`.
- Alerts if the placeholder `203.0.113.1/32` is still in your `terraform.tfvars`.

Ensures Security Group `home_ip` is set properly thus allowing SSH in.

### 4. Terraform Deployment Steps

Uses a helper function `Invoke-TerraformCommand` that:

- Runs a Terraform command.
    
- Tracks execution time.
    
- Checks success or failure.
    
- Provides colorful, clear user feedback.
    

Commands it runs in sequence:

1. `terraform init` → initializes backend + providers.
    
2. `terraform validate` → checks configuration syntax.
    
3. `terraform fmt` → formats the Terraform code.
    
4. `terraform plan -out=tfplan` → creates an executable plan file.
    
5. Prompts the user:
    
    - Explicit user confirmation before applying.
6. `terraform apply tfplan` → deploys the infrastructure.
    
7. After apply:
    
    - Shows `terraform output`.
        
    - Cleans up the `tfplan` file.
        
    - Lists helpful AWS console links.
        

Automates best practices and reduces human error in the apply phase.

### 5. Helpful Commands + Troubleshooting

At the end, it prints:

- Common Terraform CLI commands for post-deployment work.
    
- Troubleshooting tips for:
    
    - Credential issues
        
    - Region mismatches
        
    - Key pair errors
        
    - Permissions problems
        

Gives the user guidance on what to do after deployment or if something goes wrong.

### Why Utilize PowerShell Deployment

- Clear, user-friendly feedback using color and prompts.
- Safety checks to prevent misconfigured runs.
- Scripted generation of tfvars template to help beginners.
- Modular Terraform command function for reusability.
- Includes time tracking and success/failure detection.

### Potential Improvements

Add error handling for:

- Network timeouts when fetching public IP.
- `terraform` command not found inside restricted environments.
- Support for custom -var-file input if multiple environments (dev, prod).
- Support an optional `terraform destroy` flag or mode for teardown automation.
- Log output to a file for post-run audit.

---

## Best Practices and Notes

- Use environment variables or `terraform.tfvars` to avoid hardcoding sensitive values (like your home IP) in `.tf` files.
    
- Always run `terraform plan` before `apply` to review changes.
    
- Ensure your AMI IDs are up-to-date for your target region.
    
- Keep `.tfstate` files secure, especially when using sensitive outputs.
    
- Use `.gitignore` to exclude sensitive files if committing the project to version control.