---
title: "Building a Secure Hybrid Cloud Infrastructure with AWS VPN and DNS Integration"
date: 2025-06-04
tags: ["AWS", "On-Premise", "Hybrid Cloud", "Route 53", "DNS", "Samba4", "EC2", "Bastion", "VPC", "VPN", "IPsec", "terraform", "PfSense", "infrastructure-as-code", "network automation", "cloud deployment"]
cloud_provider: "AWS"
categories: ["Cloud Engineering Labs"]
draft: false
---

## Overview

This post documents my journey building a production-grade hybrid cloud infrastructure that securely connects my on-premises homelab environment with AWS. The implementation demonstrates enterprise-level network segmentation, DNS integration, and security practices using Infrastructure as Code (IaC) principles.

## Architecture Goals

My primary objectives were to:

- **Establish secure connectivity** between on-premises and AWS environments
- **Implement seamless DNS resolution** across both environments
- **Maintain security isolation** while enabling necessary communication
- **Use Infrastructure as Code** for reproducible deployments
- **Follow enterprise best practices** for hybrid cloud architectures

## On-Premises Infrastructure Overview

My existing homelab infrastructure includes:

- **Samba4 Active Directory Domain Controller** (172.30.30.30) - Authoritative DNS for `tillynet.lan`
- **Pi-hole DNS Server** (172.21.21.21) - Recursive DNS with ad-blocking
- **pfSense Firewall/Router** - Network segmentation and routing
- **VLAN Segmentation**:
    - VLAN 1: Default/legacy (172.16.7.0/24)
    - VLAN 14: Guest Wi-Fi (172.16.14.0/24)
    - VLAN 21: Production (172.21.21.0/24)
    - VLAN 99: Management (172.16.99.0/24)
    - Infrastructure subnet: (172.30.30.0/24)

### DNS Hierarchy

My DNS architecture follows enterprise patterns:

```
Client Queries → Samba4 AD DC (Authoritative) → Pi-hole (Recursive) → External DNS
```

This design provides centralized domain management while maintaining ad-blocking and filtering capabilities.

## AWS Infrastructure Design

### Network Architecture

I designed the AWS VPC to avoid IP conflicts with my on-premises networks:

```hcl
# locals.tf
locals {
  # AWS VPC CIDR - ensuring no overlap with home networks
  vpc_cidr = "10.1.0.0/16"

  # Subnet CIDRs
  public_subnet_cidr  = "10.1.1.0/24"
  private_subnet_cidr = "10.1.2.0/24"

  # My home network CIDRs
  home_networks = [
    "172.16.7.0/24",  # Default/legacy VLAN 1
    "172.16.14.0/24", # Guest Wi-Fi VLAN 14
    "172.21.21.0/24", # Production VLAN 21
    "172.16.99.0/24", # Management VLAN 99
    "172.30.30.0/24"  # Internal Infrastructure Subnet
  ]
}
```

### VPC and Core Infrastructure

```hcl
# main.tf
# VPC for hybrid connectivity
resource "aws_vpc" "hybrid_vpc" {
  cidr_block           = local.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-hybrid-vpc"
  })
}

# Public Subnet (for NAT Gateway, bastion, etc.)
resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.hybrid_vpc.id
  cidr_block              = local.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-public-subnet"
    Type = "Public"
  })
}

# Private Subnet (for hybrid workloads)
resource "aws_subnet" "private_subnet" {
  vpc_id            = aws_vpc.hybrid_vpc.id
  cidr_block        = local.private_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-private-subnet"
    Type = "Private"
  })
}
```

This architecture provides:

- **Network isolation** between public and private resources
- **NAT Gateway** for outbound internet access from private subnet
- **Route table separation** for granular traffic control

## VPN Connectivity Implementation

### Customer Gateway and VPN Connection

```hcl
# Customer Gateway (represents my pfSense firewall)
resource "aws_customer_gateway" "tillynet_cgw" {
  bgp_asn    = 65000 # Standard private ASN
  ip_address = var.home_public_ip
  type       = "ipsec.1"

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-tillynet-gateway"
  })
}

# Virtual Private Gateway
resource "aws_vpn_gateway" "hybrid_vgw" {
  vpc_id = aws_vpc.hybrid_vpc.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpn-gateway"
  })
}

# VPN Connection
resource "aws_vpn_connection" "tillynet_vpn_enhanced" {
  customer_gateway_id = aws_customer_gateway.tillynet_cgw.id
  vpn_gateway_id      = aws_vpn_gateway.hybrid_vgw.id
  type                = "ipsec.1"
  static_routes_only  = true

  # Enhanced tunnel options with correct AWS values
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
    Name = "${var.project_name}-vpn-connection-enhanced"
  })
}
```

