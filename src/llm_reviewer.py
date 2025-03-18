from typing import List, Dict, Any
import json
from langchain.prompts import ChatPromptTemplate
from langchain_aws import ChatBedrockConverse
from langchain.schema import StrOutputParser

class PRReviewer:
    def __init__(self, model_id: str = "anthropic.claude-v2"):
        self.llm = ChatBedrockConverse(
            model_id=model_id,
            model_kwargs={"temperature": 0.1, "max_tokens": 4096}
        )
        
        self.review_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 풍부한 경험을 가진 전문 코드 리뷰어입니다. 풀 리퀘스트에 대해 상세하고 건설적인 피드백을 제공합니다.
주어진 코드 변경사항을 검토하고 다음 두 가지 주요 구성요소를 포함하는 JSON 응답을 반환하세요:
1. 전체 변경사항에 대한 종합적인 리뷰
2. 구체적인 개선 제안사항

다음 가이드라인을 따르세요:
- 코드 품질, 가독성, 잠재적 버그, 모범 사례에 중점을 두세요
- 이슈가 있는 위치(파일 경로와 라인 번호)를 정확하게 지정하세요
- 실행 가능한 제안을 제공하세요
- 제안은 간결하면서도 명확해야 합니다

파일 경로 추출 방법 (중요: GitHub PR diff 형식 기준):
1. diff 헤더에서 파일 경로 추출
   - diff 헤더는 'diff --git a/[file_path] b/[file_path]' 형식으로 시작합니다
   - 예시: 'diff --git a/src/main.py b/src/main.py'
   - 이 경우 file_path는 'src/main.py'를 사용해야 합니다

2. 파일 경로 추출 규칙
   - a/나 b/ 접두어를 제외하고 경로를 사용하세요
   - 절대 경로가 아닌 상대 경로를 사용하세요
   - 경로를 임의로 변경하거나 수정하지 마세요

3. 라인 번호 추출
   - @@ -[start],[count] +[start],[count] @@ 형식의 hunk 헤더를 참고하세요
   - 예시: '@@ -15,7 +15,8 @@'
   - 변경된 코드 부분의 정확한 시작과 끝 라인을 파악하세요

응답은 아래 지정된 JSON 형식을 정확히 따라야 합니다:

{{
  "entire_review": "코드 변경사항에 대한 전반적인 리뷰, 주요 포인트와 패턴을 강조",
  "suggestions": [
    {{
      "file_path": "파일의 정확한 경로",
      "line_numbers": {{
        "start": "시작 라인 번호(정수)",
        "end": "끝 라인 번호(정수)"
      }},
      "suggest_content": "구체적인 개선 제안 내용"
    }}
  ]
}}

모든 제안은 정확한 파일 위치와 함께 명확하게 정의되어야 합니다.

한국어로 응답해주세요."""),
            ("human", "Here is the PR diff to review:\n{diff}")
        ])
        
        self.output_parser = StrOutputParser()

    def review_pr(self, diff_content: str) -> Dict[str, Any]:
        """
        Review the provided PR diff and return structured feedback.
        
        Args:
            diff_content (str): The git diff content to review
            
        Returns:
            Dict[str, Any]: Review results in the specified JSON format
        """
        chain = self.review_prompt | self.llm | self.output_parser
        
        try:
            result = chain.invoke({"diff": diff_content})
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "entire_review": "Error: Failed to parse LLM response",
                "suggestions": []
            }
        except Exception as e:
            return {
                "entire_review": f"Error during review: {str(e)}",
                "suggestions": []
            }
