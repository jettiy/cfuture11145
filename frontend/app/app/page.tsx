'use client'

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/lib/store'
import ChatPanel from '@/components/ChatPanel'
import NewsPanel from '@/components/NewsPanel'
import SignalPanel from '@/components/SignalPanel'
import RecentSignalsList from '@/components/RecentSignalsList'
import SymbolDecisionBoard from '@/components/SymbolDecisionBoard'

export default function TerminalPage() {
  const { user } = useAuthStore()
  const [selectedSymbol, setSelectedSymbol] = useState('NQ1!')
  const [mounted, setMounted] = useState(false)
  const [signalsRefreshKey, setSignalsRefreshKey] = useState(0)

  useEffect(() => {
    setMounted(true)
  }, [])

  const symbols = [
    { id: 'NQ1!', name: '나스닥선물' },
    { id: 'HSI1!', name: '항셍선물' },
    { id: 'GOLD', name: '골드선물' },
    { id: 'CL1!', name: '원유선물' },
  ]

  if (!mounted) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-900 text-white">
        <div>로딩 중...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-900 text-white">
        <div>로딩 중...</div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-gray-900">
      {/* 상단: 종목 탭 */}
      <div className="bg-gray-800 border-b border-gray-700 flex gap-2 p-2 items-center shrink-0">
        <span className="text-gray-400 text-sm mr-2">종목</span>
        {symbols.map((s) => (
          <button
            key={s.id}
            onClick={() => setSelectedSymbol(s.id)}
            className={`px-4 py-2 rounded ${selectedSymbol === s.id ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
              }`}
          >
            {s.name}
          </button>
        ))}
      </div>

      <div className="flex-1 flex overflow-hidden min-h-0 p-2 gap-2">
        {/* 왼쪽 컬럼: 최근 시그널 목록 + 실시간 뉴스 */}
        <div className="w-96 flex flex-col gap-2 shrink-0">
          <div className="flex-[2] bg-gray-800 border border-gray-700 rounded-xl flex flex-col overflow-hidden shadow-lg shadow-black/20">
            <RecentSignalsList key={signalsRefreshKey} />
          </div>
          <div className="flex-[1] min-h-[320px] bg-gray-800 border border-gray-700 rounded-xl flex flex-col overflow-hidden shadow-lg shadow-black/20">
            <div className="p-3 bg-gray-800/50 border-b border-gray-700 flex items-center gap-2 shrink-0">
              <span className="text-xs font-bold text-gray-200 uppercase tracking-wider">핵심 이슈</span>
            </div>
            <div className="flex-1 overflow-y-auto bg-gray-900/20">
              <NewsPanel compact={true} symbol={selectedSymbol} />
            </div>
          </div>
        </div>

        {/* 가운데 컬럼: AI 분석 패널 + 종목 중심 의사결정 보드 */}
        <div className="flex-1 flex flex-col gap-2 min-w-0">
          <div className="flex-[2] bg-gray-800 border border-gray-700 rounded-xl overflow-hidden shadow-lg shadow-black/20">
            <SignalPanel
              symbol={selectedSymbol}
              onSignalGenerated={() => setSignalsRefreshKey((k) => k + 1)}
            />
          </div>
          <div className="flex-[1] min-h-[320px] bg-gray-800 border border-gray-700 rounded-xl flex flex-col overflow-hidden shadow-lg shadow-black/20">
            <div className="p-3 bg-gray-800/50 border-b border-gray-700 flex items-center gap-2 shrink-0">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-blue-500 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.5)]"></span>
                <span className="text-xs font-bold text-gray-200 uppercase tracking-wider">종목 중심 의사결정 보드</span>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto bg-gray-900/20 p-1">
              <SymbolDecisionBoard symbol={selectedSymbol} />
            </div>
          </div>
        </div>

        {/* 오른쪽 컬럼: 유저 채팅 */}
        <div className="w-80 shrink-0 bg-gray-800 border border-gray-700 rounded-xl flex flex-col overflow-hidden shadow-xl shadow-black/30">
          <ChatPanel symbol={selectedSymbol} />
        </div>
      </div>
    </div>
  )
}