### VPN Route Configuration

```hcl
# VPN Connection Routes (for my home networks)
resource "aws_vpn_connection_route" "home_routes_enhanced" {
  count                  = length(local.home_networks)
  vpn_connection_id      = aws_vpn_connection.tillynet_vpn_enhanced.id
  destination_cidr_block = local.home_networks[count.index]
}

# Propagate VPN routes to private route table
resource "aws_vpn_gateway_route_propagation" "private_propagation_enhanced" {
  vpn_gateway_id = aws_vpn_gateway.hybrid_vgw.id
  route_table_id = aws_route_table.private_rt.id
  depends_on     = [aws_vpn_connection.tillynet_vpn_enhanced]
}
```

This configuration automatically advertises all my on-premises networks to AWS and enables route propagation for seamless connectivity.

## DNS Infrastructure Design

### Route 53 Resolver Endpoints

To enable bi-directional DNS resolution, I implemented Route 53 Resolver endpoints:

```hcl
# dns.tf
# Route 53 Resolver Inbound Endpoint (for on-prem to AWS queries)
resource "aws_route53_resolver_endpoint" "inbound" {
  name      = "${var.project_name}-inbound-resolver"
  direction = "INBOUND"

  security_group_ids = [aws_security_group.dns_resolver_sg.id]

  ip_address {
    subnet_id = aws_subnet.private_subnet.id
    ip        = "10.1.2.10"
  }

  ip_address {
    subnet_id = aws_subnet.public_subnet.id
    ip        = "10.1.1.10"
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-inbound-resolver"
  })
}

# Route 53 Resolver Outbound Endpoint (for AWS to on-prem queries)
resource "aws_route53_resolver_endpoint" "outbound" {
  name      = "${var.project_name}-outbound-resolver"
  direction = "OUTBOUND"

  security_group_ids = [aws_security_group.dns_resolver_sg.id]

  ip_address {
    subnet_id = aws_subnet.private_subnet.id
    ip        = "10.1.2.11"
  }

  ip_address {
    subnet_id = aws_subnet.public_subnet.id
    ip        = "10.1.1.11"
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-outbound-resolver"
  })
}
```

### Forward Resolution Rules

```hcl
# Forwarding rule to send tillynet.lan queries to my Samba4 DC
resource "aws_route53_resolver_rule" "onprem_forward" {
  domain_name          = "tillynet.lan"
  name                 = "${var.project_name}-onprem-forward"
  rule_type            = "FORWARD"
  resolver_endpoint_id = aws_route53_resolver_endpoint.outbound.id

  target_ip {
    ip   = "172.30.30.30" # my Samba4 DC IP
    port = 53
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-onprem-forward"
  })
}
```

This enables AWS instances to resolve my on-premises domain names.

### Private Hosted Zone

```hcl
# Private hosted zone for aws.tillynet.lan
resource "aws_route53_zone" "aws_private" {
  name = "aws.tillynet.lan"

  vpc {
    vpc_id = aws_vpc.hybrid_vpc.id
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-aws-private-zone"
  })
}
```

## Security Implementation

### Security Groups

I implemented least-privilege security groups for each component:

```hcl
# DNS Resolver Security Group
resource "aws_security_group" "dns_resolver_sg" {
  name_prefix = "${var.project_name}-dns-resolver-"
  description = "Security group for Route 53 Resolver endpoints"
  vpc_id      = aws_vpc.hybrid_vpc.id

  ingress {
    description = "DNS from on-premises networks"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = local.home_networks
  }

  ingress {
    description = "DNS TCP from on-premises networks"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = local.home_networks
  }

  egress {
    description = "DNS to on-premises"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = local.home_networks
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-dns-resolver-sg"
  })
}

# Private Instance Security Group
resource "aws_security_group" "private_sg" {
  name_prefix = "${var.project_name}-private-"
  description = "Security group for private instances"
  vpc_id      = aws_vpc.hybrid_vpc.id

  ingress {
    description = "SSH from home networks"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = local.home_networks
  }

  ingress {
    description = "HTTPS from home networks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = local.home_networks
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-private-sg"
  })
}
```

### Bastion Host Security

The bastion host implements a critical security pattern:

