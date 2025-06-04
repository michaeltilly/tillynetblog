---
title: "Building a Hybrid Cloud: AWS Site-to-Site VPN with pfSense and Terraform"
date: 2025-06-03
tags: ["AWS", "On-Premise", "Hybrid Cloud", "VPC", "VPN", "IPsec", "terraform", "PfSense", "infrastructure-as-code", "network automation", "cloud deployment"]
cloud_provider: "AWS"
categories: ["Cloud Engineering Labs"]
draft: false
---

In this post, I'll walk through the complete process of establishing a Site-to-Site VPN connection between my on-premise pfSense firewall and AWS, creating a true hybrid cloud environment. This project demonstrates enterprise-grade network integration, secure tunnel establishment, and Infrastructure as Code principles.

## Project Overview

The goal was to extend my existing home lab network (TillyNet) to AWS, enabling seamless communication between on-premise resources and cloud workloads. This creates opportunities for hybrid applications, cloud bursting, and distributed infrastructure management.

### Architecture Summary

```
On-Premise Network (TillyNet)           AWS Cloud Environment
┌─────────────────────────────┐         ┌─────────────────────────────┐
│ pfSense Firewall            │         │ AWS VPC (10.1.0.0/16)       │
│ Multiple VLANs:             │◄────────┤                             │
│ - VLAN 1: 172.16.7.0/24     │ IPsec   │ - Public: 10.1.1.0/24       │
│ - VLAN 14: 172.16.14.0/24   │ Tunnel  │ - Private: 10.1.2.0/24      │
│ - VLAN 21: 172.21.21.0/24   │         │                             │
│ - VLAN 99: 172.16.99.0/24   │         │ EC2 Instances               │
│ - XPS Subnet: 172.30.30.0/24│         │ NAT Gateway                 │
└─────────────────────────────┘         └─────────────────────────────┘
```

## Prerequisites

- **On-Premise Requirements**:
    - pfSense firewall with public IP address
    - Properly configured VLANs and routing
    - Administrative access to firewall configuration
- **AWS Requirements**:
    - AWS account with appropriate IAM permissions
    - AWS CLI configured with access keys
    - Terraform installed locally
- **Network Requirements**:
    - Non-overlapping IP address spaces
    - Static public IP address (recommended)
    - Understanding of IPsec protocols

## Phase 1: AWS Infrastructure Deployment

The first phase involves creating the AWS networking infrastructure using Terraform. This approach ensures reproducible, version-controlled infrastructure that can be easily modified and redeployed.

### Terraform Project Structure

I organized the Terraform code into logical files for maintainability:

```
tillynet-aws-hybrid-deployment/
├── main.tf                 # Primary resource definitions
├── variables.tf            # Input variable declarations
├── outputs.tf              # Output value definitions
├── locals.tf               # Local value computations
├── data.tf                 # Data source definitions
├── terraform.tfvars        # Variable value assignments
└── README.md               # Project documentation
```

### Variable Definitions

The `variables.tf` file defines all configurable parameters for the deployment:

```hcl
# variables.tf - Input parameter definitions

variable "aws_region" {
  description = "AWS region for VPC deployment"
  type        = string
  default     = "us-west-1"
  
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "AWS region must be in valid format (e.g., us-west-1)."
  }
}

variable "home_public_ip" {
  description = "Public IP address of on-premise network"
  type        = string
  
  validation {
    condition     = can(cidrhost("${var.home_public_ip}/32", 0))
    error_message = "Must be a valid IPv4 address."
  }
}

variable "project_name" {
  description = "Project identifier for resource naming and tagging"
  type        = string
  default     = "tillynet-hybrid"
  
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]*$", var.project_name))
    error_message = "Project name must start with letter and contain only alphanumeric characters and hyphens."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for AWS VPC"
  type        = string
  default     = "10.1.0.0/16"
  
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

variable "public_subnet_cidr" {
  description = "CIDR block for public subnet"
  type        = string
  default     = "10.1.1.0/24"
}

variable "private_subnet_cidr" {
  description = "CIDR block for private subnet"
  type        = string
  default     = "10.1.2.0/24"
}
```

