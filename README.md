# GitHub PR Review Bot

This bot provides automated code reviews for GitHub pull requests using AWS Bedrock's Claude model.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
# AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=your_region

# GitHub token (if needed)
export GITHUB_TOKEN=your_token
```

## Usage Example

```python
from src.llm_reviewer import PRReviewer

# Initialize reviewer
reviewer = PRReviewer()

# Get PR diff content somehow
diff_content = "..."

# Get review
review_result = reviewer.review_pr(diff_content)
print(review_result)
```

The review result will be in the following format:
```json
{
  "entire_review": "Overall review comments",
  "suggestions": [
    {
      "file_path": "path/to/file",
      "line_numbers": {
        "start": 10,
        "end": 15
      },
      "suggest_content": "Suggestion for improvement"
    }
  ]
}
```