```hcl
# Bastion Host Security Group
resource "aws_security_group" "bastion_sg" {
  name_prefix = "${var.project_name}-bastion-"
  description = "Security group for bastion host"
  vpc_id      = aws_vpc.hybrid_vpc.id

  ingress {
    description = "SSH from internet (backup access)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["${var.home_public_ip}/32"]
  }

  # Note: SSH from on-premises networks is intentionally blocked
  # This forces proper access patterns for security

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-bastion-sg"
  })
}
```

This design enforces different access patterns:

- **Bastion host**: Internet → AWS entry point only
- **Private instances**: On-premises ↔ AWS communication
- **No lateral movement** from on-premises to bastion

## EC2 Instance Deployment

### IAM Roles and Instance Profiles

```hcl
# IAM role for EC2 instances
resource "aws_iam_role" "ec2_hybrid_role" {
  name = "${var.project_name}-ec2-hybrid-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# IAM policy for EC2 instances
resource "aws_iam_role_policy" "ec2_hybrid_policy" {
  name = "${var.project_name}-ec2-hybrid-policy"
  role = aws_iam_role.ec2_hybrid_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "route53:ListHostedZones",
          "route53:GetHostedZone",
          "route53:ChangeResourceRecordSets",
          "route53:GetChange"
        ]
        Resource = "*"
      }
    ]
  })
}
```

### Instance Configuration

```hcl
# Private Instance for hybrid workloads
resource "aws_instance" "hybrid_app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro"
  key_name               = var.key_pair_name
  subnet_id              = aws_subnet.private_subnet.id
  vpc_security_group_ids = [aws_security_group.private_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_hybrid_profile.name

  user_data = base64encode(templatefile("${path.module}/user-data/app-userdata.sh", {
    hostname        = "app01"
    project         = var.project_name
    environment     = "hybrid"
    samba_dc_ip     = "172.30.30.30"
    dns_resolver_ip = "10.1.2.10"
  }))

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-app01"
    Role = "Application"
  })
}
```

## DNS Integration Challenges and Solutions

### Initial Approach: DNS Delegation

My first approach attempted to use DNS delegation from Samba4 to AWS Route 53:

```bash
# Create AWS subdomain zone
sudo samba-tool dns zonecreate 172.30.30.30 aws.tillynet.lan -U Administrator

# Add NS record for delegation
sudo samba-tool dns add 172.30.30.30 tillynet.lan aws NS aws-resolver.tillynet.lan -U Administrator

# Add glue record
sudo samba-tool dns add 172.30.30.30 tillynet.lan aws-resolver A 10.1.2.10 -U Administrator
```

### Problems Encountered

1. **Resolver Connectivity Issues**
    
    ```bash
    # Testing both resolver IPs
    nslookup app01.aws.tillynet.lan 10.1.1.10  # Timeout
    nslookup app01.aws.tillynet.lan 10.1.2.10  # Success
    ```
    
    By design only the private subnet resolver (10.1.2.10) was reachable from my on-prem networks since traffic between my on-prem networks and aws-public-subnets was not permitted. 
    
2. **Samba4 Delegation Behavior**
    
    Samba4 doesn't follow NS delegation for subdomains like traditional DNS servers. Even with correct delegation setup, queries weren't being forwarded properly.
    
3. **Conflicting NS Records**
    
    Having both `samba.tillynet.lan` and `aws-resolver.tillynet.lan` as nameservers created resolution conflicts.
    

### Final Solution: Direct Zone Management

I resolved the issues by making Samba4 directly authoritative for the AWS subdomain:

```bash
# Remove delegation records
sudo samba-tool dns delete 172.30.30.30 tillynet.lan aws NS aws-resolver.tillynet.lan -U Administrator
sudo samba-tool dns delete 172.30.30.30 tillynet.lan aws-resolver A 10.1.2.10 -U Administrator

# Add records directly to the aws zone
sudo samba-tool dns add 172.30.30.30 aws.tillynet.lan app01 A 10.1.2.76 -U Administrator
sudo samba-tool dns add 172.30.30.30 aws.tillynet.lan bastion A 10.1.1.101 -U Administrator
```

This approach provides:

- **Immediate resolution** without delegation complexity
- **Central management** of all DNS records
- **Better performance** (no network hops to AWS)
- **Simplified troubleshooting**

## Connectivity Testing and Validation

### VPN Tunnel Verification

```bash
# Test connectivity using allowed ports (SSH)
ssh 10.1.2.76  # Success - shows VPN is working
```

### DNS Resolution Testing

