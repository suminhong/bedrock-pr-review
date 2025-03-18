from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain.prompts import ChatPromptTemplate
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
    def __init__(self, model_id: str = "anthropic.claude-v2"):
        self.llm = ChatBedrockConverse(
            model_id=model_id,
            model_kwargs={"temperature": 0.1, "max_tokens": 4096}
        )
        
        self.output_parser = PydanticOutputParser(pydantic_object=ReviewResponse)
        format_instructions = self.output_parser.get_format_instructions()
        
        self.review_prompt = ChatPromptTemplate.from_messages(
            messages=[
            ("system", """당신은 풍부한 경험을 가진 전문 코드 리뷰어입니다. 풀 리퀘스트에 대해 상세하고 건설적인 피드백을 제공합니다.
주어진 코드 변경사항을 검토하고 다음 두 가지 주요 구성요소를 포함하는 응답을 반환하세요:
1. 전체 변경사항에 대한 종합적인 리뷰
2. 구체적인 개선 제안사항

다음 가이드라인을 따르세요:
- 코드 품질, 가독성, 잠재적 버그, 모범 사례에 중점을 두세요
- 이슈가 있는 위치(파일 경로와 라인 번호)를 정확하게 지정하세요
- 실행 가능한 제안을 제공하세요
- 제안은 간결하면서도 명확해야 합니다

파일 경로 추출 방법:
1. 파일 경로 표시자 확인
   - 각 파일의 내용은 '# FILE_PATH: [file_path]' 형식으로 시작합니다
   - 예시: '# FILE_PATH: utils/requests.py'
   - 이 경우 file_path는 'utils/requests.py'를 사용해야 합니다

2. 파일 경로 추출 규칙
   - '# FILE_PATH:' 뒤의 경로를 그대로 사용하세요
   - 경로 앞뒤의 공백을 제거하고 사용하세요
   - 경로를 임의로 변경하거나 수정하지 마세요

3. 라인 번호 추출
   - 코드 변경이 시작되는 줄부터 끝나는 줄까지의 번호를 파악하세요
   - 변경된 코드 부분의 정확한 시작과 끝 라인을 파악하세요


응답 형식:
{format_instructions}

모든 제안은 정확한 파일 위치와 함께 명확하게 정의되어야 합니다.

한국어로 응답해주세요."""),
            ("human", "Here is the PR diff to review:\n{diff}")
        ],
            partial_variables={"format_instructions": format_instructions}
        )

    def review_pr(self, diff_content: str) -> ReviewResponse:
        """
        Review the provided PR diff and return structured feedback.
        
        Args:
            diff_content (str): The git diff content to review
            
        Returns:
            ReviewResponse: Review results in the specified format
        """
        chain = self.review_prompt | self.llm | self.output_parser
        
        try:
            return chain.invoke({"diff": diff_content})
        except Exception as e:
            return ReviewResponse(
                entire_review=f"Error during review: {str(e)}",
                suggestions=[]
            )
