def get_file_content(self, repo: str, file_path: str, max_size: int = 50000) -> Optional[str]:
    """파일 크기를 확인하고 적절한 경우에만 전체 내용을 가져옴"""
    try:
        # GitHub API로 파일 정보 가져오기
        content = self.github.get_repo(repo).get_contents(file_path)
        
        # 파일이 너무 크면 None 반환
        if content.size > max_size:
            return None
            
        return content.decoded_content.decode('utf-8')
    except Exception as e:
        return None

def review_file(self, file_path: str, diff: str, repo: str) -> FileReviewResponse:
    """파일별 리뷰 수행"""
    # 전체 파일 내용 가져오기 시도
    full_content = self.get_file_content(repo, file_path)
    
    # 프롬프트에 전체 내용 포함 여부 결정
    if full_content:
        template = self.file_review_prompt_with_content
        context = {"file_path": file_path, "diff": diff, "full_content": full_content}
    else:
        template = self.file_review_prompt
        context = {"file_path": file_path, "diff": diff}
    
    return template.invoke(context)


from typing import List, Tuple
import re

class PRReviewer:
    def parse_diff_hunks(self, diff: str) -> List[Tuple[int, int]]:
        """
        diff에서 변경된 라인 범위를 추출합니다.
        @@ -X,Y +P,Q @@ 형식에서 P(새 파일 시작 라인)와 Q(변경된 라인 수)를 추출
        
        Returns:
            List[Tuple[int, int]]: (시작 라인, 끝 라인) 튜플의 리스트
        """
        ranges = []
        for match in re.finditer(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', diff):
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) else 1
            ranges.append((start, start + count - 1))
        return ranges

    def merge_ranges(self, ranges: List[Tuple[int, int]], context_lines: int = 50) -> List[Tuple[int, int]]:
        """
        가까운 범위들을 하나로 합칩니다.
        각 범위 앞뒤로 context_lines만큼의 여유를 둡니다.
        """
        if not ranges:
            return []

        # 범위 정렬
        sorted_ranges = sorted(ranges)
        merged = []
        current_start, current_end = sorted_ranges[0]
        
        # context 라인 추가
        current_start = max(1, current_start - context_lines)
        current_end = current_end + context_lines

        for start, end in sorted_ranges[1:]:
            # context를 포함한 범위
            range_start = max(1, start - context_lines)
            range_end = end + context_lines

            # 범위가 겹치거나 가까우면 병합
            if range_start <= current_end:
                current_end = range_end
            else:
                merged.append((current_start, current_end))
                current_start, current_end = range_start, range_end

        merged.append((current_start, current_end))
        return merged

    def get_relevant_file_content(self, repo: str, file_path: str, diff: str, max_lines_per_range: int = 200) -> str:
        """
        변경된 부분과 그 주변 컨텍스트를 포함한 파일 내용을 가져옵니다.
        
        Args:
            repo: GitHub 레포지토리 이름
            file_path: 파일 경로
            diff: 파일의 diff 내용
            max_lines_per_range: 각 범위당 최대 라인 수
            
        Returns:
            str: 관련 파일 내용과 범위 정보
        """
        try:
            # diff에서 변경된 라인 범위 추출
            ranges = self.parse_diff_hunks(diff)
            
            # 범위 병합
            merged_ranges = self.merge_ranges(ranges)
            
            # 파일 내용 가져오기
            content = self.github.get_repo(repo).get_contents(file_path).decoded_content.decode('utf-8')
            lines = content.splitlines()
            
            # 각 범위의 내용 추출
            relevant_contents = []
            for start, end in merged_ranges:
                # 범위가 너무 크면 축소
                if end - start + 1 > max_lines_per_range:
                    mid = (start + end) // 2
                    half_range = max_lines_per_range // 2
                    start = mid - half_range
                    end = mid + half_range

                # 유효한 범위로 조정
                start = max(1, start)
                end = min(len(lines), end)
                
                # 범위 정보와 해당 내용 추가
                range_info = f"\n[Lines {start}-{end}]"
                range_content = "\n".join(lines[start-1:end])
                relevant_contents.append(f"{range_info}\n{range_content}")
            
            return "\n\n".join(relevant_contents)
            
        except Exception as e:
            return f"Failed to get file content: {str(e)}"

    def review_file(self, file_path: str, diff: str, repo: str) -> FileReviewResponse:
        """파일별 리뷰 수행"""
        # 관련 파일 내용 가져오기
        file_content = self.get_relevant_file_content(repo, file_path, diff)
        
        # 프롬프트에 전달할 컨텍스트 구성
        context = {
            "file_path": file_path,
            "diff": diff,
            "file_content": file_content
        }
        
        return self.file_review_prompt.invoke(context)

