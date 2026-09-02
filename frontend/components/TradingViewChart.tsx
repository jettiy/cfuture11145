'use client'

import { useEffect, useRef, useState } from 'react'
import { signalsAPI } from '@/lib/api'

interface TradingViewChartProps {
  symbol: string
  isPro: boolean
  currentSignal?: any // 현재 활성화된 시그널
}

export default function TradingViewChart({ symbol, isPro, currentSignal }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [recentSignals, setRecentSignals] = useState<any[]>([])

  // 최근 시그널 가져오기
  useEffect(() => {
    const fetchRecentSignals = async () => {
      try {
        const response = await signalsAPI.getMySignals(10)
        // 현재 심볼에 해당하는 시그널만 필터링
        const symbolName = symbol.split(':')[1] || symbol
        const filtered = response.data.filter((s: any) => {
          // 심볼 매칭 (TradingView 형식과 내부 형식 매칭)
          const sSymbol = s.symbol
          return sSymbol === symbolName || 
                 sSymbol.replace('!', '') === symbolName.replace('!', '') ||
                 symbolName.includes(sSymbol.replace('!', ''))
        })
        setRecentSignals(filtered.slice(0, 5)) // 최근 5개만
      } catch (error) {
        console.error('Failed to fetch recent signals:', error)
      }
    }
    fetchRecentSignals()
  }, [symbol])

  useEffect(() => {
    if (!containerRef.current) return

    // TradingView 위젯 스크립트 동적 로드
    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/tv.js'
    script.async = true
    script.onload = () => {
      if (window.TradingView && containerRef.current) {
        // TradingView 심볼은 이미 올바른 형식으로 전달됨
        const tvSymbol = symbol

        new window.TradingView.widget({
          autosize: true,
          symbol: tvSymbol,
          interval: '15',
          timezone: 'Asia/Seoul',
          theme: 'dark',
          style: '1',
          locale: 'ko',
          toolbar_bg: '#1a1a1a',
          enable_publishing: false,
          hide_top_toolbar: false,
          hide_legend: false,
          save_image: false,
          container_id: containerRef.current.id,
          // Member는 15분 지연, PRO는 LIVE
          datafeed: isPro
            ? undefined // PRO: 실시간 데이터
            : {
                // Member: 지연 데이터 시뮬레이션 (실제로는 TradingView Pro/Pro+ 구독 필요)
                onReady: (callback: any) => {
                  setTimeout(() => {
                    callback({
                      supported_resolutions: ['15', '60', 'D'],
                      supports_marks: false,
                      supports_timescale_marks: false,
                    })
                  }, 1000)
                },
              },
        })
      }
    }
    document.body.appendChild(script)

    return () => {
      // Cleanup
      if (containerRef.current) {
        containerRef.current.innerHTML = ''
      }
    }
  }, [symbol, isPro])

  const displaySignal = currentSignal || recentSignals[0]

  return (
    <div className="relative w-full h-full">
      <div
        id={`tradingview_${symbol}`}
        ref={containerRef}
        className="w-full h-full"
      />
      {!isPro && (
        <div className="absolute top-4 right-4 bg-yellow-600 px-3 py-1 rounded text-sm font-semibold">
          15분 지연
        </div>
      )}
      {isPro && (
        <div className="absolute top-4 right-4 bg-green-600 px-3 py-1 rounded text-sm font-semibold">
          LIVE
        </div>
      )}
      
      {/* 시그널 오버레이 표시 */}
      {displaySignal && (
        <div className="absolute bottom-4 left-4 bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-lg max-w-sm z-10">
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm font-semibold ${
              displaySignal.direction === 'LONG' ? 'text-green-400' : 'text-red-400'
            }`}>
              {displaySignal.direction === 'LONG' ? '매수' : '매도'} 시그널
            </span>
            <span className="text-xs text-gray-400">
              {displaySignal.probability?.toFixed(1)}% 확률
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-gray-400">진입가:</span>
              <span className="ml-1 font-semibold">{displaySignal.entry_price?.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-gray-400">목표가:</span>
              <span className="ml-1 font-semibold text-green-400">
                {displaySignal.take_profit?.toFixed(2)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">손절가:</span>
              <span className="ml-1 font-semibold text-red-400">
                {displaySignal.stop_loss?.toFixed(2)}
              </span>
            </div>
            <div>
              <span className="text-gray-400">손익비:</span>
              <span className="ml-1 font-semibold">
                1:{displaySignal.risk_reward?.toFixed(1)}
              </span>
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-300 border-t border-gray-600 pt-2">
            생각한 이유
          </div>
          {displaySignal.llm_cost && (
            <div className="mt-1 text-xs text-gray-500">
              분석 비용: ${displaySignal.llm_cost.toFixed(6)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// TradingView 타입 선언
declare global {
  interface Window {
    TradingView: any
  }
}