The validation blocks ensure that input values meet expected formats and constraints, preventing common configuration errors during deployment.

### Local Values and Data Sources

The `locals.tf` file computes reusable values and establishes naming conventions:

```hcl
# locals.tf - Computed values and constants

locals {
  # Standardized resource tagging for cost allocation and management
  common_tags = {
    Project     = var.project_name
    Environment = "hybrid"
    ManagedBy   = "Terraform"
    CreatedAt   = timestamp()
    Purpose     = "Hybrid-Cloud-Connectivity"
  }
  
  # Consistent naming convention across all resources
  name_prefix = "${var.project_name}-hybrid"
  
  # On-premise network definitions for VPN routing
  # These represent the existing VLAN structure in my home lab
  home_networks = [
    "172.16.7.0/24",   # Default/Legacy VLAN
    "172.16.14.0/24",  # Guest Wi-Fi Network
    "172.21.21.0/24",  # Production Services (DNS, etc.)
    "172.16.99.0/24",  # Management Network
    "172.30.30.0/24"   # Proxmox XPS Subnet
  ]
}
```

The `data.tf` file queries AWS for dynamic information:

```hcl
# data.tf - External data source queries

# Current AWS region information
data "aws_region" "current" {}

# AWS account identity for resource ARN construction
data "aws_caller_identity" "current" {}

# Available Availability Zones in the selected region
data "aws_availability_zones" "available" {
  state = "available"
}

# Latest Amazon Linux 2 AMI for EC2 instances
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
  
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
```

### Core Network Infrastructure

The `main.tf` file contains the primary infrastructure definitions. Here's the VPC and networking setup:

```hcl
# main.tf - Primary infrastructure resources

# Provider configuration
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Virtual Private Cloud - The foundation of our AWS network
resource "aws_vpc" "hybrid_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true  # Required for proper hostname resolution
  enable_dns_support   = true  # Enables DNS resolution within VPC
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}

# Internet Gateway - Provides internet access to public subnets
resource "aws_internet_gateway" "hybrid_igw" {
  vpc_id = aws_vpc.hybrid_vpc.id
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

# Public Subnet - Hosts NAT Gateway and potential bastion hosts
resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.hybrid_vpc.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true  # Auto-assign public IPs to instances
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-subnet"
    Type = "Public"
  })
}

# Private Subnet - Hosts hybrid workloads accessible via VPN
resource "aws_subnet" "private_subnet" {
  vpc_id            = aws_vpc.hybrid_vpc.id
  cidr_block        = var.private_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-subnet"
    Type = "Private"
  })
}

# Elastic IP for NAT Gateway - Provides static outbound IP
resource "aws_eip" "nat_eip" {
  domain = "vpc"
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-eip"
  })
  
  depends_on = [aws_internet_gateway.hybrid_igw]
}

# NAT Gateway - Enables outbound internet access for private subnet
resource "aws_nat_gateway" "hybrid_nat" {
  allocation_id = aws_eip.nat_eip.id
  subnet_id     = aws_subnet.public_subnet.id
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-gateway"
  })
  
  depends_on = [aws_internet_gateway.hybrid_igw]
}
```

### Routing Configuration

Proper routing ensures traffic flows correctly between subnets and to the internet:

```hcl
# Public Route Table - Directs traffic to Internet Gateway
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.hybrid_vpc.id
  
  # Default route to internet for public subnet
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.hybrid_igw.id
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-rt"
    Type = "Public"
  })
}

# Private Route Table - Directs traffic to NAT Gateway for internet access
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.hybrid_vpc.id
  
  # Default route through NAT Gateway for outbound traffic
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.hybrid_nat.id
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-rt"
    Type = "Private"
  })
}

# Route Table Associations - Link subnets to appropriate route tables
resource "aws_route_table_association" "public_rta" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "private_rta" {
  subnet_id      = aws_subnet.private_subnet.id
  route_table_id = aws_route_table.private_rt.id
}
```

### VPN Infrastructure Components

The Site-to-Site VPN requires three AWS components: Customer Gateway, Virtual Private Gateway, and the VPN Connection itself.