def get_relevant_file_content(self, repo: str, file_path: str, diff: str, context_lines: int = 50) -> str:
    """
    변경된 부분 주변의 관련 코드를 추출합니다.
    
    Args:
        repo (str): 레포지토리 이름
        file_path (str): 파일 경로
        diff (str): 파일의 diff 내용
        context_lines (int): 변경된 부분 위아래로 포함할 라인 수
    """
    try:
        # 전체 파일 내용 가져오기
        content = self.github.get_repo(repo).get_contents(file_path)
        full_content = content.decoded_content.decode('utf-8').splitlines()
        
        # diff에서 변경된 라인 번호 추출
        changed_lines = set()
        for hunk in diff.split('\n@@')[1:]:  # 첫 부분 제외
            # hunk 헤더에서 새 파일의 라인 정보 추출 (+P,Q)
            match = re.search(r'\+(\d+),(\d+)', hunk)
            if match:
                start = int(match.group(1))
                count = int(match.group(2))
                changed_lines.update(range(start, start + count))
        
        # 변경된 라인 주변의 컨텍스트 포함하여 관련 라인 선택
        relevant_ranges = []
        for line_num in sorted(changed_lines):
            start = max(1, line_num - context_lines)
            end = min(len(full_content), line_num + context_lines)
            relevant_ranges.append((start, end))
        
        # 겹치는 범위 병합
        merged_ranges = []
        for start, end in sorted(relevant_ranges):
            if not merged_ranges or start > merged_ranges[-1][1] + 1:
                merged_ranges.append([start, end])
            else:
                merged_ranges[-1][1] = max(merged_ranges[-1][1], end)
        
        # 선택된 범위의 코드 조각 추출
        code_snippets = []
        for start, end in merged_ranges:
            snippet = '\n'.join(full_content[start-1:end])
            code_snippets.append(f"# 라인 {start}-{end}\n{snippet}")
        
        return '\n\n'.join(code_snippets)
        
    except Exception as e:
        return None

def review_file(self, file_path: str, diff: str, repo: str) -> FileReviewResponse:
    """파일별 리뷰 수행"""
    # 변경된 부분 주변의 관련 코드 가져오기
    relevant_content = self.get_relevant_file_content(repo, file_path, diff)
    
    context = {
        "file_path": file_path,
        "diff": diff,
        "file_content": relevant_content or "전체 파일 내용을 가져올 수 없습니다."
    }
    
    return self.file_review_prompt.invoke(context)

self.file_review_prompt = PromptTemplate(
    template="""
당신은 풍부한 경험을 가진 전문 코드 리뷰어입니다. 주어진 파일의 변경사항에 대해 상세하고 건설적인 피드백을 제공합니다.

파일 경로: {file_path}

변경사항:
{diff}

관련 코드 컨텍스트:
{file_content}

다음 가이드라인을 따르세요:
1. 변경사항에 대한 전반적인 리뷰를 제공하세요
   - 코드 품질, 가독성, 잠재적 버그, 모범 사례 관점에서 분석
   - 변경사항의 목적과 영향을 평가
   - 주변 코드와의 일관성과 통합성 검토
   - 코드의 전반적인 구조와 설계에 대한 의견 제시

2. 필요한 경우 구체적인 개선 제안을 제공하세요 (선택사항)
   - 정확한 라인 번호 지정 (hunk 헤더 @@ -X,Y +P,Q @@ 참고)
   - 실행 가능하고 구체적인 개선 방안 제시
   - 간결하면서도 명확한 설명 제공

한국어로 응답해주세요.
""",
    input_variables=["file_path", "diff", "file_content"]
).with_structured_output(FileReviewResponse)