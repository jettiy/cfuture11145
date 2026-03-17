'use client'

import { useEffect, useMemo, useState } from 'react'
import { calendarAPI } from '@/lib/api'
import type { BoardEventResponse } from '@/lib/api'
// 시간/날짜: API(UTC) → KST(Asia/Seoul) 변환 및 오늘·이번주 필터는 @/lib/utils/time (Intl.DateTimeFormat) 사용
import { formatKSTDateTime, formatKSTTime } from '@/lib/utils/time'

/** 지표/일정 통합 리스트용 표준 타입 */
export type MergedEvent = {
  id: string | number
  type: 'economic' | 'custom'
  scheduledAt: string
  title: string
  description?: string | null
  forecastValue?: string | null
  previousValue?: string | null
  actualValue?: string | null
  sourceUrl?: string | null
  country?: string | null
  importance?: string | null
  targetSymbol?: string | null
}

function boardEventToMerged(e: BoardEventResponse): MergedEvent {
  return {
    id: e.id,
    type: e.type,
    scheduledAt: e.scheduled_at,
    title: e.title,
    description: e.description,
    forecastValue: e.forecast_value,
    previousValue: e.previous_value,
    actualValue: e.actual_value,
    sourceUrl: e.source_url,
    country: e.country,
    importance: e.importance,
    targetSymbol: e.target_symbol,
  }
}

const BOARD_HOURS_AHEAD = 168
/** 우측 KST 시계에 맞춰 1분마다 API 재호출 */
const BOARD_POLL_MS = 60_000

const INDICATOR_ACTUAL_UPDATE_EVENT = 'indicator_actual_updated'

export default function SymbolDecisionBoard({ symbol }: { symbol: string }) {
  const [todayEvents, setTodayEvents] = useState<MergedEvent[]>([])
  const [weekEvents, setWeekEvents] = useState<MergedEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null)
  const [realtimeRefreshTrigger, setRealtimeRefreshTrigger] = useState(0)

  useEffect(() => {
    const handler = () => setRealtimeRefreshTrigger((t) => t + 1)
    window.addEventListener(INDICATOR_ACTUAL_UPDATE_EVENT, handler)
    return () => window.removeEventListener(INDICATOR_ACTUAL_UPDATE_EVENT, handler)
  }, [])

  useEffect(() => {
    let alive = true
    const fetchBoard = async () => {
      try {
        const [todayRes, weekRes] = await Promise.all([
          calendarAPI.getBoard(symbol || undefined, BOARD_HOURS_AHEAD, 'low', 'today'),
          calendarAPI.getBoard(symbol || undefined, BOARD_HOURS_AHEAD, 'low', 'week'),
        ])
        if (!alive) return
        const todayList = Array.isArray(todayRes?.data) ? todayRes.data : []
        const weekList = Array.isArray(weekRes?.data) ? weekRes.data : []
        setTodayEvents(todayList.map(boardEventToMerged).sort((a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime()))
        setWeekEvents(weekList.map(boardEventToMerged).sort((a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime()))
        setLastUpdatedAt(new Date().toISOString())
      } catch (e) {
        if (!alive) return
        console.error('[DecisionBoard] Board fetch error:', e)
        setTodayEvents([])
        setWeekEvents([])
        setLastUpdatedAt(new Date().toISOString())
      } finally {
        if (!alive) return
        setLoading(false)
      }
    }
    fetchBoard()
    const interval = setInterval(fetchBoard, BOARD_POLL_MS)
    return () => {
      alive = false
      clearInterval(interval)
    }
  }, [symbol, realtimeRefreshTrigger])

  const isReleased = (e: MergedEvent) => e.actualValue != null && String(e.actualValue).trim() !== ''

  const EventItem = ({ event, dimReleased }: { event: MergedEvent; dimReleased?: boolean }) => {
    const timeStr = formatKSTTime(event.scheduledAt)
    const released = dimReleased !== false && isReleased(event)
    const actual = event.actualValue != null && event.actualValue !== '' ? event.actualValue : '-'
    const forecast = event.forecastValue != null && event.forecastValue !== '' ? event.forecastValue : '-'
    const previous = event.previousValue != null && event.previousValue !== '' ? event.previousValue : '-'
    return (
      <div
        role={event.sourceUrl ? 'button' : undefined}
        tabIndex={event.sourceUrl ? 0 : undefined}
        onClick={() => event.sourceUrl && window.open(event.sourceUrl, '_blank')}
        onKeyDown={(e) => event.sourceUrl && (e.key === 'Enter' || e.key === ' ') && window.open(event.sourceUrl!, '_blank')}
        className={`rounded-lg border border-gray-700/80 bg-gray-800/60 px-3 py-2 transition hover:bg-gray-700/50 hover:border-gray-600 ${event.sourceUrl ? 'cursor-pointer' : ''} ${released ? 'opacity-60' : ''}`}
      >
        <div className="font-bold text-gray-100 tabular-nums text-[13px]">
          [{timeStr}] {event.title}
        </div>
        <div className="mt-1 text-xs text-gray-400">
          실제치: {actual} | 예상치: {forecast} | 이전치: {previous}
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="h-full min-h-0 flex flex-col bg-gray-900/40 p-4">
        <div className="text-sm text-gray-400">로딩 중...</div>
      </div>
    )
  }

  return (
    <div className="h-full min-h-0 flex flex-col bg-gray-900/40">
      <div className="px-3 py-2 border-b border-gray-700 bg-gray-800/50 flex items-center justify-between shrink-0">
        <span className="text-[13px] font-black text-gray-200 tracking-wide">지표</span>
        {lastUpdatedAt && (
          <span className="text-[11px] text-gray-500 tabular-nums">
            업데이트 {formatKSTDateTime(lastUpdatedAt)}
          </span>
        )}
      </div>

      <div className="flex-1 min-h-0 p-3 overflow-hidden">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
          {/* 왼쪽: 오늘 일정 */}
          <div className="flex flex-col min-h-0">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">오늘 일정</h3>
            <div className="symbol-board-week-scroll space-y-1.5 overflow-y-auto pr-1">
              {todayEvents.length === 0 ? (
                <div className="py-4 text-center text-[13px] text-gray-500">오늘 예정된 미국 경제 지표가 없습니다.</div>
              ) : (
                todayEvents.map((event) => <EventItem key={event.id} event={event} dimReleased />)
              )}
            </div>
          </div>

          {/* 오른쪽: 이번주 일정 */}
          <div className="flex flex-col min-h-0">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">이번주 일정</h3>
            <div className="symbol-board-week-scroll space-y-1.5 overflow-y-auto pr-1 max-h-[400px]">
              {weekEvents.length === 0 ? (
                <div className="py-4 text-center text-[13px] text-gray-500">이번 주 예정된 일정이 없습니다.</div>
              ) : (
                weekEvents.map((event) => <EventItem key={event.id} event={event} dimReleased />)
              )}
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}
