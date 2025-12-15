import openai
import json_repair
import re
import os

class CodeReviewerClient:
    """
    vLLM 엔진(8001번 포트)과 통신하여 AI 코드 리뷰 및 수정 기능을 제공하는 클라이언트 클래스입니다.
    """
    
    def __init__(self, vllm_url="http://localhost:8001/v1"):
        self.client = openai.OpenAI(base_url=vllm_url, api_key="EMPTY")
        self.model_name = "deepseek-v3" 

        # [기능 1] 리뷰용 (유지)
        self.REVIEW_SYS_PROMPT = "You are an expert Python code reviewer. Your task is to analyze Python code based on 4 criteria (bug, maintainability, style, security) and return the results in JSON format."
        
        # [기능 2] 수정용 (변경: 평가자(Reviewer) 느낌을 완전히 제거하고 '기계적인 코드 생성기'로 변경)
        self.FIX_SYS_PROMPT = (
            "You are a Python Code Refactoring Generator.\n"
            "You receive a code snippet and a list of required changes.\n"
            "Your output must be strictly the corrected Python code only.\n"
            "No JSON. No markdown text outside the code block. No comments about what you did."
        )

    def get_review(self, code_snippet: str) -> dict:
        """ [기능 1] 코드 리뷰 요청 (변경 없음) """
        user_prompt = (
            "Please review the following Python code based on 4 criteria "
            "and provide the results in the specified JSON format.\n"
            "The JSON MUST STRICTLY adhere to the following structure, including 'quality_score', "
            "'review_summary', 'scores_by_category', and 'review_details'.\n"
            "Example scores_by_category structure: {\"bug\": 93, \"maintainability\": 72, \"style\": 65, \"security\": 81}\n\n"
            f"[CODE]\n{code_snippet}\n[/CODE]"
        )
        
        output_text = self._call_vllm(self.REVIEW_SYS_PROMPT, user_prompt, temperature=0.0)
        
        if "[/INST]" in output_text:
            output_text = output_text.split("[/INST]")[-1].strip()
        
        review_json = json_repair.loads(output_text)
        if "scores_by_category" not in review_json:
             review_json["scores_by_category"] = {"bug": 0, "maintainability": 0, "style": 0, "security": 0}
        return review_json

    def get_fix(self, code_snippet: str, review_summary: str, review_details: dict) -> str:
        """
        [기능 2] 수정 코드 제안 (강력한 포맷 고정 적용)
        """
        # 1. 리뷰 결과를 '작업 목록(Todo List)'처럼 변환 (Review라는 단어 최소화)
        todo_list = []
        for category, issue in review_details.items():
            if isinstance(issue, list):
                for item in issue:
                    todo_list.append(f"- FIX [{category}]: {item}")
            else:
                todo_list.append(f"- FIX [{category}]: {issue}")
        
        todo_text = "\n".join(todo_list)

        # 2. 프롬프트 구성: '평가'가 아닌 '변환' 작업임을 강조
        user_prompt = (
            "Refactor the following Python code according to the TODO list.\n"
            "Focus on fixing security vulnerabilities and bugs first.\n\n"
            
            "### ORIGINAL CODE ###\n"
            f"```python\n{code_snippet}\n```\n\n"
            
            "### TODO LIST (Refactoring Requirements) ###\n"
            f"{review_summary}\n"
            f"{todo_text}\n\n"
            
            "### OUTPUT FORMAT ###\n"
            "Provide ONLY the refactored code inside a single markdown block.\n"
            "Do not output JSON. Do not output any conversation.\n"
            "Start your response immediately with: ```python"
        )
        
        # 3. Temperature 0.1 (약간의 창의성조차 줄여서 지시 이행률 높임)
        output_text = self._call_vllm(self.FIX_SYS_PROMPT, user_prompt, temperature=0.1)
        
        # 후처리
        if "[/INST]" in output_text:
            output_text = output_text.split("[/INST]")[-1]
            
        code_match = re.search(r'```(?:python)?\s*(.*?)\s*```', output_text, re.DOTALL | re.IGNORECASE)
        
        if code_match:
            fixed_code = code_match.group(1)
        else:
            # 만약 모델이 마크다운 없이 코드만 줬거나, JSON을 줬을 경우 대비
            # 간단한 휴리스틱: "{" 로 시작하면 실패로 간주하고 원본 반환하거나 에러 처리 가능
            if output_text.strip().startswith("{"):
                # 최후의 수단: JSON이 나오면 그냥 원본 코드를 반환하거나, 에러 로그 출력
                print(" Model returned JSON instead of code. Returning original code.")
                return code_snippet
            fixed_code = output_text.replace("```", "")
            
        return fixed_code.strip()

    def _call_vllm(self, system_msg, user_msg, temperature=0.0):
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=2048,
                temperature=temperature,
                stop=["<|EOT|>", "<|end_of_text|>"] 
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f" vLLM Connection Error: {e}")
            raise RuntimeError(f"AI Engine Error: {e}")