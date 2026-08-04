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

variables {
  backend_image_tag = "0123456789abcdef0123456789abcdef01234567"
}

run "database_is_private_encrypted_and_recoverable" {
  command = plan

  assert {
    condition = (
      aws_db_subnet_group.application.name == "ai-engineer-knowledge-engine-production-database" &&
      length(aws_subnet.database) == 2
    )
    error_message = "The DB subnet group must contain both private database subnets."
  }

  assert {
    condition = (
      aws_db_instance.postgresql.engine == "postgres" &&
      aws_db_instance.postgresql.engine_version == "16.14" &&
      aws_db_instance.postgresql.instance_class == "db.t4g.micro"
    )
    error_message = "The database must use the reviewed low-cost PostgreSQL 16 configuration."
  }

  assert {
    condition = (
      aws_db_instance.postgresql.publicly_accessible == false &&
      aws_db_instance.postgresql.multi_az == false &&
      length(aws_db_instance.postgresql.vpc_security_group_ids) == 1
    )
    error_message = "The initial database must be single-AZ, private, and use only the RDS security group."
  }

  assert {
    condition = (
      aws_db_instance.postgresql.storage_type == "gp3" &&
      aws_db_instance.postgresql.allocated_storage == 20 &&
      aws_db_instance.postgresql.max_allocated_storage == 50 &&
      aws_db_instance.postgresql.storage_encrypted == true
    )
    error_message = "Database storage must use the encrypted, bounded gp3 configuration."
  }

  assert {
    condition = (
      aws_db_instance.postgresql.manage_master_user_password == true &&
      aws_db_instance.postgresql.password == null
    )
    error_message = "RDS must manage the password without a password value in Terraform."
  }

  assert {
    condition = (
      aws_db_instance.postgresql.backup_retention_period == 7 &&
      aws_db_instance.postgresql.deletion_protection == true &&
      aws_db_instance.postgresql.skip_final_snapshot == false
    )
    error_message = "Backups, deletion protection, and a final snapshot must remain enabled."
  }

  assert {
    condition = anytrue([
      for parameter in aws_db_parameter_group.postgresql.parameter :
      parameter.name == "rds.force_ssl" && parameter.value == "1"
    ])
    error_message = "The PostgreSQL parameter group must require TLS connections."
  }
}

run "storage_limit_below_initial_size_is_rejected" {
  command = plan

  variables {
    database_allocated_storage_gib = 50
    database_max_storage_gib       = 20
  }

  expect_failures = [
    check.database_storage_autoscaling_limit,
  ]
}
