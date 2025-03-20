import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from github import Github
import requests
from langchain.prompts import ChatPromptTemplate, PromptTemplate
from langchain_aws import ChatBedrockConverse
from langchain.output_parsers import PydanticOutputParser

class LineNumbers(BaseModel):
    start: int = Field(description="시작 라인 번호")
    end: int = Field(description="끝 라인 번호")

class Suggestion(BaseModel):
    line_numbers: LineNumbers = Field(description="변경사항의 시작과 끝 라인 번호")
    content: str = Field(description="구체적인 개선 제안 내용")

class FileReviewResponse(BaseModel):
    review: str = Field(description="파일 변경사항에 대한 리뷰 내용")
    suggestions: Optional[List[Suggestion]] = Field(description="개선 제안 목록", default=[])

class PRSummaryResponse(BaseModel):
    summary: str = Field(description="전체 PR에 대한 종합적인 리뷰 요약")

class PRReviewer:
    def __init__(self, 
                 github_token: str = None, 
                 model_id: str = "anthropic.claude-v2",
                 github_base_url: str = None):
        """
        Initialize the PR reviewer.
        
        Args:
            github_token (str, optional): GitHub 토큰. 환경 변수에서도 가져올 수 있습니다.
            model_id (str, optional): 사용할 Bedrock 모델 ID. Defaults to "anthropic.claude-v2".
            github_base_url (str, optional): GitHub Enterprise URL (예: "https://github.mycompany.com/api/v3")
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            raise ValueError("GitHub token is required. Please provide it or set GITHUB_TOKEN environment variable.")
        
        self.github_base_url = github_base_url or os.getenv("GITHUB_BASE_URL")
        if self.github_base_url:
            self.github = Github(base_url=self.github_base_url, login_or_token=self.github_token)
        else:
            self.github = Github(self.github_token)
        self.llm = ChatBedrockConverse(
            model_id=model_id,
            model_kwargs={"temperature": 0.1, "max_tokens": 4096}
        )
        
        self.file_review_prompt = PromptTemplate(
            template="""
당신은 풍부한 경험을 가진 전문 코드 리뷰어입니다. 주어진 파일의 변경사항에 대해 상세하고 건설적인 피드백을 제공합니다.

파일 경로: {file_path}

다음 가이드라인을 따르세요:
1. 변경사항에 대한 전반적인 리뷰를 제공하세요
   - 코드 품질, 가독성, 잠재적 버그, 모범 사례 관점에서 분석
   - 변경사항의 목적과 영향을 평가
   - 코드의 전반적인 구조와 설계에 대한 의견 제시

2. 필요한 경우 구체적인 개선 제안을 제공하세요 (선택사항)
   - 정확한 라인 번호 지정 (hunk 헤더 @@ -X,Y +P,Q @@ 참고)
   - 실행 가능하고 구체적인 개선 방안 제시
   - 간결하면서도 명확한 설명 제공

변경사항:
{diff}

한국어로 응답해주세요.
""",
            input_variables=["file_path", "diff"]
        ).with_structured_output(FileReviewResponse)

        self.summary_prompt = PromptTemplate(
            template="""
당신은 풍부한 경험을 가진 전문 코드 리뷰어입니다. 각 파일별 리뷰 내용을 바탕으로 전체 PR에 대한 종합적인 요약을 제공해주세요.

파일별 리뷰 내용:
{file_reviews}

다음을 고려하여 전체 PR에 대한 종합적인 요약을 작성해주세요:
1. 주요 변경사항과 그 영향
2. 공통된 패턴이나 이슈
3. PR의 전반적인 품질과 준비 상태
4. 주의가 필요한 부분이나 잠재적 위험

한국어로 응답해주세요.
""",
            input_variables=["file_reviews"]
        ).with_structured_output(PRSummaryResponse)
        
        self.review_chain = prompt | self.llm

    def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        """
        GitHub API를 통해 PR의 raw diff 내용을 가져옵니다.
        
        Args:
            repo_name (str): GitHub 레포지토리 이름 (예: 'owner/repo')
            pr_number (int): PR 번호
            
        Returns:
            str: PR의 raw diff 내용
        """
        try:
            # GitHub Enterprise인 경우 base_url을 사용, 아니면 기본 GitHub API URL 사용
            base_url = self.github_base_url or "https://api.github.com"
            base_url = base_url.rstrip("/api/v3")  # Enterprise URL에서 /api/v3 제거
            
            # diff 형식으로 PR 내용을 가져오기 위한 URL 구성
            url = f"{base_url}/repos/{repo_name}/pulls/{pr_number}.diff"
            
            # GitHub 토큰을 헤더에 포함하여 요청
            headers = {"Authorization": f"token {self.github_token}"}
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"Failed to fetch PR diff: {response.status_code} - {response.text}")
                
            return response.text
        except Exception as e:
            raise Exception(f"Failed to fetch PR diff: {str(e)}")

    def review_github_pr(self, repo_name: str, pr_number: int) -> ReviewResponse:
        """
        GitHub PR을 검토하고 구조화된 피드백을 반환합니다.
        
        Args:
            repo_name (str): GitHub 레포지토리 이름 (예: 'owner/repo')
            pr_number (int): PR 번호
            
        Returns:
            ReviewResponse: 리뷰 결과
        """
        try:
            diff_content = self.get_pr_diff(repo_name, pr_number)
            return self.review_chain.invoke({"diff": diff_content})
        except Exception as e:
            return ReviewResponse(
                entire_review=f"Error during review: {str(e)}",
                suggestions=[]
            )
