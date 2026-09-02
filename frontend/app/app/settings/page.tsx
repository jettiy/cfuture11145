'use client'

import { useState } from 'react'
import { useAuthStore } from '@/lib/store'
import { usersAPI } from '@/lib/api'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { user, setAuth, token, isPro } = useAuthStore()
  const [nickname, setNickname] = useState(user?.nickname || '')
  const [lookaheadN, setLookaheadN] = useState(30)
  const [loading, setLoading] = useState(false)

  const handleUpdateNickname = async () => {
    if (!nickname.trim()) {
      toast.error('닉네임을 입력해주세요')
      return
    }

    setLoading(true)
    try {
      const res = await usersAPI.updateNickname(nickname)
      if (user && token) {
        setAuth(res.data, token)
      }
      toast.success('닉네임이 변경되었습니다')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '닉네임 변경 실패')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">설정</h1>

      <div className="bg-gray-800 rounded-lg p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2">닉네임</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              className="flex-1 px-4 py-2 bg-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleUpdateNickname}
              disabled={loading}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded disabled:opacity-50"
            >
              {loading ? '저장 중...' : '변경'}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            닉네임은 중복될 수 없습니다
          </p>
        </div>

        {isPro() && (
          <div>
            <label className="block text-sm font-medium mb-2">
              Lookahead N (시그널 계산)
            </label>
            <input
              type="number"
              value={lookaheadN}
              onChange={(e) => setLookaheadN(Number(e.target.value))}
              min="1"
              max="100"
              className="w-full px-4 py-2 bg-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              다음 N캔들 방향성 성공 확률 계산에 사용됩니다
            </p>
          </div>
        )}

        <div>
          <h3 className="text-sm font-medium mb-2">계정 정보</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">이름:</span>
              <span>{user?.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">이메일:</span>
              <span>{user?.email}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">권한:</span>
              <span className="uppercase">{user?.role}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
