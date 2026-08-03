data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ec2_managed_prefix_list" "cloudfront_origin_facing" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

locals {
  availability_zones = slice(sort(data.aws_availability_zones.available.names), 0, 2)

  public_subnet_cidr = cidrsubnet(var.vpc_cidr, 8, 0)
  database_subnet_cidrs = [
    cidrsubnet(var.vpc_cidr, 8, 10),
    cidrsubnet(var.vpc_cidr, 8, 11),
  ]

  resource_name_prefix = "${var.project_name}-${var.environment}"
}

resource "aws_vpc" "application" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${local.resource_name_prefix}-vpc"
  }
}

resource "aws_internet_gateway" "application" {
  vpc_id = aws_vpc.application.id

  tags = {
    Name = "${local.resource_name_prefix}-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.application.id
  availability_zone       = local.availability_zones[0]
  cidr_block              = local.public_subnet_cidr
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.resource_name_prefix}-public-${local.availability_zones[0]}"
    Tier = "public"
  }
}

resource "aws_subnet" "database" {
  count = 2

  vpc_id                  = aws_vpc.application.id
  availability_zone       = local.availability_zones[count.index]
  cidr_block              = local.database_subnet_cidrs[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name = "${local.resource_name_prefix}-database-${local.availability_zones[count.index]}"
    Tier = "database"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.application.id

  tags = {
    Name = "${local.resource_name_prefix}-public"
  }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.application.id
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "database" {
  vpc_id = aws_vpc.application.id

  tags = {
    Name = "${local.resource_name_prefix}-database"
  }
}

resource "aws_route_table_association" "database" {
  count = 2

  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.database.id
}

resource "aws_security_group" "ec2" {
  name_prefix            = "${local.resource_name_prefix}-ec2-"
  description            = "Runtime access for the API and scheduled collector"
  vpc_id                 = aws_vpc.application.id
  revoke_rules_on_delete = true

  tags = {
    Name = "${local.resource_name_prefix}-ec2"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "rds" {
  name_prefix            = "${local.resource_name_prefix}-rds-"
  description            = "Private PostgreSQL access from the application runtime"
  vpc_id                 = aws_vpc.application.id
  revoke_rules_on_delete = true

  tags = {
    Name = "${local.resource_name_prefix}-rds"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "ec2_from_cloudfront" {
  security_group_id = aws_security_group.ec2.id
  description       = "FastAPI origin traffic from CloudFront origin-facing servers"
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront_origin_facing.id
  ip_protocol       = "tcp"
  from_port         = var.api_origin_port
  to_port           = var.api_origin_port

  tags = {
    Name = "${local.resource_name_prefix}-cloudfront-to-api"
  }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_ec2" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from the application runtime only"
  referenced_security_group_id = aws_security_group.ec2.id
  ip_protocol                  = "tcp"
  from_port                    = var.postgresql_port
  to_port                      = var.postgresql_port

  tags = {
    Name = "${local.resource_name_prefix}-ec2-to-rds"
  }
}

resource "aws_vpc_security_group_egress_rule" "ec2_https" {
  security_group_id = aws_security_group.ec2.id
  description       = "HTTPS to ECR, AWS APIs, OpenAI, and configured sources"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443

  tags = {
    Name = "${local.resource_name_prefix}-ec2-https"
  }
}

resource "aws_vpc_security_group_egress_rule" "ec2_dns_udp" {
  security_group_id = aws_security_group.ec2.id
  description       = "DNS over UDP inside the VPC"
  cidr_ipv4         = aws_vpc.application.cidr_block
  ip_protocol       = "udp"
  from_port         = 53
  to_port           = 53

  tags = {
    Name = "${local.resource_name_prefix}-ec2-dns-udp"
  }
}

resource "aws_vpc_security_group_egress_rule" "ec2_dns_tcp" {
  security_group_id = aws_security_group.ec2.id
  description       = "DNS over TCP inside the VPC"
  cidr_ipv4         = aws_vpc.application.cidr_block
  ip_protocol       = "tcp"
  from_port         = 53
  to_port           = 53

  tags = {
    Name = "${local.resource_name_prefix}-ec2-dns-tcp"
  }
}

resource "aws_vpc_security_group_egress_rule" "ec2_to_rds" {
  security_group_id            = aws_security_group.ec2.id
  description                  = "PostgreSQL to the private RDS security group"
  referenced_security_group_id = aws_security_group.rds.id
  ip_protocol                  = "tcp"
  from_port                    = var.postgresql_port
  to_port                      = var.postgresql_port

  tags = {
    Name = "${local.resource_name_prefix}-ec2-postgresql"
  }
}

check "two_availability_zones_available" {
  assert {
    condition     = length(data.aws_availability_zones.available.names) >= 2
    error_message = "The selected AWS region must expose at least two Availability Zones."
  }
}