```hcl
# Customer Gateway - Represents the on-premise pfSense firewall
resource "aws_customer_gateway" "tillynet_cgw" {
  bgp_asn    = 65000  # Private ASN required by AWS (not used for static routing)
  ip_address = var.home_public_ip
  type       = "ipsec.1"  # Only supported VPN type
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-customer-gateway"
  })
}

# Virtual Private Gateway - AWS-side VPN endpoint
resource "aws_vpn_gateway" "hybrid_vgw" {
  vpc_id = aws_vpc.hybrid_vpc.id
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpn-gateway"
  })
}

# Site-to-Site VPN Connection with enhanced security parameters
resource "aws_vpn_connection" "tillynet_vpn" {
  customer_gateway_id = aws_customer_gateway.tillynet_cgw.id
  vpn_gateway_id      = aws_vpn_gateway.hybrid_vgw.id
  type                = "ipsec.1"
  static_routes_only  = true  # Use static routing instead of BGP
  
  # Enhanced tunnel options for improved security
  tunnel1_ike_versions                 = ["ikev2"]
  tunnel1_phase1_encryption_algorithms = ["AES256"]
  tunnel1_phase1_integrity_algorithms  = ["SHA2-256"]
  tunnel1_phase1_dh_group_numbers      = [14]
  tunnel1_phase2_encryption_algorithms = ["AES256"]
  tunnel1_phase2_integrity_algorithms  = ["SHA2-256"]
  tunnel1_phase2_dh_group_numbers      = [14]
  
  tunnel2_ike_versions                 = ["ikev2"]
  tunnel2_phase1_encryption_algorithms = ["AES256"]
  tunnel2_phase1_integrity_algorithms  = ["SHA2-256"]
  tunnel2_phase1_dh_group_numbers      = [14]
  tunnel2_phase2_encryption_algorithms = ["AES256"]
  tunnel2_phase2_integrity_algorithms  = ["SHA2-256"]
  tunnel2_phase2_dh_group_numbers      = [14]
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpn-connection"
  })
}

# Static routes for on-premise networks
resource "aws_vpn_connection_route" "home_routes" {
  count                  = length(local.home_networks)
  vpn_connection_id      = aws_vpn_connection.tillynet_vpn.id
  destination_cidr_block = local.home_networks[count.index]
}

# Enable automatic route propagation to private route table
resource "aws_vpn_gateway_route_propagation" "private_propagation" {
  vpn_gateway_id = aws_vpn_gateway.hybrid_vgw.id
  route_table_id = aws_route_table.private_rt.id
}
```

### Test Instance for Connectivity Validation

To validate the hybrid connection, I deployed a test EC2 instance with appropriate security configurations:

```hcl
# Security Group for test instance - Allows connectivity from on-premise networks
resource "aws_security_group" "test_instance_sg" {
  name_prefix = "${local.name_prefix}-test-sg-"
  description = "Security group for hybrid connectivity testing"
  vpc_id      = aws_vpc.hybrid_vpc.id
  
  # Allow ICMP (ping) from all on-premise networks
  ingress {
    description = "ICMP from on-premise networks"
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = local.home_networks
  }
  
  # Allow SSH access from on-premise networks
  ingress {
    description = "SSH from on-premise networks"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = local.home_networks
  }
  
  # Allow all outbound traffic
  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-test-sg"
  })
  
  lifecycle {
    create_before_destroy = true
  }
}

# Test EC2 instance in private subnet
resource "aws_instance" "test_instance" {
  ami                     = data.aws_ami.amazon_linux.id
  instance_type           = "t2.micro"  # Free tier eligible
  subnet_id               = aws_subnet.private_subnet.id
  vpc_security_group_ids  = [aws_security_group.test_instance_sg.id]
  
  # User data script for instance initialization
  user_data = base64encode(<<-EOF
    #!/bin/bash
    yum update -y
    yum install -y htop tree wget curl
    
    # Create identification file
    cat > /etc/motd << 'WELCOME'
*************************************************
*      AWS Hybrid Connectivity Test Instance   *
*************************************************
WELCOME
    
    echo "$(date): Hybrid test instance initialized" >> /var/log/hybrid-setup.log
  EOF
  )
  
  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-test-instance"
    Purpose = "Hybrid connectivity validation"
  })
}
```

