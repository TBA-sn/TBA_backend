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
        self.REVIEW_SYS_PROMPT = (
            "You are an expert Python code reviewer. "
            "Your task is to analyze Python code based on 4 criteria "
            "(bug, maintainability, style, security) and return the results in JSON format."
        )

        self.FIX_SYS_PROMPT = (
            "You are an expert Python Software Architect. "
            "Your ONLY job is to REFACTOR and FIX the given Python code "
            "based on the Review Report, and RETURN ONLY THE FINAL PYTHON CODE. "
            "Do NOT return JSON. Do NOT return any explanation. "
            "Only return Python source code."
        )

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
            "Example scores_by_category structure: "
            "{\"bug\": 90, \"maintainability\": 70, \"style\": 60, \"security\": 80}\n\n"
            f"[CODE]\n{code_snippet}\n[/CODE]\n"
            "[/INST]"
        )
        
        output_text = self._call_vllm(self.REVIEW_SYS_PROMPT, user_prompt)
        
        if "[/INST]" in output_text:
            output_text = output_text.split("[/INST]")[-1].strip()
        
        review_json = json_repair.loads(output_text)
        
        if "scores_by_category" not in review_json:
            review_json["scores_by_category"] = {
                "bug": 0, "maintainability": 0, "style": 0, "security": 0
            }
             
        return review_json

    def get_fix(self, code_snippet: str, review_summary: str, review_details: dict) -> str:
        """
        [기능 2] 수정 코드 제안
        """
        review_context = f"Summary: {review_summary}\nDetails: {review_details}"

        # ✅ JSON 절대 금지 + 코드블록 강제
        user_prompt = (
            "[INST]\n"
            "You will be given some original Python code and a Review Report.\n"
            "Your job is to RETURN ONLY THE FINAL REFACTORED PYTHON CODE.\n\n"
            f"[ORIGINAL CODE]\n{code_snippet}\n\n"
            f"[REVIEW REPORT TO FIX]\n{review_context}\n\n"
            "Strictly follow these rules:\n"
            "1. Fix bugs and security issues mentioned in the report.\n"
            "2. IMPROVE MAINTAINABILITY: Reduce Cyclomatic Complexity, "
            "   split long functions into well-named helper functions, "
            "   and reduce deep nesting using guard clauses where appropriate.\n"
            "3. Apply PEP 8, Type Hints, and Docstrings.\n"
            "4. VERY IMPORTANT:\n"
            "   - NEVER output JSON.\n"
            "   - NEVER output any natural language explanation.\n"
            "   - Return ONLY ONE Markdown code block with the final refactored code,\n"
            "     formatted exactly as:\n"
            "     ```python\n"
            "     # your code here\n"
            "     ```\n"
            "[/INST]"
        )
        
        output_text = self._call_vllm(self.FIX_SYS_PROMPT, user_prompt)

        # 디버깅하고 싶으면 잠깐 열어봐도 됨
        # print("RAW FIX OUTPUT:", output_text[:300])

        if "[/INST]" in output_text:
            output_text = output_text.split("[/INST]")[-1].strip()
            
        # ```python / ```py / ``` 코드블록 우선 추출
        code_match = re.search(r'```(?:python|py)?\s*(.*?)\s*```', output_text, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1).strip()
        else:
            # 코드블록이 없으면 백틱만 날리고 사용
            fixed_code = output_text.replace("```", "").strip()
        
        # 🧱 방어: 또 JSON 뱉으면 여기서 컷
        if fixed_code.lstrip().startswith("{"):
            raise RuntimeError(
                "AI returned JSON instead of refactored code in get_fix. "
                "Check vLLM model / prompt configuration."
            )
        
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
                max_tokens=2048,
                temperature=0.0,
                stop=["<|EOT|>", "[/INST]"]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f" vLLM Connection Error: {e}")
            raise RuntimeError("AI Engine (vLLM) is currently unavailable. Please check port 8001.")