```bash
# Test from on-premises
nslookup app01.aws.tillynet.lan 172.30.30.30
# Returns: 10.1.2.76

# Test SSH using DNS names
ssh -i keypair.pem ec2-user@app01.aws.tillynet.lan
# Success!
```

### Cross-Environment Access Patterns

**From On-Premises to AWS:**

- Private instances: Direct SSH via VPN tunnel
- Bastion host: SSH from internet only (security best practice)

**From AWS to On-Premises:**

- All on-premises services accessible via VPN
- DNS resolution works bi-directionally

## Security Best Practices Implemented

### Network Segmentation

- **VPC isolation** with no overlapping IP ranges
- **Security groups** implementing least-privilege access
- **Subnet separation** between public and private resources

### Access Control

- **Bastion host** restricted to internet access only
- **Private instances** accessible from on-premises networks
- **IAM roles** instead of embedded credentials

### Monitoring and Logging

- **VPC Flow Logs** for traffic analysis
- **CloudTrail** for API auditing
- **Security group logging** for access attempts

## Automation and Infrastructure as Code

The entire infrastructure is managed through Terraform, providing:

### Variable Configuration

```hcl
# terraform.tfvars
aws_region     = "us-west-1"
home_public_ip = "XXX.XXX.XXX.XXX"
project_name   = "tillynet-hybrid"
key_pair_name  = "tillynet-aws-keypair-general"
```

### Modular Design

- Separate files for different components (dns.tf, security-groups.tf, instances.tf)
- Reusable variables and locals
- Consistent tagging strategy

### Deployment Validation

```bash
terraform validate
terraform plan
terraform apply
```

## Lessons Learned

### DNS Delegation Complexity

**Challenge**: Samba4 doesn't handle DNS delegation like traditional DNS servers. **Solution**: Direct zone management is often simpler and more reliable for hybrid environments.

### Security Group Design

**Challenge**: Balancing security with functionality. **Solution**: Implement different access patterns for different resource types (bastion vs. private instances).

### Route 53 Resolver Placement

**Challenge**: Not all resolver endpoints may be reachable. **Solution**: Test connectivity to all endpoints and use only working ones.

## Performance and Cost Considerations

### Network Performance

- **VPN tunnel latency**: ~75-85ms (acceptable for hybrid operations)
- **DNS resolution**: Sub-second response times
- **Throughput**: Sufficient for management and application traffic

### Cost Optimization

- **t3.micro instances**: Free tier eligible
- **NAT Gateway**: ~$32/month (necessary for private subnet internet access)
- **VPN Connection**: ~$36/month (fixed cost)
- **Route 53 Resolver**: ~$0.125/hour per endpoint

## Future Enhancements

### Planned Improvements

1. **Certificate Management**: Extend on-premises PKI to AWS services
2. **Service Mesh**: Implement secure service-to-service communication
3. **Monitoring Integration**: Centralized logging and monitoring
4. **Automation**: Ansible playbooks for configuration management

### Scalability Considerations

- **Multi-AZ deployment** for high availability
- **Auto Scaling Groups** for dynamic capacity
- **Load balancers** for service distribution
- **Container orchestration** for microservices

## Conclusion

This hybrid infrastructure implementation demonstrates enterprise-grade practices for securely connecting on-premises and cloud environments. The combination of proper network segmentation, security controls, and DNS integration provides a solid foundation for hybrid cloud operations.

Key achievements:

- **Secure VPN connectivity** between environments
- **Seamless DNS resolution** across hybrid infrastructure
- **Defense-in-depth security** with multiple isolation layers
- **Infrastructure as Code** for reproducible deployments
- **Scalable architecture** ready for service expansion

The pragmatic approach of using direct DNS zone management over complex delegation proved that sometimes the simplest solution that works is better than a theoretically perfect solution that doesn't. This infrastructure now serves as the foundation for deploying hybrid applications and services across both environments.

## Technical Specifications

**Infrastructure Components:**

- AWS VPC with public/private subnets
- Site-to-site VPN with static routing
- Route 53 Resolver endpoints for DNS
- EC2 instances with IAM roles
- Security groups with least-privilege access

**Network Architecture:**

- On-premises: Multiple VLANs (172.16.x.x/24, 172.21.21.0/24, 172.30.30.0/24)
- AWS: 10.1.0.0/16 with /24 subnets
- VPN: IPsec with AES256 encryption

**DNS Architecture:**

- Samba4 AD DC: Authoritative for tillynet.lan and aws.tillynet.lan
- Pi-hole: Recursive resolver with ad-blocking
- Route 53: AWS service resolution and forwarding