### Output Definitions

The `outputs.tf` file defines important values needed for pfSense configuration:

```hcl
# outputs.tf - Important values for manual configuration steps

output "vpn_connection_details" {
  description = "VPN connection configuration parameters for pfSense"
  value = {
    vpn_connection_id   = aws_vpn_connection.tillynet_vpn.id
    tunnel_1_address    = aws_vpn_connection.tillynet_vpn.tunnel1_address
    tunnel_2_address    = aws_vpn_connection.tillynet_vpn.tunnel2_address
    tunnel_1_psk        = aws_vpn_connection.tillynet_vpn.tunnel1_preshared_key
    tunnel_2_psk        = aws_vpn_connection.tillynet_vpn.tunnel2_preshared_key
    customer_gateway_ip = var.home_public_ip
  }
  sensitive = true  # Hides sensitive values in console output
}

output "aws_vpc_info" {
  description = "AWS VPC infrastructure details"
  value = {
    vpc_id              = aws_vpc.hybrid_vpc.id
    vpc_cidr            = aws_vpc.hybrid_vpc.cidr_block
    public_subnet_id    = aws_subnet.public_subnet.id
    private_subnet_id   = aws_subnet.private_subnet.id
    vpn_gateway_id      = aws_vpn_gateway.hybrid_vgw.id
    test_instance_ip    = aws_instance.test_instance.private_ip
  }
}

output "connectivity_test_commands" {
  description = "Commands for testing hybrid connectivity"
  value = {
    ping_aws_from_home = "ping ${aws_instance.test_instance.private_ip}"
    ping_home_from_aws = "ping [your-home-network-ip]"
    ssh_to_aws         = "ssh ec2-user@${aws_instance.test_instance.private_ip}"
  }
}
```

### Variable Values Configuration

The `terraform.tfvars` file contains environment-specific values:

```hcl
# terraform.tfvars - Environment-specific configuration values
# Note: This file should not be committed to version control

aws_region          = "us-west-1"
home_public_ip      = "[YOUR_PUBLIC_IP_HERE]"  # Replace with actual public IP
project_name        = "tillynet-hybrid"
vpc_cidr            = "10.1.0.0/16"
public_subnet_cidr  = "10.1.1.0/24"
private_subnet_cidr = "10.1.2.0/24"
```

## Phase 2: AWS Infrastructure Deployment

With the Terraform configuration complete, I deployed the AWS infrastructure:

### Deployment Process

```bash
# Initialize Terraform and download required providers
terraform init

# Validate configuration syntax and logic
terraform validate

# Review planned changes before deployment
terraform plan

# Deploy the infrastructure
terraform apply
```

### Deployment Verification

After successful deployment, I verified the infrastructure:

```bash
# Retrieve VPN connection details for pfSense configuration
terraform output vpn_connection_details

# Get AWS infrastructure information
terraform output aws_vpc_info

# Verify VPN connection status
aws ec2 describe-vpn-connections --vpn-connection-ids [VPN_CONNECTION_ID]
```

The deployment created:

- VPC with public and private subnets
- Internet Gateway and NAT Gateway for connectivity
- Virtual Private Gateway attached to the VPC
- Customer Gateway representing my pfSense firewall
- Site-to-Site VPN connection with two redundant tunnels
- Static routes for all on-premise networks
- Test EC2 instance with appropriate security groups

## Phase 3: pfSense IPsec Configuration

With AWS infrastructure deployed, I configured the pfSense firewall to establish the IPsec tunnels.

### Phase 1 (IKE) Configuration

For each tunnel, I created Phase 1 entries in pfSense:

**Navigation**: VPN > IPsec > Add P1

#### Tunnel 1 Configuration:

- **Disabled**: Unchecked
- **Key Exchange version**: IKEv2
- **Internet Protocol**: IPv4
- **Interface**: WAN
- **Remote Gateway**: [AWS_TUNNEL_1_ADDRESS]
- **Description**: AWS VPN Tunnel 1

