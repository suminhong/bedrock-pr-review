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
    file_path: str = Field(description="파일의 정확한 경로")
    line_numbers: LineNumbers = Field(description="변경사항의 시작과 끝 라인 번호")
    suggest_content: str = Field(description="구체적인 개선 제안 내용")

class ReviewResponse(BaseModel):
    entire_review: str = Field(description="코드 변경사항에 대한 전반적인 리뷰")
    suggestions: List[Suggestion] = Field(description="구체적인 개선 제안 목록")

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
        
        prompt = PromptTemplate(
            template="""
당신은 풍부한 경험을 가진 전문 코드 리뷰어입니다. GitHub 풀 리퀘스트에 대해 상세하고 건설적인 피드백을 제공합니다.
주어진 코드 변경사항을 검토하고 다음 두 가지 주요 구성요소를 포함하는 응답을 반환하세요:
1. 전체 변경사항에 대한 종합적인 리뷰
2. 구체적인 개선 제안사항

다음 가이드라인을 따르세요:
- 코드 품질, 가독성, 잠재적 버그, 모범 사례에 중점을 두세요
- 이슈가 있는 위치(파일 경로와 라인 번호)를 정확하게 지정하세요
- 실행 가능한 제안을 제공하세요
- 제안은 간결하면서도 명확해야 합니다

GitHub PR diff 형식 이해:
1. 파일 경로 추출
   - 각 파일의 변경사항은 'diff --git a/[file_path] b/[file_path]' 형식으로 시작됩니다
   - 예시: 'diff --git a/src/utils.py b/src/utils.py'
   - 이 경우 file_path는 'src/utils.py'를 사용해야 합니다

2. 변경된 라인 추출
   - '@@ -X,Y +P,Q @@' 형식의 헤더는 변경된 라인 정보를 나타냅니다
   - X: 이전 파일의 시작 라인
   - Y: 이전 파일에서 변경된 라인 수
   - P: 새 파일의 시작 라인
   - Q: 새 파일에서 변경된 라인 수
   - 변경 내용은 이 헤더 바로 다음에 나타납니다

3. 변경 유형 구분
   - '+' 로 시작하는 라인: 새로 추가된 코드
   - '-' 로 시작하는 라인: 삭제된 코드
   - 공백으로 시작하는 라인: 변경되지 않은 컨텍스트 코드

한국어로 응답해주세요.

PR diff to review:
{diff}
""",
            input_variables=["diff"]
        ).with_structured_output(ReviewResponse)
        
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
