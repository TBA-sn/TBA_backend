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
        # 학습 때와 동일한 '강력한 프롬프트'로 교체
        user_prompt = (
            "[INST]\n"
            "Please review the following Python code based on 4 criteria "
            "and provide the results in the specified JSON format.\n"
            "The JSON MUST STRICTLY adhere to the following structure, including 'quality_score', "
            "'review_summary', 'scores_by_category', and 'review_details'.\n"
            
            # 점수 구조 예시를 줘서 형식을 고정합니다.
            "Example scores_by_category structure: {\"bug\": 90, \"maintainability\": 70, \"style\": 60, \"security\": 80}\n\n"
            
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
        [기능 2] 수정 코드 제안
        """
        review_context = f"Summary: {review_summary}\nDetails: {review_details}"

        # 여기도 상세한 가이드라인 유지
        user_prompt = (
            "[INST]\n"
            "Refactor the code below to be PRODUCTION-READY.\n\n"
            f"[ORIGINAL CODE]\n{code_snippet}\n\n"
            f"[REVIEW REPORT TO FIX]\n{review_context}\n\n"
            "Strictly follow these rules:\n"
            "1. Fix bugs and security issues mentioned in the report.\n"
            "2. Apply PEP 8, Type Hints, and Docstrings.\n"
            "Output ONLY the code block.\n[/INST]"
        )
        
        # vLLM 호출
        output_text = self._call_vllm(self.FIX_SYS_PROMPT, user_prompt)
        
        # 응답 후처리: [/INST] 태그 제거
        if "[/INST]" in output_text:
            output_text = output_text.split("[/INST]")[-1].strip()
            
        # 마크다운 코드 블록(```python ... ```)만 깔끔하게 추출
        code_match = re.search(r'```python\s*(.*?)\s*```', output_text, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1)
        else:
            fixed_code = output_text.replace("```", "").strip()
        
        return fixed_code

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