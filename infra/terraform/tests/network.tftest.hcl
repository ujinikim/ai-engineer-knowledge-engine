mock_provider "aws" {
  override_data {
    target = data.aws_availability_zones.available
    values = {
      names = ["us-east-2c", "us-east-2a", "us-east-2b"]
    }
  }

  override_data {
    target = data.aws_ec2_managed_prefix_list.cloudfront_origin_facing
    values = {
      id   = "pl-cloudfront-origin"
      name = "com.amazonaws.global.cloudfront.origin-facing"
    }
  }

  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "123456789012"
    }
  }
}

mock_provider "aws" {
  alias = "us_east_1"
}

variables {
  backend_image_tag = "0123456789abcdef0123456789abcdef01234567"
}

run "default_network_is_segmented" {
  command = plan

  assert {
    condition     = aws_vpc.application.cidr_block == "10.40.0.0/16"
    error_message = "The default VPC CIDR changed unexpectedly."
  }

  assert {
    condition     = aws_subnet.public.cidr_block == "10.40.0.0/24"
    error_message = "The public runtime subnet must be the first derived /24."
  }

  assert {
    condition = [
      for subnet in aws_subnet.database : subnet.cidr_block
    ] == ["10.40.10.0/24", "10.40.11.0/24"]
    error_message = "The database subnets must be distinct private /24 ranges."
  }

  assert {
    condition = [
      for subnet in aws_subnet.database : subnet.availability_zone
    ] == ["us-east-2a", "us-east-2b"]
    error_message = "Database subnets must use two deterministically selected AZs."
  }

  assert {
    condition     = aws_subnet.public.map_public_ip_on_launch == false
    error_message = "The future EC2 instance must receive its public address explicitly."
  }

  assert {
    condition     = aws_vpc_security_group_ingress_rule.ec2_from_cloudfront.prefix_list_id == "pl-cloudfront-origin"
    error_message = "API ingress must use the AWS-managed CloudFront origin prefix list."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.ec2_from_cloudfront.from_port == 8000 &&
      aws_vpc_security_group_ingress_rule.ec2_from_cloudfront.to_port == 8000
    )
    error_message = "CloudFront should reach only the configured API origin port."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.rds_from_ec2.from_port == 5432 &&
      aws_vpc_security_group_ingress_rule.rds_from_ec2.to_port == 5432
    )
    error_message = "RDS ingress should expose only PostgreSQL."
  }

  assert {
    condition     = aws_route.public_internet.destination_cidr_block == "0.0.0.0/0"
    error_message = "The public subnet requires the explicit Internet Gateway route."
  }
}

run "invalid_vpc_cidr_is_rejected" {
  command = plan

  variables {
    vpc_cidr = "not-a-cidr"
  }

  expect_failures = [
    var.vpc_cidr,
  ]
}
