mock_provider "aws" {
  override_data {
    target = data.aws_availability_zones.available
    values = { names = ["us-east-2a", "us-east-2b"] }
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
    values = { value = "ami-amazon-linux-2023-x86" }
  }

  override_data {
    target = data.aws_caller_identity.current
    values = { account_id = "123456789012" }
  }
}

mock_provider "aws" {
  alias = "us_east_1"
}

variables {
  backend_image_tag = "0123456789abcdef0123456789abcdef01234567"
}

run "operational_alarms_cover_public_runtime_collector_and_database" {
  command = plan

  assert {
    condition = (
      aws_sns_topic.operational_alerts.kms_master_key_id == "alias/aws/sns" &&
      length(aws_sns_topic_subscription.operational_email) == 0
    )
    error_message = "Operational notifications must be encrypted and email must remain optional."
  }

  assert {
    condition = (
      aws_cloudwatch_metric_alarm.cloudfront_5xx.metric_name == "5xxErrorRate" &&
      aws_cloudwatch_metric_alarm.cloudfront_5xx.dimensions.Region == "Global" &&
      aws_cloudwatch_metric_alarm.cloudfront_5xx.threshold == 5
    )
    error_message = "CloudFront must alarm on a sustained elevated global 5xx rate."
  }

  assert {
    condition = (
      aws_cloudwatch_metric_alarm.ec2_status.metric_name == "StatusCheckFailed" &&
      aws_cloudwatch_metric_alarm.ec2_root_disk.metric_name == "disk_used_percent" &&
      aws_cloudwatch_metric_alarm.ec2_root_disk.threshold == 85
    )
    error_message = "EC2 monitoring must cover AWS status checks and root-disk pressure."
  }

  assert {
    condition = (
      aws_cloudwatch_log_metric_filter.collector_failure.pattern == "{ $.event = \"collection_failed\" }" &&
      aws_cloudwatch_metric_alarm.collector_failure.comparison_operator == "GreaterThanOrEqualToThreshold" &&
      aws_cloudwatch_metric_alarm.collector_stale.period == 43200 &&
      aws_cloudwatch_metric_alarm.collector_stale.treat_missing_data == "breaching"
    )
    error_message = "Collector monitoring must detect explicit failure and a missing 12-hour completion."
  }

  assert {
    condition = (
      aws_cloudwatch_metric_alarm.rds_free_storage.threshold == 5368709120 &&
      aws_cloudwatch_metric_alarm.rds_cpu.threshold == 90 &&
      aws_cloudwatch_metric_alarm.rds_connections.threshold == 60
    )
    error_message = "RDS alarms must cover low storage, sustained CPU, and connection pressure."
  }

  assert {
    condition = alltrue([
      for actions in [
        aws_cloudwatch_metric_alarm.cloudfront_5xx.alarm_actions,
        aws_cloudwatch_metric_alarm.ec2_status.alarm_actions,
        aws_cloudwatch_metric_alarm.ec2_root_disk.alarm_actions,
        aws_cloudwatch_metric_alarm.collector_failure.alarm_actions,
        aws_cloudwatch_metric_alarm.collector_stale.alarm_actions,
        aws_cloudwatch_metric_alarm.rds_free_storage.alarm_actions,
        aws_cloudwatch_metric_alarm.rds_cpu.alarm_actions,
        aws_cloudwatch_metric_alarm.rds_connections.alarm_actions,
      ] : length(actions) == 1
    ])
    error_message = "Every operational alarm must publish to the shared alert topic."
  }
}

run "invalid_alarm_email_is_rejected" {
  command = plan

  variables {
    alarm_notification_email = "not-an-email"
  }

  expect_failures = [var.alarm_notification_email]
}
