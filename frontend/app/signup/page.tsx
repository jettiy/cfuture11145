'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { authAPI, getBackendConnectionErrorMessage } from '@/lib/api'

const IconUser = ({ className = '' }: { className?: string }) => (
  <svg className={`w-4 h-4 shrink-0 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
)
const IconLock = ({ className = '' }: { className?: string }) => (
  <svg className={`w-4 h-4 shrink-0 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
)
const IconUserCircle = ({ className = '' }: { className?: string }) => (
  <svg className={`w-4 h-4 shrink-0 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)
const IconCheck = ({ className = '' }: { className?: string }) => (
  <svg className={`w-4 h-4 shrink-0 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
)
const IconArrowLeft = ({ className = '' }: { className?: string }) => (
  <svg className={`w-5 h-5 shrink-0 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
  </svg>
)
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'

const useScrollAnimation = (options?: IntersectionObserverInit) => {
  const ref = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px', ...options }
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])

  return { ref, isVisible }
}

const FadeInUp = ({
  children,
  delay = 0,
  className = '',
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) => {
  const { ref, isVisible } = useScrollAnimation()
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
        transition: `opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s`,
      }}
    >
      {children}
    </div>
  )
}

const ScaleIn = ({
  children,
  delay = 0,
  className = '',
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) => {
  const { ref, isVisible } = useScrollAnimation()
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'scale(1)' : 'scale(0.95)',
        transition: `opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s`,
      }}
    >
      {children}
    </div>
  )
}

const SignalTalkLogo = () => (
  <svg viewBox="0 0 64 64" className="w-full h-full">
    <defs>
      <linearGradient id="logoGradientSignup" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#3b82f6" />
        <stop offset="100%" stopColor="#2563eb" />
      </linearGradient>
      <filter id="glowSignup">
        <feGaussianBlur stdDeviation="2" result="coloredBlur" />
        <feMerge>
          <feMergeNode in="coloredBlur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#logoGradientSignup)" />
    <g fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" filter="url(#glowSignup)">
      <path d="M18 32 Q18 24 24 20" />
      <path d="M18 32 Q18 40 24 44" />
      <circle cx="32" cy="32" r="4" fill="white" stroke="none" />
      <path d="M46 32 Q46 24 40 20" />
      <path d="M46 32 Q46 40 40 44" />
      <path d="M12 32 Q12 18 22 12" opacity="0.6" />
      <path d="M12 32 Q12 46 22 52" opacity="0.6" />
      <path d="M52 32 Q52 18 42 12" opacity="0.6" />
      <path d="M52 32 Q52 46 42 52" opacity="0.6" />
    </g>
  </svg>
)

export default function SignupPage() {
  const router = useRouter()
  const setAuth = useAuthStore((state) => state.setAuth)
  const [loading, setLoading] = useState(false)
  const [checkingUsername, setCheckingUsername] = useState(false)
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null)
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    nickname: '',
  })

  const handleCheckUsername = async () => {
    if (!formData.username.trim()) {
      toast.error('아이디를 입력해주세요')
      return
    }
    setCheckingUsername(true)
    try {
      const response = await authAPI.checkUsername(formData.username)
      setUsernameAvailable(response.data.available)
      if (response.data.available) {
        toast.success('사용 가능한 아이디입니다')
      } else {
        toast.error('이미 사용 중인 아이디입니다')
      }
    } catch (error: any) {
      const d = error.response?.data?.detail
      let msg: string
      if (error.code === 'ERR_NETWORK' || error.message === 'Network Error') {
        msg = getBackendConnectionErrorMessage()
      } else if (Array.isArray(d) && d.length) {
        msg = (d[0]?.msg ?? d[0]?.loc?.join('.')) || '중복 확인 중 오류가 발생했습니다.'
      } else if (typeof d === 'string') {
        msg = d
      } else {
        msg = '중복 확인 중 오류가 발생했습니다.'
      }
      toast.error(msg)
    } finally {
      setCheckingUsername(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.username || !formData.password || !formData.nickname) {
      toast.error('모든 필드를 입력해주세요')
      return
    }
    if (usernameAvailable === null) {
      toast.error('아이디 중복 확인을 해주세요')
      return
    }
    if (!usernameAvailable) {
      toast.error('사용 가능한 아이디로 변경해주세요')
      return
    }
    setLoading(true)
    try {
      const response = await authAPI.signup(formData)
      setAuth(response.data.user, response.data.access_token)
      toast.success('회원가입 성공!')
      router.push('/app')
    } catch (error: any) {
      const d = error.response?.data?.detail
      const errorMessage =
        Array.isArray(d) && d.length
          ? (d[0]?.msg ?? d[0]?.loc?.join('.') ?? '회원가입 실패')
          : (typeof d === 'string' ? d : '회원가입 실패')
      toast.error(errorMessage)
      if (String(errorMessage).includes('Username') || String(errorMessage).includes('username')) {
        toast.error('이미 사용 중인 아이디입니다')
        setUsernameAvailable(false)
      } else if (String(errorMessage).includes('Nickname') || String(errorMessage).includes('nickname')) {
        toast.error('이미 사용 중인 닉네임입니다')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0d1117] flex items-center justify-center p-4">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl animate-pulse" />
        <div
          className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-600/5 rounded-full blur-3xl animate-pulse"
          style={{ animationDelay: '1s' }}
        />
      </div>

      <div className="w-full max-w-md relative z-10">
        <FadeInUp delay={0}>
          <div className="text-center mb-8">
            <ScaleIn delay={0.1}>
              <div className="inline-flex items-center justify-center w-16 h-16 mb-4">
                <SignalTalkLogo />
              </div>
            </ScaleIn>
            <FadeInUp delay={0.2}>
              <h1 className="logo-korean text-4xl text-white mb-2 bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600 bg-clip-text text-transparent" style={{ letterSpacing: '-0.03em' }}>시그널톡</h1>
            </FadeInUp>
          </div>
        </FadeInUp>

        <FadeInUp delay={0.4}>
          <div className="border border-[#30363d] bg-[#161b22] rounded-xl shadow-2xl backdrop-blur-sm py-6 flex flex-col gap-6">
            <div className="space-y-1 px-6">
              <div className="flex items-center gap-2 mb-2">
                <Link
                  href="/login"
                  className="text-[#8b949e] hover:text-white transition-colors p-1 rounded-lg hover:bg-[#21262d]"
                >
                  <IconArrowLeft />
                </Link>
              </div>
              <h2 className="text-xl text-white text-center font-semibold tracking-tight">회원가입</h2>
              <p className="text-[#8b949e] text-center font-light text-sm">
                시그널톡에 가입하세요
              </p>
            </div>
            <div className="px-6">
              <form onSubmit={handleSubmit} className="space-y-4">
                <FadeInUp delay={0.6}>
                  <div className="space-y-2">
                    <label htmlFor="register-id" className="text-[#c9d1d9] text-sm font-medium block">
                      아이디
                    </label>
                    <div className="flex gap-2">
                      <div className="relative flex-1 group">
                        <IconUser className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b949e] transition-colors group-focus-within:text-blue-400" />
                        <input
                          id="register-id"
                          type="text"
                          placeholder="아이디를 입력하세요"
                          value={formData.username}
                          onChange={(e) => {
                            setFormData({ ...formData, username: e.target.value })
                            setUsernameAvailable(null)
                          }}
                          className="w-full h-9 pl-10 pr-3 rounded-md bg-[#21262d] border border-[#30363d] text-white placeholder:text-[#6e7681] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all duration-300"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={handleCheckUsername}
                        disabled={!formData.username.trim() || checkingUsername}
                        className="h-9 px-4 rounded-md bg-[#21262d] hover:bg-[#30363d] text-[#c9d1d9] border border-[#30363d] whitespace-nowrap transition-all duration-300 disabled:opacity-50 hover:border-blue-500/50 flex items-center gap-1"
                      >
                        {checkingUsername ? (
                          <>
                            <span className="w-4 h-4 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
                            확인중
                          </>
                        ) : usernameAvailable === true ? (
                          <>
                            <IconCheck className="w-4 h-4 text-green-400" />
                            <span className="text-green-400">사용가능</span>
                          </>
                        ) : (
                          '중복확인'
                        )}
                      </button>
                    </div>
                    {usernameAvailable === true && (
                      <p className="text-green-400 text-xs animate-pulse">사용 가능한 아이디입니다.</p>
                    )}
                  </div>
                </FadeInUp>

                <FadeInUp delay={0.7}>
                  <div className="space-y-2">
                    <label htmlFor="register-password" className="text-[#c9d1d9] text-sm font-medium block">
                      비밀번호
                    </label>
                    <div className="relative group">
                      <IconLock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b949e] transition-colors group-focus-within:text-blue-400" />
                      <input
                        id="register-password"
                        type="password"
                        placeholder="비밀번호를 입력하세요"
                        required
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="w-full h-9 pl-10 pr-3 rounded-md bg-[#21262d] border border-[#30363d] text-white placeholder:text-[#6e7681] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all duration-300"
                      />
                    </div>
                  </div>
                </FadeInUp>

                <FadeInUp delay={0.8}>
                  <div className="space-y-2">
                    <label htmlFor="register-nickname" className="text-[#c9d1d9] text-sm font-medium block">
                      닉네임
                    </label>
                    <div className="relative group">
                      <IconUserCircle className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b949e] transition-colors group-focus-within:text-blue-400" />
                      <input
                        id="register-nickname"
                        type="text"
                        placeholder="닉네임을 입력하세요"
                        required
                        value={formData.nickname}
                        onChange={(e) => setFormData({ ...formData, nickname: e.target.value })}
                        className="w-full h-9 pl-10 pr-3 rounded-md bg-[#21262d] border border-[#30363d] text-white placeholder:text-[#6e7681] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all duration-300"
                      />
                    </div>
                  </div>
                </FadeInUp>

                <FadeInUp delay={0.9}>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full h-10 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-md transition-all duration-300 shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
                  >
                    {loading ? '가입 중...' : '회원가입'}
                  </button>
                </FadeInUp>
              </form>

              <FadeInUp delay={1.0}>
                <div className="mt-6 text-center">
                  <p className="text-[#8b949e] text-sm font-light">
                    이미 계정이 있으신가요?{' '}
                    <Link
                      href="/login"
                      className="text-blue-400 hover:text-blue-300 font-medium transition-colors hover:underline underline-offset-2"
                    >
                      로그인
                    </Link>
                  </p>
                </div>
              </FadeInUp>
            </div>
          </div>
        </FadeInUp>

        <FadeInUp delay={1.1}>
          <p className="text-center text-[#6e7681] text-xs mt-8 font-light tracking-wide">
            © 2025 시그널톡. All rights reserved.
          </p>
        </FadeInUp>
      </div>
    </div>
  )
}
