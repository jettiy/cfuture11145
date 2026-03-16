'use client'

import { useEffect, useState } from 'react'
import { newsAPI } from '@/lib/api'
import { formatKSTDateTime } from '@/lib/utils/time'
import { calcRelevanceForSymbol, type ImpactLevel } from '@/lib/relevance'

/** 뉴스 해석 캐시 (newsId -> 해석 텍스트) */
const interpretationCache: Record<number, string> = {}

interface News {
  id: number
  original_title: string
  ko_title: string | null
  ko_summary: string | null
  original_link: string
  original_summary: string | null
  is_breaking: boolean
  importance: string
  sentiment: 'bullish' | 'bearish' | 'neutral'
  source?: string | null
  published_at?: string | null
  created_at: string
}

interface NewsPanelProps {
  compact?: boolean
  symbol?: string
}

function toImpactLevel(importance?: string | null, isBreaking?: boolean): ImpactLevel {
  if (isBreaking) return 'critical'
  switch ((importance || '').toLowerCase()) {
    case 'critical': return 'critical'
    case 'high': return 'high'
    case 'medium': return 'medium'
    default: return 'low'
  }
}

export default function NewsPanel({ compact = false, symbol }: NewsPanelProps) {
  const [news, setNews] = useState<News[]>([])
  const [loading, setLoading] = useState(true)
  const [interpretations, setInterpretations] = useState<Record<number, string>>({ ...interpretationCache })
  const [loadingInterpretId, setLoadingInterpretId] = useState<number | null>(null)
  const [expandedInterpretId, setExpandedInterpretId] = useState<number | null>(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null)

  useEffect(() => {
    loadNews()
    const interval = setInterval(loadNews, 20000) // 20초마다 갱신

    // 실시간 뉴스 업데이트 수신 (신규 추가 또는 번역 완료 시 기존 항목 갱신)
    const handleNewsUpdate = (e: any) => {
      const payload = e?.detail
      if (!payload?.id) return
      setNews(prev => {
        const idx = prev.findIndex(n => n.id === payload.id)
        if (idx >= 0) {
          const next = [...prev]
          next[idx] = { ...next[idx], ...payload, id: payload.id }
          return next
        }
        return [payload, ...prev].slice(0, 20)
      })
    }

    window.addEventListener('news_update', handleNewsUpdate)
    return () => {
      clearInterval(interval)
      window.removeEventListener('news_update', handleNewsUpdate)
    }
  }, [symbol])

  const loadNews = async () => {
    try {
      const res = await newsAPI.getNews(20)
      setNews(Array.isArray(res?.data) ? res.data : [])
    } catch (error) {
      console.error('Failed to load news:', error)
      setNews([])
    } finally {
      setLoading(false)
      setLastUpdatedAt(new Date().toISOString())
    }
  }

  const handleNewsClick = (link: string) => {
    window.open(link, '_blank')
  }

  const handleShowInterpret = async (e: React.MouseEvent, item: News) => {
    e.stopPropagation()
    const id = item.id
    if (interpretations[id]) {
      setExpandedInterpretId((prev) => (prev === id ? null : id))
      return
    }
    setLoadingInterpretId(id)
    try {
      const res = await newsAPI.getInterpret(id)
      const text = res.data?.interpretation
      if (text) {
        interpretationCache[id] = text
        setInterpretations((prev) => ({ ...prev, [id]: text }))
        setExpandedInterpretId(id)
      }
    } catch {
      // 503 등 무시
    } finally {
      setLoadingInterpretId(null)
    }
  }

  const getTitle = (item: News) => item.ko_title?.trim() || item.original_title || ''
  const getKoreanHeadline = (item: News) => (item.ko_title || '').trim()
  const getKoreanSummary3 = (item: News): string[] => {
    const s = (item.ko_summary || '').trim()
    if (!s) return []
    return s.split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 3)
  }
  /** 원문 먼저 표시, 번역 도착 시 한글로 교체 (번역 준비 중 대기 없음) */
  const getDisplayHeadline = (item: News) => {
    const ko = getKoreanHeadline(item)
    if (ko) return ko
    return item.original_title?.trim() || '제목 없음'
  }
  const getDisplaySummaryLines = (item: News): string[] => {
    const ko3 = getKoreanSummary3(item)
    if (ko3.length > 0) return ko3
    const orig = (item.original_summary || '').trim()
    if (orig) return orig.split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 3)
    return []
  }
  const isTranslating = (item: News) => !(item.ko_title?.trim()) && !!item.original_title
  const getOneLiner = (item: News) => {
    const s = getKoreanSummary3(item)
    if (s.length > 0) return s[0]
    return ''
  }

  const formatKstSmart = formatKSTDateTime

  const getPrimaryTimeIso = (item: News) => item.published_at || item.created_at
  const safeTime = (item: News) => formatKstSmart(getPrimaryTimeIso(item))

  if (loading && news.length === 0) {
    return <div className="p-2 text-center text-gray-400 text-sm">로딩 중...</div>
  }

  const ranked = (() => {
    if (!symbol) return news
    return [...news]
      .map((n) => {
        const rel = calcRelevanceForSymbol({
          symbol,
          title: getTitle(n),
          summary: getOneLiner(n),
          source: (n as any).source || '',
          baseImpact: toImpactLevel(n.importance, n.is_breaking),
        })
        return { n, rel }
      })
      .sort((a, b) => (b.rel.score - a.rel.score) || (new Date(b.n.created_at).getTime() - new Date(a.n.created_at).getTime()))
      .map((x) => x.n)
  })()

  const displayNews = ranked

  if (!loading && displayNews.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500 text-[13px]">
        데이터 없음
        {lastUpdatedAt && (
          <div className="mt-1 text-[11px] text-gray-600">
            마지막 업데이트: {formatKSTDateTime(lastUpdatedAt)}
          </div>
        )}
      </div>
    )
  }

  if (compact) {
    // 컴팩트 모드: 핵심 이슈(종목 중심 정렬) + 뉴스 해석 페르소나
    return (
      <div className="space-y-1">
        {displayNews.slice(0, 5).map((item) => (
          <div
            key={item.id}
            className={`p-2 border-b border-gray-700 rounded ${item.is_breaking ? 'bg-red-900/30' : ''}`}
          >
            <div
              onClick={() => handleNewsClick(item.original_link)}
              className="cursor-pointer hover:bg-gray-700/50 -m-1 p-1 rounded transition"
            >
              <div className="flex items-center gap-2 mb-1">
                {item.is_breaking && (
                  <span className="px-1.5 py-0.5 bg-red-600 text-[10px] rounded font-semibold text-white">
                    BREAKING
                  </span>
                )}
                <span className={`w-1.5 h-1.5 rounded-full ${item.sentiment === 'bullish' ? 'bg-blue-500 shadow-[0_0_5px_rgba(59,130,246,0.8)]' :
                  item.sentiment === 'bearish' ? 'bg-red-500 shadow-[0_0_5px_rgba(239,68,68,0.8)]' :
                    'bg-gray-400'
                  }`} />
              </div>
              <div className="font-bold text-[13px] mb-1 line-clamp-1 text-gray-100">
                {getDisplayHeadline(item)}
                {isTranslating(item) && (
                  <span className="ml-1.5 text-[10px] font-normal text-amber-400/90">(번역 중)</span>
                )}
              </div>
              <div className="text-[11px] text-gray-400 line-clamp-2 space-y-0.5 font-medium leading-relaxed">
                {getDisplaySummaryLines(item).slice(0, 2).map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            </div>
            {/* 뉴스 해석 페르소나: 해석 보기 / 해석 문단 */}
            <div className="mt-1.5 pt-1.5 border-t border-gray-700/50">
              <button
                type="button"
                onClick={(e) => handleShowInterpret(e, item)}
                disabled={loadingInterpretId === item.id}
                className="text-[11px] text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1"
              >
                {loadingInterpretId === item.id ? (
                  <>해석 중...</>
                ) : interpretations[item.id] ? (
                  <>{expandedInterpretId === item.id ? '해석 접기' : '해석 보기'}</>
                ) : (
                  <>AI 뉴스 해석</>
                )}
              </button>
              {expandedInterpretId === item.id && interpretations[item.id] && (
                <div className="mt-1 text-[11px] text-gray-300 leading-relaxed bg-gray-800/60 rounded p-1.5 border border-amber-500/20">
                  {interpretations[item.id]}
                </div>
              )}
            </div>
            {symbol && (
              <div className="mt-1 flex flex-wrap gap-1">
                {calcRelevanceForSymbol({
                  symbol,
                  title: getDisplayHeadline(item),
                  summary: getOneLiner(item),
                  source: (item as any).source || '',
                  baseImpact: toImpactLevel(item.importance, item.is_breaking),
                }).assetTags.slice(0, 3).map((t) => (
                  <span key={t} className="px-1.5 py-0.5 bg-gray-800/70 border border-gray-700 text-[10px] rounded text-gray-300">{t}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-3 bg-gray-700 border-b border-gray-600">
        <h3 className="font-semibold">핵심 이슈</h3>
      </div>
      <div className="flex-1 overflow-y-auto">
        {displayNews.map((item) => (
          <div
            key={item.id}
            className={`p-3 border-b border-gray-700 ${item.is_breaking ? 'bg-red-900/30' : ''}`}
          >
            <div
              onClick={() => handleNewsClick(item.original_link)}
              className="cursor-pointer hover:bg-gray-700/50 -m-1 p-1 rounded transition"
            >
              <div className="flex items-center gap-2 mb-1">
                {item.is_breaking && (
                  <span className="px-2 py-0.5 bg-red-600 text-[11px] rounded font-semibold text-white">
                    BREAKING
                  </span>
                )}
                {item.importance === 'high' && (
                  <span className="px-2 py-0.5 bg-orange-600 text-[11px] rounded text-white">중요</span>
                )}
                <span className={`w-2 h-2 rounded-full ${item.sentiment === 'bullish' ? 'bg-blue-500 shadow-[0_0_5px_rgba(59,130,246,0.8)]' :
                  item.sentiment === 'bearish' ? 'bg-red-500 shadow-[0_0_5px_rgba(239,68,68,0.8)]' :
                    'bg-gray-400'
                  }`} />
              </div>
              <div className="font-bold text-[14px] mb-1 text-gray-100">
                {getDisplayHeadline(item)}
                {isTranslating(item) && (
                  <span className="ml-2 text-xs font-normal text-amber-400/90">(번역 중)</span>
                )}
              </div>
              <div className="text-[12px] text-gray-400 space-y-0.5 font-medium leading-relaxed">
                {getDisplaySummaryLines(item).map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-gray-700/50">
              <button
                type="button"
                onClick={(e) => handleShowInterpret(e, item)}
                disabled={loadingInterpretId === item.id}
                className="text-xs text-amber-400 hover:text-amber-300 font-medium"
              >
                {loadingInterpretId === item.id ? '해석 중...' : interpretations[item.id] ? (expandedInterpretId === item.id ? '해석 접기' : '해석 보기') : 'AI 뉴스 해석'}
              </button>
              {expandedInterpretId === item.id && interpretations[item.id] && (
                <div className="mt-1.5 text-[12px] text-gray-300 leading-relaxed bg-gray-800/60 rounded p-2 border border-amber-500/20">
                  {interpretations[item.id]}
                </div>
              )}
            </div>
            {symbol && (
              <div className="mt-2 flex flex-wrap gap-1">
                {calcRelevanceForSymbol({
                  symbol,
                  title: getDisplayHeadline(item),
                  summary: getOneLiner(item),
                  source: (item as any).source || '',
                  baseImpact: toImpactLevel(item.importance, item.is_breaking),
                }).assetTags.slice(0, 4).map((t) => (
                  <span key={t} className="px-1.5 py-0.5 bg-gray-800/70 border border-gray-700 text-[10px] rounded text-gray-300">{t}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
