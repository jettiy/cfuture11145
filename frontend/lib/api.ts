import axios from 'axios'

function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ''
    const base = (envUrl || `http://${window.location.hostname}:8000`).replace(/\/$/, '')
    return base
  }
  return (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
}

const API_BASE_URL = getApiBaseUrl()

/** 연결 실패 시 사용자 안내 문구 (로그인/회원가입 등에서 사용) */
export function getBackendConnectionErrorMessage(): string {
  const url = typeof window !== 'undefined' ? getApiBaseUrl() : API_BASE_URL
  return `백엔드에 연결할 수 없습니다. (1) 터미널에서 백엔드를 먼저 실행하세요: cd backend → .\\venv\\Scripts\\python.exe main.py (2) 주소: ${url}`
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: 토큰 추가 (로그인/회원가입 제외)
api.interceptors.request.use((config) => {
  const isAuthEndpoint = typeof config.url === 'string' && (config.url.includes('/api/auth/login') || config.url.includes('/api/auth/signup'))
  if (!isAuthEndpoint && typeof window !== 'undefined') {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: 에러 처리
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 에러: 인증 실패
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    // 네트워크 에러: 백엔드 서버 연결 실패
    if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
      const url = error.config?.baseURL || API_BASE_URL
      console.error(`백엔드 연결 실패: ${url} — 터미널에서 백엔드를 먼저 실행하세요. (cd backend && .\\venv\\Scripts\\python.exe main.py)`)
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authAPI = {
  signup: (data: {
    username: string
    password: string
    nickname: string
  }) => api.post('/api/auth/signup', data),

  checkEmail: (email: string) => api.get(`/api/auth/check-email/${encodeURIComponent(email)}`),
  checkPhone: (phone: string) => api.get(`/api/auth/check-phone/${encodeURIComponent(phone)}`),
  checkUsername: (username: string) => api.get(`/api/auth/check-username/${encodeURIComponent(username)}`),

  login: (username: string, password: string) => {
    const body = `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
    return api.post('/api/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },

  getMe: () => api.get('/api/auth/me'),
}

// Users API
export const usersAPI = {
  updateNickname: (nickname: string) => api.put('/api/users/nickname', { nickname }),
}

// Chat API
export const chatAPI = {
  getChannels: () => api.get('/api/chat/channels'),
  getMessages: (channelId: number, limit = 50) =>
    api.get(`/api/chat/channels/${channelId}/messages`, { params: { limit } }),
  sendMessage: (channelId: number, content: string) =>
    api.post('/api/chat/messages', { channel_id: channelId, content }),
}

// Private AI Assistant API (프라이빗 - 내 화면에서만 사용)
export const aiAPI = {
  ask: (data: { command: 'briefing' | 'news' | 'ask'; symbol?: string; message: string }) =>
    api.post('/api/ai/ask', data),
}

// News API
export const newsAPI = {
  getNews: (limit = 20) => api.get('/api/news', { params: { limit } }),
  getBreakingNews: (limit = 10) => api.get('/api/news/breaking', { params: { limit } }),
  /** 실시간 뉴스 해석 (뉴스 해석 페르소나) */
  getInterpret: (newsId: number) => api.get<{ news_id: number; interpretation: string }>(`/api/news/${newsId}/interpret`),
}

// Indicators & Earnings API
export const indicatorsAPI = {
  getIndicators: (country = 'US', category?: string, limit = 20, releasedOnly?: boolean) =>
    api.get('/api/indicators/indicators', { params: { country, category, limit, released_only: releasedOnly } }),
  getEarnings: (symbol?: string, limit = 20, date?: 'today') =>
    api.get('/api/indicators/earnings', { params: { symbol, limit, date } }),
}

// Calendar board response (통합 보드 API 단일 이벤트)
export type BoardEventResponse = {
  id: string
  type: 'economic' | 'custom'
  scheduled_at: string
  title: string
  description?: string | null
  country?: string | null
  importance?: string | null
  actual_value?: string | null
  forecast_value?: string | null
  previous_value?: string | null
  source_url?: string | null
  target_symbol?: string | null
}

// Calendar API
export const calendarAPI = {
  getCalendar: (country = 'US', daysAhead = 7, importance?: string) =>
    api.get('/api/calendar', { params: { country, days_ahead: daysAhead, importance } }),
  /** KST 오늘 00:00~24:00 이벤트 (예정 이벤트 fallback) */
  getTodayEvents: (country = 'US', importance?: string) =>
    api.get('/api/calendar/today-events', { params: { country, importance } }),
  /** 뉴스정리 패널 전용: Al Jazeera 헤드라인 5개만 */
  getNewsSummary: () => api.get('/api/calendar/news-summary'),
  getUpcomingEvents: (hoursAhead = 24, importance = 'high') =>
    api.get('/api/calendar/upcoming', { params: { hours_ahead: hoursAhead, importance } }),
  /** 지표/일정 통합 보드. range: 'today' = KST 오늘만, 'week' = 오늘~이번 주 일요일 */
  getBoard: (symbol?: string, hoursAhead = 168, importance = 'low', range?: 'today' | 'week') =>
    api.get<BoardEventResponse[]>('/api/calendar/board', {
      params: { symbol, hours_ahead: hoursAhead, importance, range_filter: range },
    }),
}

// Signals API
export const signalsAPI = {
  calculate: (symbol: string, timeframe: string, lookaheadN?: number) =>
    api.post('/api/signals/calculate', { symbol, timeframe, lookahead_n: lookaheadN }),
  getMySignals: (limit = 20) => api.get('/api/signals/my-signals', { params: { limit } }),
}

// Custom Events API (관리자 전용 - 특별 이벤트 관리)
export const customEventsAPI = {
  /** 커스텀 이벤트 목록 조회 */
  getEvents: (symbol?: string, activeOnly = true, limit = 50) =>
    api.get('/api/custom-events', { params: { symbol, active_only: activeOnly, limit } }),
  
  /** 새 커스텀 이벤트 등록 (관리자 전용) */
  createEvent: (data: {
    title: string
    event_date: string
    description?: string
    target_symbol?: string
    importance?: string
    link?: string
  }) => api.post('/api/custom-events', data),
  
  /** 커스텀 이벤트 수정 (관리자 전용) */
  updateEvent: (eventId: number, data: {
    title?: string
    event_date?: string
    description?: string
    target_symbol?: string
    importance?: string
    link?: string
    is_active?: boolean
  }) => api.put(`/api/custom-events/${eventId}`, data),
  
  /** 커스텀 이벤트 삭제 (관리자 전용) */
  deleteEvent: (eventId: number) => api.delete(`/api/custom-events/${eventId}`),
}

// Pro API
export const proAPI = {
  requestUpgrade: (data: { name: string; phone: string; email: string }) =>
    api.post('/api/pro/request-upgrade', data),
}

// Support API (사용자용)
export const supportAPI = {
  createChat: () => api.post('/api/support/create'),
  getMyChat: () => api.get('/api/support/my-chat'),
  getMessages: (chatId: number) => api.get(`/api/support/chats/${chatId}/messages`),
  sendMessage: (chatId: number, content: string) =>
    api.post(`/api/support/chats/${chatId}/messages`, { content }),
}

// Admin API
export const adminAPI = {
  listUsers: (search?: string, role?: string) =>
    api.get('/api/admin/users', { params: { search, role } }),
  updateUserRole: (userId: number, role: string) =>
    api.put('/api/admin/users/role', { user_id: userId, role }),
  banUser: (userId: number) => api.delete(`/api/admin/users/${userId}`),
  getStats: () => api.get('/api/admin/stats'),
  getSupportInbox: () => api.get('/api/admin/support/inbox'),
  getSupportMessages: (chatId: number) => api.get(`/api/admin/support/chats/${chatId}/messages`),
  respondToSupport: (chatId: number, content: string) =>
    api.post(`/api/admin/support/chats/${chatId}/respond`, { content }),
}
