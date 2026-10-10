resource "aws_iam_role" "checkout" {
  name = "checkout-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "checkout" {
  name = "checkout-admin"
  role = aws_iam_role.checkout.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:*", "iam:*"]
        Resource = "*"
      }
    ]
  })
}
