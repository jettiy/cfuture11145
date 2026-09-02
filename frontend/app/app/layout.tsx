'use client'

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuthStore } from '@/lib/store'
import Link from 'next/link'
import { ThemeToggle } from '@/components/ThemeToggle'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, clearAuth, isAdmin, setAuth } = useAuthStore()

  // localStorage에서 사용자 정보 로드 (클라이언트 사이드에서만)
  useEffect(() => {
    if (typeof window === 'undefined') return
    const token = localStorage.getItem('token')
    const userStr = localStorage.getItem('user')
    if (token && userStr && !user) {
      try {
        const userData = JSON.parse(userStr)
        setAuth(userData, token)
      } catch (e) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
      }
    }
  }, [setAuth, user])

  // 사용자 확인 및 리다이렉트 (localStorage 없고 store에도 user 없으면 로그인으로)
  useEffect(() => {
    if (typeof window === 'undefined') return
    const token = localStorage.getItem('token')
    const userStr = localStorage.getItem('user')
    if (token && userStr && !user) return
    if ((!token || !userStr) && !user) {
      router.replace('/login')
    }
  }, [user, router])

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center text-white">
        <p>로그인 확인 중...</p>
      </div>
    )
  }

  const isPro =
    String(user.role).toLowerCase() === 'pro' || String(user.role).toLowerCase() === 'admin'

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 transition-colors duration-300 font-sans">
      <nav className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-700 sticky top-0 z-50 transition-colors duration-300">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            {/* Logo Section */}
            <div className="flex items-center gap-8">
              <Link href="/app" className="flex items-center gap-2 group">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20 group-hover:shadow-blue-500/40 transition-all duration-300">
                  시
                </div>
                <span className="text-xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600">
                  시그널톡
                </span>
              </Link>

              {/* Desktop Navigation */}
              <div className="hidden md:flex items-center gap-2">
                {[
                  { href: '/app', label: 'Terminal' },
                  { href: '/app/support', label: '상담' },
                  { href: '/app/settings', label: '설정' },
                ].map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${pathname === item.href
                        ? 'bg-blue-600/10 text-blue-600 dark:text-blue-400 font-bold'
                        : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 hover:text-gray-900 dark:hover:text-gray-200'
                      }`}
                  >
                    {item.label}
                  </Link>
                ))}

                {!isPro && (
                  <Link
                    href="/app/pro-upgrade"
                    className={`ml-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all duration-200 flex items-center gap-1 ${pathname === '/app/pro-upgrade'
                        ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-600 dark:text-yellow-400'
                        : 'border-yellow-500/30 text-yellow-600 dark:text-yellow-400 hover:bg-yellow-500/10'
                      }`}
                  >
                    <span>👑</span> PRO Upgrade
                  </Link>
                )}

                {isAdmin() && (
                  <Link
                    href="/admin"
                    className={`ml-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all duration-200 ${pathname === '/admin'
                        ? 'bg-purple-600/10 border-purple-500/30 text-purple-600 dark:text-purple-400'
                        : 'border-purple-500/30 text-purple-600 dark:text-purple-400 hover:bg-purple-500/10'
                      }`}
                  >
                    Admin Console
                  </Link>
                )}
              </div>
            </div>

            {/* Right Section */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {user.nickname}
                </span>
                {isPro ? (
                  <span className="px-2 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-500 text-[10px] font-bold rounded-full border border-yellow-200 dark:border-yellow-500/30">
                    PRO
                  </span>
                ) : (
                  <span className="px-2 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-[10px] font-bold rounded-full">
                    BASIC
                  </span>
                )}
              </div>

              <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1"></div>

              <ThemeToggle />

              <button
                onClick={() => {
                  clearAuth()
                  router.push('/login')
                }}
                className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all duration-200"
                title="로그아웃"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </nav>
      <main className="container mx-auto px-4 py-6 animate-in fade-in duration-500">{children}</main>
    </div>
  )
}
