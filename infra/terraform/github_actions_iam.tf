data "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github"
}

data "aws_iam_policy_document" "github_actions_ecr_push" {
  statement {
    sid = "GetEcrAuthorizationToken"

    actions = [
      "ecr:GetAuthorizationToken",
    ]

    resources = ["*"]
  }

  statement {
    sid = "PushAndVerifyBackendImage"

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeImageScanFindings",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]

    resources = [aws_ecr_repository.backend.arn]
  }
}

resource "aws_iam_role_policy" "github_actions_ecr_push" {
  name   = "${var.project_name}-ecr-push"
  role   = data.aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_ecr_push.json
}

data "aws_iam_policy_document" "github_actions_frontend_deploy" {
  statement {
    sid = "InspectFrontendBucket"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [aws_s3_bucket.frontend.arn]
  }

  statement {
    sid = "PublishFrontendObjects"
    actions = [
      "s3:DeleteObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]
  }

  statement {
    sid = "InvalidateFrontendCache"
    actions = [
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
    ]
    resources = [aws_cloudfront_distribution.application.arn]
  }
}

resource "aws_iam_role_policy" "github_actions_frontend_deploy" {
  name   = "${var.project_name}-frontend-deploy"
  role   = data.aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_frontend_deploy.json
}