#### Authentication Settings:

- **Authentication Method**: Mutual PSK
- **Negotiation Mode**: Main
- **My identifier**: My IP address
- **Peer identifier**: Peer IP address
- **Pre-Shared Key**: [AWS_TUNNEL_1_PSK]

#### Encryption Parameters:

- **Encryption Algorithm**: AES 256 bits
- **Hash Algorithm**: SHA2-256
- **DH Group**: 14 (2048 bit)
- **Lifetime**: 28800 seconds

#### Advanced Options:

- **NAT Traversal**: Auto
- **Dead Peer Detection**: Enabled
- **Delay**: 10 seconds
- **Max failures**: 3

### Phase 2 (IPsec) Configuration

For each Phase 1, I created corresponding Phase 2 entries:

**Navigation**: VPN > IPsec > Show Phase 2 Entries > Add P2

#### Network Configuration:

- **Mode**: Tunnel IPv4
- **Local Network**: Network - 0.0.0.0/0 (any)
- **Remote Network**: Network - 10.1.0.0/16 (AWS VPC)

#### Security Parameters:

- **Protocol**: ESP
- **Encryption Algorithms**: AES 256 bits
- **Hash Algorithms**: SHA2-256
- **PFS key group**: 14 (2048 bit)
- **Lifetime**: 3600 seconds

#### Advanced Configuration:

- **Automatically ping host**: 10.1.0.1

I replicated this configuration for Tunnel 2 with the appropriate endpoint address and pre-shared key.

### Firewall Rules Configuration

#### IPsec Interface Rules

**Navigation**: Firewall > Rules > IPsec

I created a rule to allow all traffic through the VPN tunnels (this rule will later be more restrictive but for now this allowed testing traffic through the tunnel):

- **Action**: Pass
- **Interface**: IPsec
- **Address Family**: IPv4
- **Protocol**: Any
- **Source**: Any
- **Destination**: Any
- **Description**: Allow all traffic through VPN tunnels

#### VLAN Interface Rules

For each VLAN interface, I added rules allowing traffic to AWS:

**Navigation**: Firewall > Rules > [VLAN_Interface]

Example for Management VLAN:

- **Action**: Pass
- **Interface**: MGMT
- **Protocol**: Any
- **Source**: MGMT net (172.16.99.0/24)
- **Destination**: 10.1.0.0/16
- **Description**: Allow Management VLAN to AWS VPC

## Phase 4: Connection Establishment and Testing

### Tunnel Establishment

After applying all configurations, I established the tunnels:

1. **Status > IPsec > Overview**
2. Clicked "Connect P1 and P2s" for both tunnels
3. Verified both tunnels showed "Established" status

### AWS-Side Verification

I confirmed tunnel status from AWS:

```bash
# Check tunnel status
aws ec2 describe-vpn-connections --vpn-connection-ids [VPN_ID] \
  --query 'VpnConnections[0].VgwTelemetry'
```

Expected output showed Tunnel 1 as "UP" and Tunnel 2 as "DOWN" (normal for active/passive configuration).

### Connectivity Testing

#### Test 1: AWS Infrastructure Ping

```bash
# From pfSense Diagnostics > Ping
ping [AWS_EC2_INSTANCE_IP]  # Should succeed
```

#### Test 2: Bidirectional Connectivity

```bash
# From on-premise management network
ping [AWS_EC2_INSTANCE_IP]

# From AWS EC2 instance
ping [ON_PREMISE_DEVICE_IP]
```

#### Test 3: Application-Level Testing

```bash
# SSH from on-premise to AWS (if keys configured)
ssh ec2-user@[AWS_EC2_INSTANCE_IP]

# HTTP/HTTPS services (if configured)
curl http://[AWS_EC2_INSTANCE_IP]
```

## Troubleshooting and Resolution

### Challenge 1: Route Table Issues

**Problem**: pfSense wasn't automatically creating routes to AWS networks despite established tunnels.

**Solution**: Added "Automatically ping host" parameter in Phase 2 configuration pointing to AWS VPC gateway (10.1.0.1). This forces pfSense to maintain active routes through the tunnel.

