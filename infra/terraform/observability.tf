locals {
  operational_metric_namespace = "${var.project_name}/Operational"
  alarm_actions                = [aws_sns_topic.operational_alerts.arn]
}

resource "aws_sns_topic" "operational_alerts" {
  name              = "${local.resource_name_prefix}-operational-alerts"
  kms_master_key_id = "alias/aws/sns"
}

data "aws_iam_policy_document" "operational_alerts" {
  statement {
    sid = "AllowAccountAdministration"
    actions = [
      "sns:AddPermission",
      "sns:DeleteTopic",
      "sns:GetTopicAttributes",
      "sns:ListSubscriptionsByTopic",
      "sns:Publish",
      "sns:RemovePermission",
      "sns:SetTopicAttributes",
      "sns:Subscribe",
    ]
    resources = [aws_sns_topic.operational_alerts.arn]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid     = "AllowCloudWatchAlarmPublish"
    actions = ["sns:Publish"]
    resources = [
      aws_sns_topic.operational_alerts.arn,
    ]

    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "AWS:SourceArn"
      values   = ["arn:aws:cloudwatch:*:${data.aws_caller_identity.current.account_id}:alarm:${local.resource_name_prefix}-*"]
    }
  }
}

resource "aws_sns_topic_policy" "operational_alerts" {
  arn    = aws_sns_topic.operational_alerts.arn
  policy = data.aws_iam_policy_document.operational_alerts.json
}

resource "aws_sns_topic_subscription" "operational_email" {
  count = var.alarm_notification_email == null ? 0 : 1

  topic_arn = aws_sns_topic.operational_alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_notification_email
}

resource "aws_cloudwatch_log_metric_filter" "collector_failure" {
  name           = "${local.resource_name_prefix}-collector-failure"
  log_group_name = aws_cloudwatch_log_group.collector.name
  pattern        = "{ $.event = \"collection_failed\" }"

  metric_transformation {
    name          = "CollectorFailures"
    namespace     = local.operational_metric_namespace
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "collector_completion" {
  name           = "${local.resource_name_prefix}-collector-completion"
  log_group_name = aws_cloudwatch_log_group.collector.name
  pattern        = "{ $.event = \"collection_completed\" && $.status != \"failed\" }"

  metric_transformation {
    name          = "CollectorCompletions"
    namespace     = local.operational_metric_namespace
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "cloudfront_5xx" {
  provider = aws.us_east_1

  alarm_name          = "${local.resource_name_prefix}-cloudfront-5xx"
  alarm_description   = "CloudFront is returning a sustained elevated percentage of 5xx responses."
  namespace           = "AWS/CloudFront"
  metric_name         = "5xxErrorRate"
  dimensions          = { DistributionId = aws_cloudfront_distribution.application.id, Region = "Global" }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "ec2_status" {
  alarm_name          = "${local.resource_name_prefix}-ec2-status"
  alarm_description   = "The EC2 host or its underlying AWS system is failing status checks."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  dimensions          = { InstanceId = aws_instance.runtime.id }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "ec2_root_disk" {
  alarm_name          = "${local.resource_name_prefix}-ec2-root-disk"
  alarm_description   = "The EC2 root filesystem has sustained usage above 85 percent."
  namespace           = "CWAgent"
  metric_name         = "disk_used_percent"
  dimensions          = { InstanceId = aws_instance.runtime.id }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "collector_failure" {
  alarm_name          = "${local.resource_name_prefix}-collector-failure"
  alarm_description   = "A collector run failed before it could complete successfully."
  namespace           = local.operational_metric_namespace
  metric_name         = "CollectorFailures"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions

  depends_on = [aws_cloudwatch_log_metric_filter.collector_failure]
}

resource "aws_cloudwatch_metric_alarm" "collector_stale" {
  alarm_name          = "${local.resource_name_prefix}-collector-stale"
  alarm_description   = "No non-failed collector completion was recorded in the last 12 hours."
  namespace           = local.operational_metric_namespace
  metric_name         = "CollectorCompletions"
  statistic           = "Sum"
  period              = 43200
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions

  depends_on = [aws_cloudwatch_log_metric_filter.collector_completion]
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "${local.resource_name_prefix}-rds-free-storage"
  alarm_description   = "RDS has less than 5 GiB of free storage for two consecutive periods."
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgresql.identifier }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 5 * 1024 * 1024 * 1024
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.resource_name_prefix}-rds-cpu"
  alarm_description   = "RDS CPU has remained above 90 percent for 15 minutes."
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgresql.identifier }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
}

resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${local.resource_name_prefix}-rds-connections"
  alarm_description   = "RDS has sustained more database connections than the reviewed MVP threshold."
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgresql.identifier }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  threshold           = var.rds_connection_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = local.alarm_actions
  ok_actions          = local.alarm_actions
}
