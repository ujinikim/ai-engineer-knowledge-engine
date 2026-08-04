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

run "frontend_is_private_and_api_is_uncached" {
  command = plan

  assert {
    condition = (
      aws_s3_bucket_public_access_block.frontend.block_public_acls == true &&
      aws_s3_bucket_public_access_block.frontend.block_public_policy == true &&
      aws_s3_bucket_public_access_block.frontend.ignore_public_acls == true &&
      aws_s3_bucket_public_access_block.frontend.restrict_public_buckets == true
    )
    error_message = "The frontend bucket must block every form of public S3 access."
  }

  assert {
    condition = (
      aws_cloudfront_origin_access_control.frontend.signing_behavior == "always" &&
      aws_cloudfront_origin_access_control.frontend.signing_protocol == "sigv4"
    )
    error_message = "CloudFront must always sign private S3 origin requests with SigV4."
  }

  assert {
    condition = (
      aws_cloudfront_distribution.application.default_cache_behavior[0].target_origin_id == "private-s3-frontend" &&
      aws_cloudfront_distribution.application.ordered_cache_behavior[0].path_pattern == "/api/*" &&
      aws_cloudfront_distribution.application.ordered_cache_behavior[0].target_origin_id == "ec2-fastapi" &&
      aws_cloudfront_distribution.application.ordered_cache_behavior[0].cache_policy_id == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    )
    error_message = "Static requests must use S3 while /api/* uses the uncached FastAPI origin."
  }

  assert {
    condition = (
      aws_cloudfront_distribution.application.default_cache_behavior[0].viewer_protocol_policy == "redirect-to-https" &&
      aws_cloudfront_distribution.application.ordered_cache_behavior[0].viewer_protocol_policy == "redirect-to-https"
    )
    error_message = "Every viewer-facing behavior must redirect HTTP to HTTPS."
  }

  assert {
    condition     = aws_s3_bucket_versioning.frontend.versioning_configuration[0].status == "Enabled"
    error_message = "Frontend deployments must be versioned for recoverability."
  }
}
