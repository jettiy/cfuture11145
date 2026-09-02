# API 호출 빈도 최적화 요약

## 문제
- GDELT 429 Too Many Requests
- yfinance rate limit 초과
- DB QueuePool timeout (세션 고갈)

## 적용된 변경 사항

### 1. 스케줄러 수집 주기 조정 (`app/scheduler.py`)

| 작업 | 변경 전 | 변경 후 | 환경변수 |
|------|---------|---------|----------|
| 뉴스 수집 | 30초 | **10분** | `NEWS_FETCH_INTERVAL_MINUTES` |
| 지표 수집 | 5분 | **15분** | `INDICATORS_FETCH_INTERVAL_MINUTES` |
| 실적 수집 | 5분 | **15분** | `INDICATORS_FETCH_INTERVAL_MINUTES` |
| 캘린더 수집 | 5분 | **15분** | `INDICATORS_FETCH_INTERVAL_MINUTES` |

### 2. 번역 작업 동시 실행 제한 (`app/services/news_service.py`)

```python
# semaphore로 최대 2개 동시 실행 제한
_TRANSLATION_SEMAPHORE = asyncio.Semaphore(2)

async def translate_news_in_background(news_id: int):
    async with _TRANSLATION_SEMAPHORE:
        # 번역 작업...
```

- **효과**: 뉴스 수집 시 다수의 번역 태스크가 동시에 실행되어 LLM API 및 DB 세션을 고갈시키는 문제 방지

### 3. GDELT 호출 간격 증가 (`app/services/gdelt_service.py`)

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| GDELT_MIN_INTERVAL_SEC | 300초 (5분) | **600초 (10분)** |

### 4. yfinance 요청 간격 증가 (`app/services/chart_data_service.py`)

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| _MIN_REQUEST_INTERVAL_SEC | 2.0초 | **3.0초** |

---

## 기대 효과

| 영역 | 개선 내용 |
|------|-----------|
| **API 호출 빈도** | 뉴스 120회/시간 → 6회/시간 (95% 감소) |
| **GDELT 429** | 5분 → 10분 간격으로 완화 |
| **yfinance rate limit** | 요청 간격 2초 → 3초로 완화 |
| **DB 세션 사용** | 번역 동시 실행 2개로 제한, 세션 고갈 방지 |
| **LLM API 부하** | 번역 요청 직렬화로 API 과부하 방지 |
| **Render 무료 환경** | CPU/메모리 사용량 감소, 안정적 운영 |

---

## 환경변수로 주기 조정 가능

Render 대시보드에서 환경변수 설정으로 주기를 조정할 수 있습니다:

```
NEWS_FETCH_INTERVAL_MINUTES=10       # 뉴스 수집 주기 (분)
INDICATORS_FETCH_INTERVAL_MINUTES=15 # 지표/실적/캘린더 수집 주기 (분)
```

---

## 수정된 파일 목록

1. `backend/app/scheduler.py` - 수집 주기 환경변수화 및 기본값 조정
2. `backend/app/services/news_service.py` - 번역 semaphore 추가
3. `backend/app/services/gdelt_service.py` - GDELT 호출 간격 증가
4. `backend/app/services/chart_data_service.py` - yfinance 요청 간격 증가
