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
    target = data.aws_ssm_parameter.al2023_x86_64_ami
    values = {
      value = "ami-amazon-linux-2023-x86"
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

run "runtime_is_hardened_and_uses_immutable_image" {
  command = plan

  assert {
    condition = (
      aws_instance.runtime.ami == "ami-amazon-linux-2023-x86" &&
      aws_instance.runtime.instance_type == "t3.small" &&
      aws_instance.runtime.associate_public_ip_address == false
    )
    error_message = "The runtime must use the reviewed x86 Amazon Linux instance configuration."
  }

  assert {
    condition = (
      aws_instance.runtime.metadata_options[0].http_tokens == "required" &&
      aws_instance.runtime.metadata_options[0].http_put_response_hop_limit == 1 &&
      aws_instance.runtime.metadata_options[0].instance_metadata_tags == "disabled"
    )
    error_message = "The container host must require IMDSv2 and hide instance tags."
  }

  assert {
    condition = (
      aws_instance.runtime.root_block_device[0].encrypted == true &&
      aws_instance.runtime.root_block_device[0].volume_type == "gp3" &&
      aws_instance.runtime.root_block_device[0].volume_size == 20
    )
    error_message = "The runtime root volume must use the encrypted bounded gp3 configuration."
  }

  assert {
    condition = (
      strcontains(templatefile("${path.module}/templates/ec2-user-data.sh.tftpl", {
        aws_region               = "us-east-2"
        backend_image_uri        = "registry.example/backend:0123456789abcdef0123456789abcdef01234567"
        database_host            = "database.example"
        database_name            = "knowledge_engine"
        database_port            = 5432
        database_secret_arn      = "arn:aws:secretsmanager:us-east-2:123456789012:secret:database"
        ecr_registry             = "registry.example"
        openai_parameter_name    = "/ai-engineer-knowledge-engine/production/openai-api-key"
        api_log_group_name       = "/project/production/api"
        collector_log_group_name = "/project/production/collector"
      }), "knowledge-engine-api.service") &&
      strcontains(templatefile("${path.module}/templates/ec2-user-data.sh.tftpl", {
        aws_region               = "us-east-2"
        backend_image_uri        = "registry.example/backend:0123456789abcdef0123456789abcdef01234567"
        database_host            = "database.example"
        database_name            = "knowledge_engine"
        database_port            = 5432
        database_secret_arn      = "arn:aws:secretsmanager:us-east-2:123456789012:secret:database"
        ecr_registry             = "registry.example"
        openai_parameter_name    = "/ai-engineer-knowledge-engine/production/openai-api-key"
        api_log_group_name       = "/project/production/api"
        collector_log_group_name = "/project/production/collector"
      }), "knowledge-engine-collector.timer") &&
      strcontains(templatefile("${path.module}/templates/ec2-user-data.sh.tftpl", {
        aws_region               = "us-east-2"
        backend_image_uri        = "registry.example/backend:0123456789abcdef0123456789abcdef01234567"
        database_host            = "database.example"
        database_name            = "knowledge_engine"
        database_port            = 5432
        database_secret_arn      = "arn:aws:secretsmanager:us-east-2:123456789012:secret:database"
        ecr_registry             = "registry.example"
        openai_parameter_name    = "/ai-engineer-knowledge-engine/production/openai-api-key"
        api_log_group_name       = "/project/production/api"
        collector_log_group_name = "/project/production/collector"
      }), "/run/knowledge-engine-secrets") &&
      strcontains(templatefile("${path.module}/templates/ec2-user-data.sh.tftpl", {
        aws_region               = "us-east-2"
        backend_image_uri        = "registry.example/backend:0123456789abcdef0123456789abcdef01234567"
        database_host            = "database.example"
        database_name            = "knowledge_engine"
        database_port            = 5432
        database_secret_arn      = "arn:aws:secretsmanager:us-east-2:123456789012:secret:database"
        ecr_registry             = "registry.example"
        openai_parameter_name    = "/ai-engineer-knowledge-engine/production/openai-api-key"
        api_log_group_name       = "/project/production/api"
        collector_log_group_name = "/project/production/collector"
      }), "disk_used_percent")
    )
    error_message = "Bootstrap must install API, collector, in-memory secrets, host metrics, and the selected immutable image."
  }

  assert {
    condition = !strcontains(templatefile("${path.module}/templates/ec2-user-data.sh.tftpl", {
      aws_region               = "us-east-2"
      backend_image_uri        = "registry.example/backend:0123456789abcdef0123456789abcdef01234567"
      database_host            = "database.example"
      database_name            = "knowledge_engine"
      database_port            = 5432
      database_secret_arn      = "arn:aws:secretsmanager:us-east-2:123456789012:secret:database"
      ecr_registry             = "registry.example"
      openai_parameter_name    = "/ai-engineer-knowledge-engine/production/openai-api-key"
      api_log_group_name       = "/project/production/api"
      collector_log_group_name = "/project/production/collector"
    }), "enable --now knowledge-engine-collector.timer")
    error_message = "The first boot must not schedule ingestion before production data validation."
  }

  assert {
    condition = (
      aws_eip.runtime.domain == "vpc" &&
      aws_instance.runtime.credit_specification[0].cpu_credits == "standard" &&
      aws_instance.runtime.monitoring == false
    )
    error_message = "The MVP must use a stable VPC address without surprise burst or detailed-monitoring costs."
  }

  assert {
    condition = (
      aws_cloudwatch_log_group.api.retention_in_days == 14 &&
      aws_cloudwatch_log_group.collector.retention_in_days == 14
    )
    error_message = "Runtime log groups must enforce finite retention."
  }
}

run "non_commit_image_tag_is_rejected" {
  command = plan

  variables {
    backend_image_tag = "latest"
  }

  expect_failures = [
    var.backend_image_tag,
  ]
}
