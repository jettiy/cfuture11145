'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { authAPI, getBackendConnectionErrorMessage } from '@/lib/api'
import { ThemeToggle } from '@/components/ThemeToggle'

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
      <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#3b82f6" />
        <stop offset="100%" stopColor="#2563eb" />
      </linearGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="2" result="coloredBlur" />
        <feMerge>
          <feMergeNode in="coloredBlur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#logoGradient)" />
    <g fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" filter="url(#glow)">
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

export default function LoginPage() {
  const router = useRouter()
  const setAuth = useAuthStore((state) => state.setAuth)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({ username: '', password: '' })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await authAPI.login(formData.username.trim(), formData.password)
      const data = response?.data
      if (!data?.access_token || !data?.user) {
        toast.error('로그인 응답 형식 오류')
        return
      }
      setAuth(data.user, data.access_token)
      if (typeof document !== 'undefined') {
        document.cookie = `token=${data.access_token}; path=/; max-age=86400`
      }
      toast.success('로그인 성공!')
      setTimeout(() => {
        window.location.href = '/app'
      }, 300)
    } catch (error: any) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Login error:', error?.response?.status, error?.response?.data, error?.message)
      }
      const d = error?.response?.data?.detail
      let errorMessage = '로그인 실패'
      if (typeof d === 'string') errorMessage = d
      else if (Array.isArray(d) && d.length) errorMessage = d[0]?.msg ?? d[0]?.loc?.join('.') ?? errorMessage
      else if (error?.code === 'ERR_NETWORK' || error?.message === 'Network Error') errorMessage = getBackendConnectionErrorMessage()
      toast.error(errorMessage)
      if (error?.response?.status === 401 || String(errorMessage).toLowerCase().includes('password') || String(errorMessage).toLowerCase().includes('username')) {
        setTimeout(() => {
          if (confirm('계정이 없으신가요? 회원가입 페이지로 이동하시겠습니까?')) {
            router.push('/signup')
          }
        }, 1000)
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

      <div className="fixed top-4 right-4 z-50">
        <ThemeToggle />
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
              <h2 className="text-xl text-white text-center font-semibold tracking-tight">로그인</h2>
              <p className="text-[#8b949e] text-center font-light text-sm">
                시그널톡 계정으로 로그인하세요
              </p>
            </div>
            <div className="px-6">
              <form onSubmit={handleSubmit} className="space-y-4">
                <FadeInUp delay={0.5}>
                  <div className="space-y-2">
                    <label htmlFor="login-id" className="text-[#c9d1d9] text-sm font-medium block">
                      아이디
                    </label>
                    <div className="relative group">
                      <IconUser className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b949e] transition-colors group-focus-within:text-blue-400" />
                      <input
                        id="login-id"
                        type="text"
                        placeholder="아이디를 입력하세요"
                        required
                        value={formData.username}
                        onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                        className="w-full h-9 pl-10 pr-3 rounded-md bg-[#21262d] border border-[#30363d] text-white placeholder:text-[#6e7681] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition-all duration-300"
                      />
                    </div>
                  </div>
                </FadeInUp>

                <FadeInUp delay={0.6}>
                  <div className="space-y-2">
                    <label htmlFor="login-password" className="text-[#c9d1d9] text-sm font-medium block">
                      비밀번호
                    </label>
                    <div className="relative group">
                      <IconLock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8b949e] transition-colors group-focus-within:text-blue-400" />
                      <input
                        id="login-password"
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

                <FadeInUp delay={0.7}>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full h-10 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-md transition-all duration-300 shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
                  >
                    {loading ? '로그인 중...' : '로그인'}
                  </button>
                </FadeInUp>
              </form>

              <FadeInUp delay={0.8}>
                <div className="mt-6 text-center">
                  <p className="text-[#8b949e] text-sm font-light">
                    계정이 없으신가요?{' '}
                    <Link
                      href="/signup"
                      className="text-blue-400 hover:text-blue-300 font-medium transition-colors hover:underline underline-offset-2"
                    >
                      회원가입
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
