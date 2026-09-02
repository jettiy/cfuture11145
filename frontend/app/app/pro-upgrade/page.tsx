'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { proAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'

export default function ProUpgradePage() {
  const router = useRouter()
  const { user } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name || !formData.phone || !formData.email) {
      toast.error('모든 필드를 입력해주세요')
      return
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(formData.email)) {
      toast.error('올바른 이메일 형식을 입력해주세요')
      return
    }

    setLoading(true)

    try {
      await proAPI.requestUpgrade(formData)
      toast.success('PRO 업그레이드 요청이 접수되었습니다! 상담을 위해 이동합니다.')
      // 1초 뒤에 상담 페이지로 이동
      setTimeout(() => {
        router.push('/app/support')
      }, 1000)
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || '요청 실패'
      if (errorMessage.includes('Email') || errorMessage.includes('email')) {
        toast.error('이미 사용 중인 이메일입니다')
      } else if (errorMessage.includes('Phone') || errorMessage.includes('phone')) {
        toast.error('이미 사용 중인 전화번호입니다')
      } else if (errorMessage.includes('pending')) {
        toast.error('이미 PRO 업그레이드 요청이 진행 중입니다')
      } else if (errorMessage.includes('Already PRO')) {
        toast.error('이미 PRO 또는 관리자 계정입니다')
      } else {
        toast.error(errorMessage)
      }
    } finally {
      setLoading(false)
    }
  }

  if (user && (user.role === 'pro' || user.role === 'admin')) {
    router.push('/app')
    return null
  }

  return (
    <div className="min-h-[calc(100vh-64px)] bg-gray-950 flex flex-col items-center justify-center p-6 bg-[radial-gradient(circle_at_top,_var(--tw-gradient-stops))] from-blue-900/10 via-gray-950 to-gray-950">
      <div className="max-w-4xl w-full grid md:grid-cols-2 gap-8 items-center">
        {/* Left: Info Section */}
        <div className="space-y-8 animate-in fade-in slide-in-from-left-8 duration-700">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-yellow-500/10 border border-yellow-500/30 rounded-full text-yellow-500 text-[10px] font-black uppercase tracking-widest mb-4">
              Premium Upgrade
            </div>
            <h1 className="text-4xl md:text-5xl font-black text-white leading-tight tracking-tight">
              Unlock Professional <br />
              <span className="text-blue-500">Trading Tools</span>
            </h1>
          </div>

          <div className="space-y-4">
            <div className="flex gap-4 p-4 bg-gray-900/50 border border-gray-800 rounded-2xl hover:border-blue-500/30 transition-colors">
              <div className="w-10 h-10 bg-blue-500/10 rounded-xl flex items-center justify-center text-xl shrink-0">⚡</div>
              <div>
                <div className="text-sm font-bold text-white mb-1">고고도 실시간 시그널 (1분/5분)</div>
                <div className="text-xs text-gray-500">초단기 매매를 위한 1분봉, 5분봉 AI 분석을 제한 없이 사용 가능합니다.</div>
              </div>
            </div>
            <div className="flex gap-4 p-4 bg-gray-900/50 border border-gray-800 rounded-2xl hover:border-blue-500/30 transition-colors">
              <div className="w-10 h-10 bg-purple-500/10 rounded-xl flex items-center justify-center text-xl shrink-0">🔥</div>
              <div>
                <div className="text-sm font-bold text-white mb-1">글로벌 고속 특보 시스템</div>
                <div className="text-xs text-gray-500">시장을 뒤흔드는 특급 속보를 지연 없이 가장 먼저 받아보세요.</div>
              </div>
            </div>
            <div className="flex gap-4 p-4 bg-gray-900/50 border border-gray-800 rounded-2xl hover:border-blue-500/30 transition-colors">
              <div className="w-10 h-10 bg-green-500/10 rounded-xl flex items-center justify-center text-xl shrink-0">💬</div>
              <div>
                <div className="text-sm font-bold text-white mb-1">1:1 전담 관리자 상담</div>
                <div className="text-xs text-gray-500">트레이딩 도구 활용법 및 계정 관리를 전문가에게 직접 상담받으세요.</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Registration Form */}
        <div className="bg-gray-900/80 backdrop-blur-xl p-8 rounded-[32px] border border-gray-800 shadow-2xl shadow-blue-500/5 animate-in fade-in slide-in-from-right-8 duration-700">
          <div className="mb-8">
            <h2 className="text-xl font-bold text-white mb-2">상담 정보 입력</h2>
            <p className="text-xs text-gray-500 font-medium">관리자 확인 후 바로 상담 채널이 개설됩니다.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest pl-1">Name</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-5 py-4 bg-gray-950 border border-gray-800 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/50 transition-all text-sm font-medium"
                placeholder="성함을 입력해주세요"
              />
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest pl-1">Phone Number</label>
              <input
                type="tel"
                required
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-5 py-4 bg-gray-950 border border-gray-800 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/50 transition-all text-sm font-medium"
                placeholder="010-0000-0000"
              />
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest pl-1">Email Address</label>
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-5 py-4 bg-gray-950 border border-gray-800 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/50 transition-all text-sm font-medium"
                placeholder="example@email.com"
              />
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading}
                className="w-full py-5 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-black text-sm tracking-tight shadow-xl shadow-blue-900/20 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:hover:scale-100 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    처리 중...
                  </>
                ) : (
                  '신청하고 상담 시작하기 🚀'
                )}
              </button>
            </div>

            <p className="text-center text-[10px] text-gray-600 px-4">
              신청 버튼을 누르면 개인정보 수집 및 상담 진행에 동의하는 것으로 간주됩니다.
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
