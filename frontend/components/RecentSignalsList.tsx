'use client'

import { useState, useEffect } from 'react'
import { signalsAPI } from '@/lib/api'
import { formatKSTDateTime } from '@/lib/utils/time'

const SYMBOL_NAMES: Record<string, string> = {
  'NQ1!': '나스닥선물',
  'HSI1!': '항셍선물',
  'GOLD': '골드선물',
  'CL1!': '원유선물',
}

const TF_NAMES: Record<string, string> = {
  '1': '1분',
  '5': '5분',
  '15': '15분',
  '30': '30분',
  '1H': '60분',
  '1D': '일',
  '1W': '주',
  '1M': '월',
}

export default function RecentSignalsList() {
  const [signals, setSignals] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const fetchSignals = async () => {
    try {
      const res = await signalsAPI.getMySignals(15)
      const list = res.data || []
      setSignals(list)
    } catch (e) {
      console.error('Failed to fetch signals:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSignals()
  }, [])

  if (loading) {
    return (
      <div className="p-4 text-gray-400 text-sm">시그널 불러오는 중...</div>
    )
  }

  if (signals.length === 0) {
    return (
      <div className="p-4 text-gray-400 text-sm">아직 분석한 시그널이 없습니다. &apos;현재 상황 분석&apos;을 실행해보세요.</div>
    )
  }

  return (
    <div className="p-4 flex flex-col h-full">
      <h3 className="font-semibold text-sm mb-2">최근 시그널</h3>
      <ul className="space-y-2 overflow-y-auto flex-1">
        {signals.map((s) => (
          <li key={s.id} className="bg-gray-700 rounded-lg p-3 text-sm">
            <div className="flex justify-between items-center mb-1">
              <span className="font-medium">
                {SYMBOL_NAMES[s.symbol] || s.symbol} · {TF_NAMES[s.timeframe] || s.timeframe}봉
              </span>
              <span className={`font-semibold ${s.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                {s.direction === 'LONG' ? '매수' : '매도'} {s.probability?.toFixed(0)}%
              </span>
            </div>
            <div className="text-xs text-gray-400 flex justify-between">
              <span>진입 {s.entry_price != null ? Number(s.entry_price).toFixed(2) : '-'} · 목표 {s.take_profit != null ? Number(s.take_profit).toFixed(2) : '-'} · 손절 {s.stop_loss != null ? Number(s.stop_loss).toFixed(2) : '-'}</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">{formatKSTDateTime(s.created_at)}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}
