/**
 * Asia/Seoul 기준 시간 포맷 유틸
 * 시그널, 채팅, 뉴스, 시계 등 전체 서비스 시간 표시 통일
 */
const TIMEZONE = 'Asia/Seoul'

/**
 * 백엔드가 timezone 없는 ISO 문자열(예: "2026-03-16T15:23:00")을 UTC로 내려주는 경우가 있어
 * 프론트에서 그대로 new Date()로 파싱하면 "로컬시간"으로 해석되어 9시간 오차가 날 수 있음.
 * timezone 표기(Z 또는 ±hh:mm)가 없으면 UTC로 간주해 'Z'를 붙여 파싱한다.
 */
export function parseDateAssumingUTC(input: string | Date): Date {
  if (input instanceof Date) return input
  const s = String(input).trim()
  const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(s)
  const normalized = hasTz ? s : `${s}Z`
  return new Date(normalized)
}

/**
 * KST(Asia/Seoul) 기준 날짜 문자열 YYYY-MM-DD
 * API 이벤트 시간(UTC/EST 등)을 파싱할 때 parseDateAssumingUTC 사용 후 이 함수로 KST 날짜 추출
 */
export function getKSTDateString(isoOrDate: string | Date): string {
  const d = typeof isoOrDate === 'string' ? parseDateAssumingUTC(isoOrDate) : isoOrDate
  if (isNaN(d.getTime())) return ''
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(d)
}

/**
 * KST 기준 "오늘" 날짜 문자열 (YYYY-MM-DD)
 * 브라우저 로컬 시간이 아닌 우측 KST 시계와 동기화된 오늘
 */
export function getTodayKST(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

/**
 * KST 기준 이번 주 월요일~금요일 날짜 집합 (YYYY-MM-DD)
 * 오늘 일정 / 이번주 일정 필터링에 사용
 */
export function getThisWeekKSTSet(): Set<string> {
  const todayStr = getTodayKST()
  if (!todayStr) return new Set()
  const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
  const d = new Date(todayStr + 'T12:00:00Z')
  const dayStr = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Seoul', weekday: 'long' }).format(d)
  const dayNum = dayNames.indexOf(dayStr)
  const monOffset = dayNum === 0 ? -6 : 1 - dayNum
  const set = new Set<string>()
  for (let i = 0; i < 5; i++) {
    const m = new Date(d)
    m.setUTCDate(m.getUTCDate() + monOffset + i)
    set.add(getKSTDateString(m))
  }
  return set
}

/**
 * 현재 시간의 KST 24시간제 문자열 반환 (HH:mm)
 * 이벤트 발생 시점에 호출하여 화면 표시용으로 사용
 */
export function getNowKSTTime(): string {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date())
}

/**
 * 현재 UTC 시간의 ISO 문자열 반환 (백엔드 전송용)
 * Vercel/Render 등 서버 환경 호환을 위해 UTC 기준으로 저장
 */
export function getNowISOString(): string {
  return new Date().toISOString()
}

/**
 * 시간만 표시 (HH:mm)
 * @param iso ISO 8601 문자열 또는 Date
 */
export function formatKSTTime(iso: string | Date | null | undefined): string {
  if (iso == null) return ''
  const d = parseDateAssumingUTC(iso)
  if (isNaN(d.getTime())) return ''
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d)
}

/**
 * 날짜+시간 표시 (MM/dd HH:mm 또는 오늘은 HH:mm만)
 * @param iso ISO 8601 문자열 또는 Date
 */
export function formatKSTDateTime(iso: string | Date | null | undefined): string {
  if (iso == null) return ''
  const d = parseDateAssumingUTC(iso)
  if (isNaN(d.getTime())) return ''
  const kstDay = new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(d)
  const nowKstDay = new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
  const time = new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(d)
  if (kstDay === nowKstDay) return time
  const md = new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    month: 'numeric',
    day: 'numeric',
  }).format(d)
  return `${md} ${time}`
}

/**
 * 실시간 시계용: HH:mm:ss (KST)
 */
export function formatKSTTimeWithSeconds(d: Date): string {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(d)
}

/**
 * 실시간 시계용: yyyy.MM.dd (eee) (KST)
 */
export function formatKSTDateWithWeekday(d: Date): string {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
  }).format(d)
}
