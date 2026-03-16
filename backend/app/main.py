"""
uvicorn 실행 진입점 호환용 모듈.

이 프로젝트의 실제 FastAPI 앱은 `backend/main.py`에 정의되어 있습니다.
그런데 일부 실행 스크립트/가이드에서 `uvicorn app.main:app` 형태를 사용하므로,
해당 경로로도 앱을 import 할 수 있도록 얇은 래퍼를 제공합니다.
"""

from main import app  # noqa: F401