### Challenge 2: AWS Security Group Configuration

**Problem**: Initial ping tests failed due to restrictive default security groups.

**Solution**: Created explicit security group rules allowing ICMP and SSH traffic from on-premise network ranges to AWS resources.

### Challenge 3: Tunnel Authentication Issues

**Problem**: Initial configuration used weaker encryption (SHA-1, DH Group 2).

**Solution**: Updated both AWS VPN connection and pfSense configuration to use stronger parameters:

- IKEv2 instead of IKEv1
- AES-256 instead of AES-128
- SHA2-256 instead of SHA-1
- DH Group 14 instead of Group 2

## Security Considerations

### Network Segmentation

- AWS VPC uses non-overlapping IP space (10.1.0.0/16)
- On-premise networks remain segmented by existing VLAN structure
- VPN provides encrypted tunnel between environments

### Access Control

- Security groups limit AWS resource access to specific on-premise networks
- pfSense firewall rules control which VLANs can access AWS resources
- Principle of least privilege applied throughout

### Encryption Standards

- IKEv2 with AES-256 encryption
- SHA2-256 integrity checking
- Perfect Forward Secrecy (PFS) enabled
- Strong Diffie-Hellman groups (Group 14)

### Monitoring and Logging

- AWS VPC Flow Logs capture network traffic
- pfSense logs IPsec tunnel status and traffic
- CloudTrail logs AWS API activities

## Performance and Cost Considerations

### Network Performance

- VPN provides approximately 1.25 Gbps throughput
- Latency depends on geographic distance to AWS region
- Dual tunnels provide redundancy and failover capability

### Cost Structure

- AWS VPN Connection: $36/month base cost
- NAT Gateway: $45/month plus data processing
- Data transfer charges apply for cross-VPN traffic
- EC2 instances: Variable based on usage

### Optimization Opportunities

- Use VPC Endpoints to reduce NAT Gateway usage
- Implement lifecycle policies for temporary resources
- Monitor data transfer patterns for cost optimization

## Future Enhancements

### Automation Improvements

- Implement Terraform modules for reusability
- Add automated testing for tunnel connectivity
- Create CI/CD pipeline for infrastructure changes

### Security Enhancements

- Implement AWS Config for compliance monitoring
- Add AWS GuardDuty for threat detection
- Configure AWS Security Hub for centralized security management

### Operational Improvements

- Set up CloudWatch monitoring for VPN metrics
- Implement automated failover testing
- Add backup VPN connection for additional redundancy

## Conclusion

This project successfully established a production-grade Site-to-Site VPN between my on-premise pfSense infrastructure and AWS, creating a true hybrid cloud environment. The implementation demonstrates several key technical concepts:

**Infrastructure as Code**: Using Terraform ensured reproducible, version-controlled infrastructure deployment with proper validation and documentation.

**Network Security**: The solution implements enterprise-grade encryption and access controls while maintaining network segmentation and the principle of least privilege.

**Hybrid Architecture**: The established connection enables seamless communication between on-premise and cloud resources, opening possibilities for distributed applications, cloud bursting, and hybrid backup strategies.

**Operational Excellence**: Comprehensive monitoring, logging, and documentation support ongoing management and troubleshooting.

The resulting infrastructure provides a solid foundation for hybrid cloud applications and demonstrates practical implementation of enterprise networking concepts in a home lab environment. This setup now enables exploration of advanced hybrid scenarios including cross-environment authentication, distributed databases, and multi-cloud architectures.

### Key Takeaways

1. **Planning is Critical**: Proper IP address planning prevents conflicts and simplifies routing configuration.
    
2. **Security by Design**: Implementing strong encryption and access controls from the beginning is easier than retrofitting security later.
    
3. **Testing Methodology**: Systematic testing from basic connectivity to application-level validation ensures reliable operation.
    
4. **Documentation Value**: Thorough documentation accelerates troubleshooting and enables knowledge sharing.
    

This hybrid cloud setup now serves as a platform for continued learning and experimentation with enterprise cloud technologies and networking concepts.