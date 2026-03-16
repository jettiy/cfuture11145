'use client'

import { useEffect, useState } from 'react'
import { indicatorsAPI, calendarAPI } from '@/lib/api'
import { formatKSTDateTime } from '@/lib/utils/time'

interface Indicator {
  id: number
  name: string
  ko_name: string | null
  country: string
  category: string
  value: number | null
  previous_value: number | null
  forecast: number | null
  unit: string | null
  period: string | null
  release_date: string | null
  is_released: boolean
  link: string | null
}

interface CalendarEvent {
  id: number
  event_name: string
  ko_event_name: string | null
  country: string
  category: string
  importance: string
  scheduled_time: string
  actual_value: string | null
  forecast_value: string | null
  previous_value: string | null
  is_released: boolean
  link: string | null
}

interface IndicatorsPanelProps {
  symbol: string
}

export default function IndicatorsPanel({ symbol }: IndicatorsPanelProps) {
  const [indicators, setIndicators] = useState<Indicator[]>([])
  const [calendar, setCalendar] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [indicatorsRes, newsSummaryRes] = await Promise.all([
          indicatorsAPI.getIndicators('US,CN', undefined, 10),
          calendarAPI.getNewsSummary()
        ])
        setIndicators(Array.isArray(indicatorsRes?.data) ? indicatorsRes.data : [])
        setCalendar(Array.isArray(newsSummaryRes?.data) ? newsSummaryRes.data : [])
      } catch (error) {
        console.error('Failed to fetch indicators/calendar:', error)
        setIndicators([])
        setCalendar([])
      } finally {
        setLoading(false)
      }
    }
    fetchData()
    const interval = setInterval(fetchData, 20 * 1000) // 20초마다 갱신 (뉴스정리 반영)
    return () => clearInterval(interval)
  }, [])

  const formatDateTime = (dateStr: string | null) => formatKSTDateTime(dateStr)

  const getImportanceColor = (importance: string) => {
    switch (importance) {
      case 'critical':
        return 'bg-red-600'
      case 'high':
        return 'bg-orange-600'
      case 'medium':
        return 'bg-yellow-600'
      default:
        return 'bg-gray-600'
    }
  }

  if (loading) {
    return <div className="text-sm text-gray-400 p-4">로딩 중...</div>
  }

  const indicatorItems = [...indicators]
    .sort((a, b) => new Date(a.release_date || 0).getTime() - new Date(b.release_date || 0).getTime())
    .map(ind => ({
      id: ind.id,
      type: 'indicator' as const,
      title: ind.ko_name || ind.name,
      summary: [
        `결과: ${ind.value !== null ? (ind.value + (ind.unit || '')) : '발표 대기'}`,
        ind.previous_value !== null ? `이전: ${ind.previous_value}${ind.unit || ''}` : '',
        ind.forecast !== null ? `예측: ${ind.forecast}${ind.unit || ''}` : ''
      ],
      date: formatDateTime(ind.release_date),
      link: ind.link
    }))

  // 어려운 표현을 쉽게 요약 (뉴스정리 가독성)
  const simplifySummary = (forecastValue: string | null, actualValue: string | null, importance: string): string[] => {
    const lines: string[] = []
    const fv = (forecastValue || '').trim()
    const av = (actualValue || '').toLowerCase()
    if (av === 'breaking' || av === 'news') lines.push('속보')
    else if (fv) {
      const v = fv.toLowerCase()
      if (v === 'speech' || v.includes('연설')) lines.push('연설 예정')
      else if (v === 'breaking' || v === 'news') lines.push('속보')
      else if (fv.length > 20) lines.push(fv.slice(0, 30) + '…')
      else lines.push(fv)
    }
    if (importance === 'critical') lines.push('⚡ 시장에 큰 영향')
    else if (importance === 'high') lines.push('시장 주목')
    return lines
  }

  const calendarItemsRaw = [...calendar]
    .sort((a, b) => new Date(a.scheduled_time || 0).getTime() - new Date(b.scheduled_time || 0).getTime())
    .map(cal => ({
      id: cal.id,
      type: 'schedule' as const,
      title: cal.ko_event_name || cal.event_name,
      summary: simplifySummary(cal.forecast_value, cal.actual_value, cal.importance),
      date: formatDateTime(cal.scheduled_time),
      importance: cal.importance,
      category: cal.category,
      link: cal.link
    }))
  // 뉴스정리 중복 제거 (유사 제목 정규화: 의·쉼표 제거 후 동일하면 제거)
  const normalizeTitle = (t: string) =>
    (t || '')
      .replace(/,|،/g, ' ')
      .replace(/\s*의\s*/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 50)
  const seenKey = new Set<string>()
  const calendarItems = calendarItemsRaw.filter((item) => {
    const key = `${item.date || ''}|${normalizeTitle(item.title || '')}`
    if (seenKey.has(key)) return false
    seenKey.add(key)
    return true
  })

  const getTypeLabel = (type: string, category?: string) => {
    if (type === 'schedule' && category === 'news') return '뉴스'
    if (type === 'schedule' && (category === 'politics' || category === 'monetary')) return '특보'
    switch (type) {
      case 'indicator': return '지표'
      case 'schedule': return '일정'
      default: return ''
    }
  }

  const getTypeColor = (type: string, importance?: string, category?: string) => {
    if (type === 'schedule' && (category === 'politics' || category === 'monetary' || importance === 'critical')) {
      return 'bg-red-600 animate-pulse outline outline-1 outline-red-400'
    }
    if (type === 'schedule' && importance) return getImportanceColor(importance)
    switch (type) {
      case 'indicator': return 'bg-blue-600'
      case 'schedule': return 'bg-purple-600'
      default: return 'bg-gray-600'
    }
  }

  const renderItem = (item: any) => (
    <div
      key={`${item.type}-${item.id}`}
      onClick={() => item.link && window.open(item.link, '_blank')}
      className={`p-3 border-b border-gray-700 cursor-pointer hover:bg-gray-700 transition rounded ${item.type === 'schedule' && !item.importance ? 'opacity-50' : ''
        } ${item.link ? 'hover:border-blue-500/50' : ''}`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className={`px-2 py-1 ${getTypeColor(item.type, item.importance, item.category)} text-[13px] rounded font-bold text-white`}>
          {getTypeLabel(item.type, item.category)}
        </span>
        {item.date && <span className="text-[13px] text-gray-400 font-mono">{item.date}</span>}
      </div>
      <div className="font-bold text-[15px] mb-1.5 line-clamp-2 text-gray-100 leading-snug" title={item.title}>{item.title || '-'}</div>
      <div className="text-[13px] text-gray-400 space-y-0.5 font-medium leading-relaxed">
        {(Array.isArray(item.summary) ? item.summary : []).map((line: string, i: number) => (
          <div key={i}>{line}</div>
        ))}
      </div>
    </div>
  )

  if (indicatorItems.length === 0 && calendarItems.length === 0) {
    return <div className="text-sm text-gray-400 p-4 font-mono">데이터가 없습니다.</div>
  }

  return (
    <div className="flex h-full min-h-0 divide-x divide-gray-700 bg-gray-900/40">
      {/* 지표 섹션 */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="p-2.5 border-b border-gray-700 bg-gray-800/50 flex items-center justify-between">
          <span className="text-[13px] font-black text-blue-400 uppercase tracking-widest">매크로지표</span>
          <span className="w-1.5 h-1.5 bg-blue-500 rounded-full shadow-[0_0_5px_rgba(59,130,246,0.5)]"></span>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-hide">
          {indicatorItems.length > 0 ? indicatorItems.map(renderItem) : <div className="p-4 text-[13px] text-gray-500 text-center">지표 데이터 없음</div>}
        </div>
      </div>

      {/* 일정 섹션 - 뉴스정리 (폰트 크기 확대, 쉬운 표현) */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="p-2.5 border-b border-gray-700 bg-gray-800/50 flex items-center justify-between">
          <span className="text-[13px] font-black text-red-400 uppercase tracking-widest">뉴스정리</span>
          <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse shadow-[0_0_5px_rgba(239,68,68,0.5)]"></span>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-hide">
          {calendarItems.length > 0 ? calendarItems.map(renderItem) : <div className="p-4 text-[13px] text-gray-500 text-center">뉴스 없음</div>}
        </div>
      </div>
    </div>
  )
}
