'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LandingPage() {
  const router = useRouter()

  useEffect(() => {
    // 루트 페이지 접속 시 로그인 페이지로 리다이렉트
    router.push('/login')
  }, [router])

  return null
}
