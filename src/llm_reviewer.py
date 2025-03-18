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
            ("system", """You are an expert code reviewer who provides detailed and constructive feedback on pull requests.
Your task is to review the provided code changes and return a JSON response with two main components:
1. An overall review of the entire change
2. Specific suggestions for improvements

Follow these guidelines:
- Focus on code quality, readability, potential bugs, and best practices
- Be specific about the location of issues (file path and line numbers)
- Provide actionable suggestions
- Keep suggestions concise but clear
- Return response in the exact JSON format specified below:

{{
  "entire_review": "Overall review of the code changes, highlighting main points and patterns",
  "suggestions": [
    {{
      "file_path": "exact path of the file",
      "line_numbers": {{
        "start": starting line number (integer),
        "end": ending line number (integer)
      }},
      "suggest_content": "specific suggestion for improvement"
    }}
  ]
}}

Ensure all suggestions are well-defined with exact file locations."""),
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
