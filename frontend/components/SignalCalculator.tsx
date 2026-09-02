'use client'

import { useState } from 'react'
import { useAuthStore } from '@/lib/store'
import { signalsAPI } from '@/lib/api'
import toast from 'react-hot-toast'

interface SignalCalculatorProps {
  symbol: string
  onClose: () => void
  onSignalGenerated?: (signal: any) => void
}

const TIMEFRAMES = [
  { value: '1M', label: '월', proOnly: false },
  { value: '1W', label: '주', proOnly: false },
  { value: '1D', label: '일', proOnly: false },
  { value: '1H', label: '60분', proOnly: false },
  { value: '30', label: '30분', proOnly: false },
  { value: '15', label: '15분', proOnly: false },
  { value: '5', label: '5분', proOnly: true },
  { value: '1', label: '1분', proOnly: true },
]

export default function SignalCalculator({ symbol, onClose, onSignalGenerated }: SignalCalculatorProps) {
  const { isPro } = useAuthStore()
  const [timeframe, setTimeframe] = useState('15')
  const [lookaheadN, setLookaheadN] = useState(30)
  const [loading, setLoading] = useState(false)
  const [signal, setSignal] = useState<any>(null)

  const handleCalculate = async () => {
    const selectedTf = TIMEFRAMES.find((tf) => tf.value === timeframe)
    if (selectedTf?.proOnly && !isPro()) {
      toast.error('PRO 구독이 필요합니다')
      return
    }

    setLoading(true)
    try {
      const res = await signalsAPI.calculate(symbol, timeframe, lookaheadN)
      setSignal(res.data)
      toast.success('시그널 계산 완료')
      // 시그널 생성 콜백 호출
      if (onSignalGenerated) {
        onSignalGenerated(res.data)
      }
    } catch (error: any) {
      console.error('Signal calculation error:', error)
      const errorMessage = error.response?.data?.detail || error.message || '시그널 계산 실패'
      
      // CORS 에러인 경우
      if (errorMessage.includes('CORS') || error.code === 'ERR_NETWORK') {
        toast.error('백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.')
      } else if (error.response?.status === 403) {
        toast.error('PRO 구독이 필요한 타임프레임입니다')
      } else {
        toast.error(errorMessage)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-lg">시그널 계산기</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white"
        >
          ✕
        </button>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2">타임프레임</label>
          <div className="grid grid-cols-4 gap-2">
            {TIMEFRAMES.map((tf) => {
              const disabled = tf.proOnly && !isPro()
              return (
                <button
                  key={tf.value}
                  onClick={() => !disabled && setTimeframe(tf.value)}
                  disabled={disabled}
                  className={`px-3 py-2 rounded text-sm ${
                    timeframe === tf.value
                      ? 'bg-blue-600'
                      : disabled
                      ? 'bg-gray-700 opacity-50 cursor-not-allowed'
                      : 'bg-gray-700 hover:bg-gray-600'
                  }`}
                  title={disabled ? 'PRO 전용' : ''}
                >
                  {tf.label}
                  {tf.proOnly && !disabled && <span className="text-xs">🔒</span>}
                </button>
              )
            })}
          </div>
        </div>

        {isPro() && (
          <div>
            <label className="block text-sm font-medium mb-2">
              Lookahead N (기본: 30)
            </label>
            <input
              type="number"
              value={lookaheadN}
              onChange={(e) => setLookaheadN(Number(e.target.value))}
              min="1"
              max="100"
              className="w-full px-3 py-2 bg-gray-700 rounded"
            />
          </div>
        )}

        <button
          onClick={handleCalculate}
          disabled={loading}
          className="w-full py-2 bg-blue-600 hover:bg-blue-700 rounded font-semibold disabled:opacity-50"
        >
          {loading ? '계산 중...' : '시그널 계산 시작'}
        </button>

        {signal && (
          <div className="mt-4 p-3 bg-gray-700 rounded space-y-4">
            {/* 원형 그래프 */}
            <div className="flex justify-center">
              <div className="relative w-32 h-32">
                <svg className="w-32 h-32 transform -rotate-90">
                  {/* 전체 원 둘레 (배경) */}
                  <circle
                    cx="64"
                    cy="64"
                    r="56"
                    fill="none"
                    stroke="#374151"
                    strokeWidth="12"
                    strokeLinecap="butt"
                  />
                  {(() => {
                    const circumference = 2 * Math.PI * 56
                    const isLong = signal.direction === 'LONG'
                    const mainPercentage = signal.probability
                    const remainingPercentage = 100 - mainPercentage
                    
                    // 메인 색상 (LONG이면 초록색, SHORT이면 빨간색)
                    const mainColor = isLong ? '#10b981' : '#ef4444'
                    // 나머지 색상 (LONG이면 빨간색, SHORT이면 초록색)
                    const remainingColor = isLong ? '#ef4444' : '#10b981'
                    
                    const mainLength = circumference * (mainPercentage / 100)
                    const remainingLength = circumference * (remainingPercentage / 100)
                    
                    return (
                      <>
                        {/* 메인 확률 (시계방향 12시부터) */}
                        <circle
                          cx="64"
                          cy="64"
                          r="56"
                          fill="none"
                          stroke={mainColor}
                          strokeWidth="12"
                          strokeDasharray={`${mainLength} ${circumference}`}
                          strokeDashoffset="0"
                          strokeLinecap="butt"
                        />
                        {/* 나머지 확률 (메인 다음부터) */}
                        <circle
                          cx="64"
                          cy="64"
                          r="56"
                          fill="none"
                          stroke={remainingColor}
                          strokeWidth="12"
                          strokeDasharray={`${remainingLength} ${circumference}`}
                          strokeDashoffset={`-${mainLength}`}
                          strokeLinecap="butt"
                        />
                      </>
                    )
                  })()}
                </svg>
                {/* 중앙 텍스트 */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <div className={`text-lg font-bold ${
                    signal.direction === 'LONG' ? 'text-green-500' : 'text-red-500'
                  }`}>
                    {signal.direction === 'LONG' ? '매수' : '매도'}
                  </div>
                  <div className="text-sm font-semibold text-gray-300">
                    {signal.probability.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>

            {/* 가격 정보 그리드 */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-gray-800 rounded p-2">
                <div className="text-xs text-gray-400 mb-1">진입가</div>
                <div className="text-sm font-semibold">{signal.entry_price.toFixed(2)}</div>
              </div>
              <div className="bg-gray-800 rounded p-2">
                <div className="text-xs text-gray-400 mb-1">손절가</div>
                <div className="text-sm font-semibold text-red-400">
                  {signal.stop_loss ? signal.stop_loss.toFixed(2) : '-'}
                </div>
              </div>
              <div className="bg-gray-800 rounded p-2">
                <div className="text-xs text-gray-400 mb-1">목표가</div>
                <div className="text-sm font-semibold text-green-400">
                  {signal.take_profit ? signal.take_profit.toFixed(2) : '-'}
                </div>
              </div>
              <div className="bg-gray-800 rounded p-2">
                <div className="text-xs text-gray-400 mb-1">손익비</div>
                <div className="text-sm font-semibold">
                  {signal.risk_reward ? `1:${signal.risk_reward.toFixed(1)}` : '-'}
                </div>
              </div>
            </div>

            {signal.rationale && (
              <div className="text-xs text-gray-400 mt-2 pt-2 border-t border-gray-600">
                {signal.rationale}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
