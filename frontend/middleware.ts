import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // Next.js 정적 파일은 middleware에서 제외
  if (request.nextUrl.pathname.startsWith('/_next/')) {
    return NextResponse.next()
  }

  const token = request.cookies.get('token')?.value

  // /app 경로는 로그인 필요
  // 쿠키에 토큰이 없으면 클라이언트 사이드에서 localStorage를 확인하도록 통과
  // (클라이언트 사이드에서 체크하므로 middleware에서는 일단 통과)
  if (request.nextUrl.pathname.startsWith('/app')) {
    // 토큰이 없어도 일단 통과 (클라이언트에서 localStorage 확인)
    // 클라이언트 사이드 layout에서 체크함
  }

  // /admin 경로: 토큰 없으면 URL 직접 접근 차단 → 로그인으로 리다이렉트
  if (request.nextUrl.pathname.startsWith('/admin')) {
    if (!token) {
      const loginUrl = new URL('/login', request.url)
      loginUrl.searchParams.set('next', request.nextUrl.pathname)
      return NextResponse.redirect(loginUrl)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/app/:path*', '/admin/:path*'],
}
