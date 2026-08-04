data "aws_caller_identity" "current" {}

data "aws_ssm_parameter" "al2023_x86_64_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/${var.project_name}/${var.environment}/api"
  retention_in_days = var.runtime_log_retention_days
}

resource "aws_cloudwatch_log_group" "collector" {
  name              = "/${var.project_name}/${var.environment}/collector"
  retention_in_days = var.runtime_log_retention_days
}

resource "aws_iam_role" "runtime" {
  name = "${local.resource_name_prefix}-runtime"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "runtime_ssm" {
  role       = aws_iam_role.runtime.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "runtime_application" {
  name = "${var.project_name}-runtime-application"
  role = aws_iam_role.runtime.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "GetEcrAuthorizationToken"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "PullBackendImage"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
        ]
        Resource = aws_ecr_repository.backend.arn
      },
      {
        Sid      = "ReadDatabaseCredentials"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_db_instance.postgresql.master_user_secret[0].secret_arn
      },
      {
        Sid      = "ReadOpenAiKey"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.openai_api_key_parameter_name}"
      },
      {
        Sid    = "PublishContainerLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents",
        ]
        Resource = [
          "${aws_cloudwatch_log_group.api.arn}:*",
          "${aws_cloudwatch_log_group.collector.arn}:*",
        ]
      },
      {
        Sid      = "PublishHostMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "CWAgent"
          }
        }
      },
    ]
  })
}

resource "aws_iam_instance_profile" "runtime" {
  name = "${local.resource_name_prefix}-runtime"
  role = aws_iam_role.runtime.name
}

locals {
  backend_image_uri = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
}

resource "aws_instance" "runtime" {
  ami                    = data.aws_ssm_parameter.al2023_x86_64_ami.value
  instance_type          = var.runtime_instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.runtime.name

  associate_public_ip_address = false
  source_dest_check           = true
  monitoring                  = false

  user_data = templatefile("${path.module}/templates/ec2-user-data.sh.tftpl", {
    aws_region               = var.aws_region
    backend_image_uri        = local.backend_image_uri
    database_name            = var.database_name
    database_secret_arn      = aws_db_instance.postgresql.master_user_secret[0].secret_arn
    ecr_registry             = split("/", aws_ecr_repository.backend.repository_url)[0]
    openai_parameter_name    = var.openai_api_key_parameter_name
    api_log_group_name       = aws_cloudwatch_log_group.api.name
    collector_log_group_name = aws_cloudwatch_log_group.collector.name
  })
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "disabled"
  }

  root_block_device {
    encrypted             = true
    delete_on_termination = true
    volume_type           = "gp3"
    volume_size           = var.runtime_root_volume_gib
  }

  credit_specification {
    cpu_credits = "standard"
  }

  depends_on = [
    aws_iam_role_policy.runtime_application,
    aws_iam_role_policy_attachment.runtime_ssm,
  ]

  tags = {
    Name = "${local.resource_name_prefix}-runtime"
  }
}

resource "aws_eip" "runtime" {
  domain = "vpc"

  tags = {
    Name = "${local.resource_name_prefix}-runtime"
  }
}

resource "aws_eip_association" "runtime" {
  allocation_id = aws_eip.runtime.id
  instance_id   = aws_instance.runtime.id
}
