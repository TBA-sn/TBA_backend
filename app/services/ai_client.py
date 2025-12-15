import openai
import json_repair
import re
import os

class CodeReviewerClient:
    """
    vLLM 엔진(8001번 포트)과 통신하여 AI 코드 리뷰 및 수정 기능을 제공하는 클라이언트 클래스입니다.
    """
    
    def __init__(self, vllm_url="http://localhost:8001/v1"):
        """
        클라이언트 초기화
        :param vllm_url: vLLM 서버 주소 (기본값: 로컬 8001번 포트)
        """
        # vLLM은 OpenAI SDK와 호환됩니다. API 키는 로컬이라 필요 없지만 형식상 'EMPTY'를 넣습니다.
        self.client = openai.OpenAI(base_url=vllm_url, api_key="EMPTY")
        
        # start_vllm.sh에서 설정한 모델 이름 (--served-model-name)
        self.model_name = "deepseek-v3" 

        # 시스템 프롬프트 정의 (리뷰용 vs 수정용)
        self.REVIEW_SYS_PROMPT = "You are an expert Python code reviewer. Your task is to analyze Python code based on 4 criteria (bug, maintainability, style, security) and return the results in JSON format."
        self.FIX_SYS_PROMPT = "You are an expert Python Software Architect. Your task is to REFACTOR and FIX the code based on the provided Review Report."

    def get_review(self, code_snippet: str) -> dict:
        """
        [기능 1] 코드 리뷰 요청
        """
        user_prompt = (
            "[INST]\n"
            "Please review the following Python code based on 4 criteria "
            "and provide the results in the specified JSON format.\n"
            "The JSON MUST STRICTLY adhere to the following structure, including 'quality_score', "
            "'review_summary', 'scores_by_category', and 'review_details'.\n"
            
            # 점수 구조 예시를 줘서 형식을 고정합니다.
            'Example scores_by_category structure: {"bug": 93, "maintainability": 72, "style": 65, "security": 81}\n\n'
            
            f"[CODE]\n{code_snippet}\n[/CODE]\n"
            "[/INST]"
        )
        
        # vLLM 호출
        output_text = self._call_vllm(self.REVIEW_SYS_PROMPT, user_prompt)
        
        # 응답 후처리: [/INST] 태그 제거
        if "[/INST]" in output_text:
            output_text = output_text.split("[/INST]")[-1].strip()
        
        # JSON 파싱 및 자동 복구 (json_repair 사용)
        review_json = json_repair.loads(output_text)
        
        # 안전장치: 필수 필드 누락 시 기본값 채우기
        if "scores_by_category" not in review_json:
             review_json["scores_by_category"] = {"bug": 0, "maintainability": 0, "style": 0, "security": 0}
             
        return review_json

    def get_fix(self, code_snippet: str, review_summary: str, review_details: dict) -> str:
        """
        [기능 2] 최종 합본: 상세 리팩토링 지시 + 주석 보존 + 순수 코드 추출
        """
        # 1. 문맥 생성
        review_context = (
            f"Review Summary: {review_summary}\n"
            f"Detailed Issues: {review_details}"
        )

        # 2. 프롬프트 구성 (상세 지시와 안전 장치 결합)
        user_prompt = (
            "[INST]\n"
            "You are a strict Python Code Generator. Your ONLY task is to write fixed code.\n"
            "Refactor the [INPUT CODE] based on [ISSUES].\n\n"
            
            f"[INPUT CODE]\n{code_snippet}\n\n"
            f"[ISSUES]\n{review_context}\n\n"
            
            "--- STRICT RULES ---\n"
            "1. Output ONLY the valid Python code inside markdown blocks (```python ... ```).\n"
            "2. Fix bugs and security issues mentioned in the report.\n"
            
            # [복구됨] 사용자님이 작성하신 상세 리팩토링 가이드라인
            "3. IMPROVE MAINTAINABILITY:\n"
            "   - Reduce Cyclomatic Complexity (break down long functions into helpers).\n"
            "   - Reduce deep nesting (use guard clauses where possible).\n"
            "   - Apply PEP 8, Type Hints, and Docstrings.\n"
            
            # [유지] 주석 스마트 유지 및 한글 보존 규칙
            "4. Update existing comments to match the refactored logic.\n"
            "   CRITICAL: If the original comments are in Korean, KEEP them in Korean. Do not translate them to English.\n"
            
            # [유지] 출력 오염 방지 규칙
            "5. DO NOT write introductions (e.g., 'Here is the code') or explanations.\n"
            "6. DO NOT output JSON.\n"
            "[/INST]"
        )
        
        # 3. vLLM 호출
        output_text = self._call_vllm(self.FIX_SYS_PROMPT, user_prompt)
        
        # 4. 후처리 (잡담 제거 및 코드 추출)
        if "[/INST]" in output_text:
            output_text = output_text.split("[/INST]")[-1]
            
        code_match = re.search(r'```(?:python)?\s*(.*?)\s*```', output_text, re.DOTALL)
        
        if code_match:
            fixed_code = code_match.group(1)
        else:
            fixed_code = output_text.replace("```", "")
            
        return fixed_code.strip()

    def _call_vllm(self, system_msg, user_msg):
        """
        vLLM 서버로 실제 HTTP 요청을 보내는 내부 함수
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=2048, # 긴 코드도 생성할 수 있도록 넉넉하게
                temperature=0.0, # 결정론적 생성 (일관성 유지)
                stop=["<|EOT|>", "[/INST]"] # 생성을 멈출 토큰
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f" vLLM Connection Error: {e}")
            # vLLM이 꺼져있거나 연결 안 될 때 에러 발생
            raise RuntimeError("AI Engine (vLLM) is currently unavailable. Please check port 8001.")