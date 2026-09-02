"""
DeepSeek API 키 유효성 검증 유틸리티
서버 시작 시 API 키가 유효한지 확인합니다.
API 키는 환경 변수(Cloudflare Secrets 등)로만 주입합니다.
"""
import httpx
import os


def _load_api_config():
    """환경 변수에서만 API 설정 로드 (Cloudflare Secrets / 시스템 환경변수)"""
    api_key = os.getenv("LLM_API_KEY", "")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    return api_key, api_url, model

# 초기 로드
LLM_API_KEY, LLM_API_URL, LLM_MODEL = _load_api_config()


def validate_api_key_format(api_key: str) -> tuple[bool, str]:
    """
    API 키 형식 검증
    반환: (유효 여부, 에러 메시지)
    """
    if not api_key:
        return False, "API 키가 설정되지 않았습니다."
    
    if not api_key.startswith("sk-"):
        return False, "API 키는 'sk-'로 시작해야 합니다."
    
    if len(api_key) < 20:
        return False, "API 키가 너무 짧습니다. 올바른 형식인지 확인하세요."
    
    return True, ""


async def validate_api_key_connection() -> tuple[bool, str]:
    """
    실제 API 호출을 통해 API 키 유효성 검증
    반환: (유효 여부, 에러 메시지)
    """
    # 런타임에 최신 API 설정 로드
    current_api_key, current_api_url, current_model = _load_api_config()
    
    if not current_api_key:
        return False, "API 키가 설정되지 않았습니다. LLM_API_KEY 환경 변수(또는 Cloudflare Secrets)를 확인하세요."
    
    # 형식 검증
    is_valid_format, format_error = validate_api_key_format(current_api_key)
    if not is_valid_format:
        return False, format_error
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "Authorization": f"Bearer {current_api_key}",
                "Content-Type": "application/json"
            }
            
            # 최소한의 테스트 요청
            response = await client.post(
                current_api_url,
                headers=headers,
                json={
                    "model": current_model,
                    "messages": [
                        {"role": "user", "content": "test"}
                    ],
                    "max_tokens": 5
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                return True, "API 키가 유효합니다."
            elif response.status_code == 401:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error", {}).get("message", "인증 실패")
                return False, f"API 키 인증 실패 (401): {error_msg}. DeepSeek 대시보드에서 API 키를 확인하세요."
            elif response.status_code == 402:
                return False, "API 키는 유효하지만 계정 잔액이 부족합니다. DeepSeek 대시보드에서 잔액을 확인하세요."
            else:
                return False, f"API 키 검증 실패 ({response.status_code}): {response.text[:200]}"
                
    except httpx.TimeoutException:
        return False, "API 키 검증 중 타임아웃이 발생했습니다. 네트워크 연결을 확인하세요."
    except httpx.RequestError as e:
        return False, f"API 키 검증 중 네트워크 오류: {str(e)}"
    except Exception as e:
        return False, f"API 키 검증 중 예상치 못한 오류: {str(e)}"


def get_api_key_preview(_api_key: str) -> str:
    """
    로그/출력용으로 사용 금지. 키는 어떤 형태로도 로그에 남기지 않습니다.
    (레거시 호환용으로 시그니처만 유지)
    """
    return "(설정됨)" if _api_key else "(미설정)"
