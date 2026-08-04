resource "aws_db_subnet_group" "application" {
  name        = "${local.resource_name_prefix}-database"
  description = "Private database subnets for the knowledge engine"
  subnet_ids  = aws_subnet.database[*].id

  tags = {
    Name = "${local.resource_name_prefix}-database"
  }
}

resource "aws_db_parameter_group" "postgresql" {
  name_prefix = "${local.resource_name_prefix}-postgresql16-"
  description = "PostgreSQL 16 settings for the knowledge engine"
  family      = "postgres16"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.resource_name_prefix}-postgresql16"
  }
}

resource "aws_db_instance" "postgresql" {
  identifier = "${local.resource_name_prefix}-postgresql"

  engine                   = "postgres"
  engine_version           = var.database_engine_version
  engine_lifecycle_support = "open-source-rds-extended-support-disabled"
  instance_class           = var.database_instance_class
  db_name                  = var.database_name
  username                 = var.database_master_username
  port                     = var.postgresql_port

  manage_master_user_password = true

  allocated_storage     = var.database_allocated_storage_gib
  max_allocated_storage = var.database_max_storage_gib
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.application.name
  parameter_group_name   = aws_db_parameter_group.postgresql.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  availability_zone      = local.availability_zones[0]
  network_type           = "IPV4"
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = var.database_backup_retention_days
  backup_window           = "05:00-06:00"
  maintenance_window      = "sun:07:00-sun:08:00"
  copy_tags_to_snapshot   = true

  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = false

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.resource_name_prefix}-postgresql-final"
  delete_automated_backups  = true

  performance_insights_enabled = false
  monitoring_interval          = 0

  tags = {
    Name = "${local.resource_name_prefix}-postgresql"
  }
}

check "database_storage_autoscaling_limit" {
  assert {
    condition     = var.database_max_storage_gib >= var.database_allocated_storage_gib
    error_message = "database_max_storage_gib must be greater than or equal to database_allocated_storage_gib."
  }
}
