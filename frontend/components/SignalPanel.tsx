'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/lib/store'
import { signalsAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { formatKSTTimeWithSeconds, formatKSTDateWithWeekday } from '@/lib/utils/time'
import { Crown, LockKeyhole } from 'lucide-react'

interface SignalPanelProps {
  symbol: string
  onSignalGenerated?: (signal: any) => void
}

const TIMEFRAMES = [
  { value: '1M', label: '월봉', proOnly: false },
  { value: '1W', label: '주봉', proOnly: false },
  { value: '1D', label: '일봉', proOnly: false },
  { value: '1H', label: '60분봉', proOnly: false },
  { value: '30', label: '30분봉', proOnly: true },
  { value: '15', label: '15분봉', proOnly: true },
  { value: '5', label: '5분봉', proOnly: true },
  { value: '1', label: '1분봉', proOnly: true },
]

export default function SignalPanel({ symbol, onSignalGenerated }: SignalPanelProps) {
  const router = useRouter()
  const { user, isPro, theme, toggleTheme } = useAuthStore()
  const [timeframe, setTimeframe] = useState('15')
  const [lookaheadN, setLookaheadN] = useState(30)
  const [loading, setLoading] = useState(false)
  const [signal, setSignal] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [activeStep, setActiveStep] = useState<number | null>(null)
  const [now, setNow] = useState(new Date())
  const [isProModalOpen, setIsProModalOpen] = useState(false)

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!isProModalOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsProModalOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isProModalOpen])

  // 시그널 히스토리 불러오기
  useEffect(() => {
    if (user) {
      loadHistory()
    }
  }, [user])

  const loadHistory = async () => {
    try {
      const res = await signalsAPI.getMySignals(10) // 최근 10개만
      setHistory(res.data)
      // 가장 최근 시그널이 있으면 메인 화면에 표시 (선택사항)
      // if (res.data.length > 0) setSignal(res.data[0]) 
    } catch (error) {
      console.error('Failed to load signal history:', error)
    }
  }

  const handleAnalyze = async () => {
    const selectedTf = TIMEFRAMES.find((tf) => tf.value === timeframe)
    if (selectedTf?.proOnly && !isPro()) {
      toast.error('PRO 구독이 필요합니다')
      return
    }

    setLoading(true)
    setSignal(null)

    // 분석 단계 시뮬레이션
    setActiveStep(1) // 데이터 수집
    await new Promise(r => setTimeout(r, 600))
    setActiveStep(2) // 지표 계산
    await new Promise(r => setTimeout(r, 600))
    setActiveStep(3) // 인공지능 분석

    try {
      const res = await signalsAPI.calculate(symbol, timeframe, lookaheadN)
      setSignal(res.data)
      toast.success('애널리스트 분석 완료')
      onSignalGenerated?.(res.data)
      loadHistory() // 히스토리 갱신
    } catch (error: any) {
      console.error('Signal analysis error:', error)
      const statusCode = error.response?.status
      const errorMessage = error.response?.data?.detail || error.message || '분석 실패'

      if (statusCode === 401) {
        toast.error(`API 인증 실패: ${errorMessage}`, { duration: 8000 })
      } else if (statusCode === 402) {
        toast.error(`잔액 부족: ${errorMessage}`, { duration: 5000 })
      } else if (statusCode === 503) {
        toast.error(`LLM API 호출 실패: ${errorMessage}`, { duration: 5000 })
      } else if (statusCode === 403) {
        toast.error('PRO 구독이 필요한 타임프레임입니다')
      } else {
        toast.error(errorMessage)
      }
    } finally {
      setLoading(false)
      setActiveStep(null)
    }
  }

  const handleHistoryClick = (item: any) => {
    setSignal(item)
    toast('과거 분석 결과를 불러왔습니다', { icon: '📂' })
  }

  const steps = [
    { id: 1, label: '시장 데이터 동기화' },
    { id: 2, label: '기술적 지표 계산' },
    { id: 3, label: 'AI 심층 분석' },
  ]

  return (
    <div className="flex flex-col h-full bg-white/80 dark:bg-gray-800/50 backdrop-blur-md transition-colors duration-300">
      {/* Header Area */}
      <div className="p-5 pb-2">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-xl text-gray-800 dark:text-white flex items-center gap-2 transition-colors">
            <span className="w-2 h-6 bg-gradient-to-b from-blue-400 to-blue-600 rounded-full shadow-lg shadow-blue-500/30"></span>
            AI 애널리스트·단기트레이딩 시그널
          </h3>

          <div className="flex items-center gap-3">
            {/* Theme Toggle Button */}

            {/* Real-time Clock (KST) */}
            <div className="flex flex-col items-end">
              <div className="text-xl font-black font-mono text-gray-700 dark:text-white tracking-widest leading-none">
                {formatKSTTimeWithSeconds(now)}
              </div>
              <div className="text-xs text-gray-500 font-bold uppercase tracking-[0.1em] mt-1">
                {formatKSTDateWithWeekday(now)}
              </div>
            </div>
          </div>
        </div>

        {/* Timeframe Selector */}
        <div className="bg-gray-50 dark:bg-gray-900/40 rounded-xl p-4 border border-gray-200 dark:border-gray-700/50 shadow-sm">
          <label className="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-1">
            <span>TIMEFRAME</span>
            <span className="w-full h-px bg-gray-200 dark:bg-gray-800 ml-2"></span>
          </label>
          <div className="grid grid-cols-4 gap-2">
            {TIMEFRAMES.map((tf) => {
              const isLocked = tf.proOnly && !isPro()
              const active = timeframe === tf.value
              return (
                <button
                  key={tf.value}
                  onClick={() => {
                    if (isLocked) {
                      setIsProModalOpen(true)
                      return
                    }
                    setTimeframe(tf.value)
                  }}
                  className={`relative px-1 py-2.5 rounded-lg text-[11px] font-bold transition-all duration-200 border ${active
                    ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-md shadow-blue-500/20 border-transparent'
                    : isLocked
                      ? 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 border-gray-100 dark:border-gray-700 hover:border-amber-400/50 dark:hover:border-amber-400/40 hover:text-gray-700 dark:hover:text-gray-200 cursor-pointer'
                      : 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 border-gray-100 dark:border-gray-700 hover:border-blue-300 dark:hover:border-gray-600 hover:text-blue-500 dark:hover:text-gray-200 cursor-pointer'
                    }`}
                >
                  {tf.label}
                  {tf.proOnly && !active && (
                    <span className="absolute top-1 right-1">
                      <LockKeyhole className="w-3 h-3 text-amber-500" />
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* PRO Upgrade Modal */}
      {isProModalOpen && (
        <div
          className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
          onClick={() => setIsProModalOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-amber-500/20 bg-gray-950/95 shadow-2xl shadow-black/50 p-6 transform transition-all animate-in fade-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-center mb-4">
              <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                <Crown className="w-8 h-8 text-amber-400" />
              </div>
            </div>

            <div className="text-center">
              <div className="text-xl font-black text-white tracking-tight">
                더 정밀한 단기 타점을 원하시나요?
              </div>
              <div className="mt-2 text-sm text-gray-400 leading-relaxed">
                30분봉 이하의 짧은 타임프레임을 활용한 실시간 AI 시그널은 PRO 멤버십 전용 기능입니다.
                지금 업그레이드하고 초단기 변동성을 수익으로 연결해 보세요.
              </div>
            </div>

            <div className="mt-6 flex gap-2">
              <button
                type="button"
                onClick={() => setIsProModalOpen(false)}
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-700/60 bg-transparent text-gray-300 hover:bg-gray-800/40 transition"
              >
                닫기
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsProModalOpen(false)
                  router.push('/app/pro-upgrade')
                }}
                className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-500 text-gray-950 font-black hover:from-amber-400 hover:to-yellow-400 transition shadow-lg shadow-amber-500/20"
              >
                PRO 알아보기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-0 px-5 overflow-hidden">
        {/* Loading State */}
        {loading && (
          <div className="flex-1 flex flex-col items-center justify-center space-y-8 animate-in fade-in duration-300">
            <div className="relative">
              <div className="w-24 h-24 border-4 border-blue-100 dark:border-blue-500/10 border-t-blue-500 rounded-full animate-spin"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-2xl animate-pulse">⚡</span>
              </div>
            </div>
            <div className="space-y-4 w-full max-w-[240px]">
              {steps.map((step) => (
                <div key={step.id} className="flex items-center gap-4 group">
                  <div className={`w-2.5 h-2.5 rounded-full transition-colors duration-300 ${activeStep === step.id ? 'bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.6)] animate-pulse' : activeStep && activeStep > step.id ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`}></div>
                  <span className={`text-sm tracking-wide transition-colors duration-300 ${activeStep === step.id ? 'text-gray-800 dark:text-white font-bold' : 'text-gray-400 dark:text-gray-500'}`}>{step.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!signal && !loading && history.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 m-4 bg-gray-50 dark:bg-gray-900/20 rounded-3xl border border-dashed border-gray-200 dark:border-gray-700/50">
            <div className="w-20 h-20 bg-white dark:bg-gray-800 rounded-full flex items-center justify-center mb-6 shadow-sm">
              <span className="text-3xl text-gray-300">📈</span>
            </div>
            <p className="text-gray-600 dark:text-gray-300 font-bold text-lg mb-2">분석 준비 완료</p>
            <p className="text-gray-400 dark:text-gray-500 text-xs max-w-[200px] leading-relaxed">
              상단에서 타임프레임을 선택하고 버튼을 클릭하여 AI 분석을 시작하세요.
            </p>
          </div>
        )}

        {/* Signal Result */}
        {signal && !loading && (
          <div className="flex-1 overflow-hidden flex flex-col min-h-0">
            {/* Donut Chart & Direction (Compact) */}
            <div className="flex justify-center py-2 relative shrink-0">
              <div className="absolute inset-0 bg-blue-500/5 dark:bg-blue-500/5 blur-3xl rounded-full transform scale-75"></div>
              <div className="relative w-32 h-32">
                <svg className="w-32 h-32 transform -rotate-90 drop-shadow-lg">
                  <circle cx="64" cy="64" r="54" fill="none" stroke="currentColor" strokeWidth="8" className="text-gray-100 dark:text-gray-800" />
                  {(() => {
                    const circumference = 2 * Math.PI * 54
                    const isLong = signal.direction === 'LONG'
                    const mainPct = signal.probability
                    const mainColor = isLong ? '#10b981' : '#ef4444'
                    const mainLength = circumference * (mainPct / 100)
                    return (
                      <circle
                        cx="64" cy="64" r="54"
                        fill="none" stroke={mainColor} strokeWidth="8"
                        strokeDasharray={`${mainLength} ${circumference}`}
                        strokeLinecap="round"
                        className="transition-all duration-1000 ease-out"
                      />
                    )
                  })()}
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <div className={`text-2xl font-black tracking-tighter drop-shadow-sm ${signal.direction === 'LONG' ? 'text-green-500' : 'text-red-500'}`}>
                    {signal.direction === 'LONG' ? '매수' : '매도'}
                  </div>
                  <div className="text-lg font-bold text-gray-700 dark:text-white mb-[-2px]">{signal.probability?.toFixed(1)}%</div>
                </div>
              </div>
            </div>

            {/* Price Info Grid (Compact) */}
            <div className="grid grid-cols-2 gap-2 px-2 shrink-0">
              <div className="bg-white dark:bg-gray-800 rounded-lg p-2 border border-gray-100 dark:border-gray-700 shadow-sm relative overflow-hidden flex flex-col justify-center">
                <div className="text-[10px] text-gray-400 font-bold uppercase">진입가</div>
                <div className="text-sm font-mono font-bold text-gray-800 dark:text-blue-400">{signal.entry_price?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-lg p-2 border border-gray-100 dark:border-gray-700 shadow-sm relative overflow-hidden flex flex-col justify-center">
                <div className="text-[10px] text-gray-400 font-bold uppercase">손익비</div>
                <div className="text-sm font-mono font-bold text-gray-800 dark:text-indigo-400">1 : {signal.risk_reward?.toFixed(1)}</div>
              </div>
              <div className="bg-green-50 dark:bg-green-500/10 rounded-lg p-2 border border-green-100 dark:border-green-500/20 shadow-sm flex flex-col justify-center">
                <div className="text-[10px] text-green-600 dark:text-green-500/70 font-bold uppercase">익절가</div>
                <div className="text-sm font-mono font-bold text-green-600 dark:text-green-400">{signal.take_profit?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
              </div>
              <div className="bg-red-50 dark:bg-red-500/10 rounded-lg p-2 border border-red-100 dark:border-red-500/20 shadow-sm flex flex-col justify-center">
                <div className="text-[10px] text-red-600 dark:text-red-500/70 font-bold uppercase">손절가</div>
                <div className="text-sm font-mono font-bold text-red-600 dark:text-red-400">{signal.stop_loss?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
              </div>
            </div>

            {/* AI Strategy & Rationale (Flexible Height) - 폰트 크기 확대 */}
            <div className="mt-2 flex-1 min-h-0 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/10 dark:to-indigo-900/10 rounded-lg p-3 border border-blue-100 dark:border-blue-500/10 shadow-sm overflow-hidden flex flex-col">
              <div className="flex items-center gap-2 mb-1.5 shrink-0">
                <span className="text-blue-500 text-sm">💡</span>
                <div className="text-sm font-bold text-blue-600 dark:text-blue-300 tracking-wide">생각한 이유</div>
              </div>
              <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 text-[14px] text-gray-600 dark:text-gray-300 leading-relaxed font-medium bg-white/50 dark:bg-black/20 p-3 rounded border border-white/50 dark:border-white/5">
                "{signal.rationale}"
              </div>
            </div>
          </div>
        )}

        {/* History List (Shows when no active signal or active signal exists) */}
        {/* History List Removed as per user request */}
      </div>

      <div className="p-5 pt-0">
        <button
          onClick={handleAnalyze}
          disabled={loading}
          className="w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 rounded-xl font-bold disabled:opacity-50 text-white shadow-xl shadow-blue-500/20 transition-all duration-200 active:scale-[0.98] flex items-center justify-center gap-2 shrink-0 group relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span className="relative">시장 분석 중...</span>
            </>
          ) : (
            <>
              <span className="text-lg relative">⚡</span>
              <span className="relative">AI 시그널 생성</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}
