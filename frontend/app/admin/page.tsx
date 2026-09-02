'use client'

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/lib/store'
import { adminAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { formatKSTDateTime, formatKSTTime } from '@/lib/utils/time'

export default function AdminPage() {
  const { isAdmin } = useAuthStore()
  const [users, setUsers] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [search, setSearch] = useState('')
  const [filterRole, setFilterRole] = useState('')
  const [supportChats, setSupportChats] = useState<any[]>([])
  const [selectedChatId, setSelectedChatId] = useState<number | null>(null)
  const [chatMessages, setChatMessages] = useState<any[]>([])
  const [replyMessage, setReplyMessage] = useState('')
  const [activeTab, setActiveTab] = useState<'users' | 'support'>('users')

  useEffect(() => {
    if (!isAdmin()) return
    loadUsers()
    loadStats()
    loadSupportChats()
  }, [isAdmin, search, filterRole])

  useEffect(() => {
    if (selectedChatId) {
      loadMessages(selectedChatId)
      const interval = setInterval(() => loadMessages(selectedChatId), 3000)
      return () => clearInterval(interval)
    }
  }, [selectedChatId])

  const loadUsers = async () => {
    try {
      const res = await adminAPI.listUsers(search || undefined, filterRole || undefined)
      setUsers(Array.isArray(res?.data) ? res.data : [])
    } catch (error) {
      console.error('Failed to load users:', error)
      setUsers([])
    }
  }

  const loadStats = async () => {
    try {
      const res = await adminAPI.getStats()
      setStats(res?.data ?? null)
    } catch (error) {
      console.error('Failed to load stats:', error)
      setStats(null)
    }
  }

  const loadSupportChats = async () => {
    try {
      const res = await adminAPI.getSupportInbox()
      setSupportChats(res.data)
    } catch (error) {
      console.error('Failed to load support chats:', error)
    }
  }

  const loadMessages = async (chatId: number) => {
    try {
      const res = await adminAPI.getSupportMessages(chatId)
      setChatMessages(res.data)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const handleSendMessage = async () => {
    if (!selectedChatId || !replyMessage.trim()) return
    try {
      await adminAPI.respondToSupport(selectedChatId, replyMessage)
      setReplyMessage('')
      loadMessages(selectedChatId)
    } catch (error) {
      toast.error('메시지 전송 실패')
    }
  }

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      await adminAPI.updateUserRole(userId, newRole)
      toast.success('권한이 변경되었습니다')
      loadUsers()
      loadStats()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '권한 변경 실패')
    }
  }

  const handleBanUser = async (userId: number, nickname: string) => {
    if (!confirm(`정말 "${nickname}" 계정을 삭제(밴)하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return
    try {
      await adminAPI.banUser(userId)
      toast.success('계정이 삭제되었습니다')
      loadUsers()
      loadStats()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '삭제 실패')
    }
  }

  if (!isAdmin()) {
    return (
      <div className="container mx-auto px-4 py-12 text-center bg-gray-950 min-h-screen flex items-center justify-center">
        <div className="bg-gray-900/50 p-8 rounded-2xl border border-red-500/20 max-w-md">
          <p className="text-red-500 text-lg font-bold mb-2">접근 제한됨</p>
          <p className="text-gray-400 text-sm">이 페이지를 보려면 관리자 권한이 필요합니다.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-gray-800 pb-8">
          <div>
            <h1 className="text-3xl font-black text-white tracking-tight mb-2">Admin Dashboard</h1>
            <p className="text-gray-500 text-sm font-medium">유저 관리 및 상담 업무를 통합 관리합니다.</p>
          </div>

          <div className="flex gap-2 p-1 bg-gray-900 rounded-xl border border-gray-800">
            <button
              onClick={() => setActiveTab('users')}
              className={`px-5 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === 'users' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-500 hover:text-gray-300'
                }`}
            >
              사용자 관리
            </button>
            <button
              onClick={() => setActiveTab('support')}
              className={`px-5 py-2.5 rounded-lg text-sm font-bold transition-all ${activeTab === 'support' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-500 hover:text-gray-300'
                }`}
            >
              상담 관리
            </button>
          </div>
        </div>

        {/* Overview Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-gray-900/50 p-5 rounded-2xl border border-gray-800">
              <div className="text-gray-500 text-[10px] font-bold uppercase tracking-wider mb-1">Total Users</div>
              <div className="text-2xl font-black text-white">{stats.total_users}</div>
            </div>
            <div className="bg-gray-900/50 p-5 rounded-2xl border border-gray-800">
              <div className="text-gray-500 text-[10px] font-bold uppercase tracking-wider mb-1">Members</div>
              <div className="text-2xl font-black text-gray-300">{stats.member_count}</div>
            </div>
            <div className="bg-blue-500/5 p-5 rounded-2xl border border-blue-500/10">
              <div className="text-blue-500/70 text-[10px] font-bold uppercase tracking-wider mb-1">PRO Users</div>
              <div className="text-2xl font-black text-blue-400">{stats.pro_count}</div>
            </div>
            <div className="bg-yellow-500/5 p-5 rounded-2xl border border-yellow-500/10">
              <div className="text-yellow-500/70 text-[10px] font-bold uppercase tracking-wider mb-1">Pending Pro</div>
              <div className="text-2xl font-black text-yellow-400">{stats.pending_pro_requests}</div>
            </div>
            <div className="bg-gray-900/50 p-5 rounded-2xl border border-gray-800">
              <div className="text-gray-500 text-[10px] font-bold uppercase tracking-wider mb-1">Admins</div>
              <div className="text-2xl font-black text-purple-400">{stats.admin_count}</div>
            </div>
          </div>
        )}

        {activeTab === 'users' && (
          <div className="bg-gray-900/30 rounded-3xl border border-gray-800/50 overflow-hidden">
            <div className="p-6 border-b border-gray-800 flex flex-col md:flex-row gap-4 items-center">
              <div className="relative flex-1 group">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 group-focus-within:text-blue-500 transition-colors">🔍</span>
                <input
                  type="text"
                  placeholder="닉네임, 이메일, 사용자명 검색..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 bg-gray-900/50 border border-gray-800 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/50 transition-all text-sm"
                />
              </div>
              <select
                value={filterRole}
                onChange={(e) => setFilterRole(e.target.value)}
                className="px-6 py-3 bg-gray-900/50 border border-gray-800 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/50 transition-all text-sm font-bold min-w-[150px]"
              >
                <option value="">모든 권한</option>
                <option value="MEMBER">일반 멤버</option>
                <option value="PRO">PRO 멤버</option>
                <option value="ADMIN">관리자</option>
              </select>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-900/50">
                    <th className="text-left py-4 px-6 text-[10px] font-bold text-gray-500 uppercase tracking-widest">User Info</th>
                    <th className="text-left py-4 px-6 text-[10px] font-bold text-gray-500 uppercase tracking-widest">Contact</th>
                    <th className="text-left py-4 px-6 text-[10px] font-bold text-gray-500 uppercase tracking-widest">Created At</th>
                    <th className="text-left py-4 px-6 text-[10px] font-bold text-gray-500 uppercase tracking-widest">Status / Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {users.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-800/20 transition-colors">
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs ${(user.role || '').toString().toLowerCase() === 'pro' ? 'bg-blue-500/20 text-blue-400' :
                            (user.role || '').toString().toLowerCase() === 'admin' ? 'bg-purple-500/20 text-purple-400' :
                              'bg-gray-800 text-gray-400'
                            }`}>
                            {(user.nickname || user.username || '?')[0].toUpperCase()}
                          </div>
                          <div>
                            <div className="text-sm font-bold text-white">{user.nickname}</div>
                            <div className="text-[10px] text-gray-500 font-mono">@{user.username}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-6">
                        <div className="text-xs text-gray-300 font-medium"> {user.name || '-'} </div>
                        <div className="text-[10px] text-gray-500">{user.email || '-'}</div>
                        <div className="text-[10px] text-gray-500">{user.phone || '-'}</div>
                      </td>
                      <td className="py-4 px-6 text-[10px] text-gray-500 font-mono">
                        {formatKSTDateTime(user.created_at)}
                      </td>
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <span className={`px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-tight ${user.role.toLowerCase() === 'pro' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/20' :
                            user.role.toLowerCase() === 'admin' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/20' :
                              'bg-gray-800 text-gray-500 border border-gray-700'
                            }`}>
                            {user.role}
                          </span>

                          {user.role.toLowerCase() !== 'admin' && (
                            <div className="flex flex-wrap items-center gap-2">
                              {user.role.toLowerCase() === 'member' ? (
                                <button
                                  onClick={() => handleRoleChange(user.id, 'PRO')}
                                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold shadow-lg shadow-blue-900/20 transition-all active:scale-95"
                                >
                                  PRO 승격
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleRoleChange(user.id, 'MEMBER')}
                                  className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-[10px] font-bold border border-gray-700 transition-all active:scale-95"
                                >
                                  MEMBER 강등
                                </button>
                              )}
                              <button
                                onClick={() => handleBanUser(user.id, (user.nickname || user.username || '').toString())}
                                className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-[10px] font-bold border border-red-500/50 transition-all active:scale-95"
                                title="계정 삭제(밴)"
                              >
                                Ban
                              </button>
                              {user.pro_request_status === 'pending' && (
                                <div className="flex items-center gap-1 text-[10px] text-yellow-500 font-bold animate-pulse">
                                  <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full"></span>
                                  신청됨
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'support' && (
          <div className="bg-gray-900/30 rounded-3xl border border-gray-800/50 p-6">
            {!selectedChatId ? (
              <>
                <h2 className="text-xl font-black text-white mb-6 flex items-center gap-2">
                  <span className="w-1.5 h-5 bg-blue-500 rounded-full"></span>
                  상담 대기 목록
                </h2>
                <div className="grid md:grid-cols-2 gap-4">
                  {supportChats.length === 0 ? (
                    <div className="col-span-2 text-center py-12 bg-gray-900/50 rounded-2xl border border-dashed border-gray-800">
                      <span className="text-3xl block mb-2">💬</span>
                      <p className="text-gray-500 text-sm">현재 대기 중인 상담이 없습니다.</p>
                    </div>
                  ) : (
                    supportChats.map((chat) => (
                      <div
                        key={chat.id}
                        className="p-5 bg-gray-900/80 border border-gray-800 rounded-2xl hover:border-gray-700 transition-all group"
                      >
                        <div className="flex justify-between items-start mb-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-gray-800 rounded-xl flex items-center justify-center text-lg">👤</div>
                            <div>
                              <div className="text-sm font-bold text-white mb-0.5">{chat.user_nickname}</div>
                              <div className="text-[10px] text-gray-500">{chat.user_email || 'No email'}</div>
                            </div>
                          </div>
                          <span className={`px-2 py-1 rounded text-[9px] font-black uppercase ${chat.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'
                            }`}>
                            {chat.status}
                          </span>
                        </div>

                        <div className="flex gap-2">
                          <button
                            onClick={() => setSelectedChatId(chat.id)}
                            className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 rounded-xl text-xs font-bold transition-all"
                          >
                            채팅 로그 보기
                          </button>
                          <button
                            onClick={() => setSelectedChatId(chat.id)}
                            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-blue-900/20"
                          >
                            상담 시작
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </>
            ) : (
              <div className="flex flex-col h-[600px]">
                <div className="flex justify-between items-center mb-4 pb-4 border-b border-gray-800">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setSelectedChatId(null)}
                      className="text-gray-500 hover:text-white transition-colors"
                    >
                      ← 뒤로
                    </button>
                    <h2 className="text-xl font-black text-white">상담 진행 중</h2>
                  </div>
                  <div className="text-xs text-gray-500 font-mono">Chat ID: #{selectedChatId}</div>
                </div>

                <div className="flex-1 overflow-y-auto space-y-4 mb-4 p-4 bg-gray-950/50 rounded-2xl border border-gray-800/50">
                  {chatMessages.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-gray-600 text-xs italic">
                      메시지가 없습니다.
                    </div>
                  ) : (
                    chatMessages.map((msg: any) => (
                      <div
                        key={msg.id}
                        className={`flex flex-col ${msg.is_admin ? 'items-end' : 'items-start'}`}
                      >
                        <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${msg.is_admin
                          ? 'bg-blue-600 text-white rounded-tr-none'
                          : 'bg-gray-800 text-gray-200 rounded-tl-none border border-gray-700'
                          }`}>
                          {msg.content}
                        </div>
                        <span className="text-[10px] text-gray-600 mt-1 px-1">
                          {formatKSTTime(msg.created_at)}
                        </span>
                      </div>
                    ))
                  )}
                </div>

                <div className="flex gap-2 p-2 bg-gray-900 rounded-2xl border border-gray-800">
                  <input
                    type="text"
                    value={replyMessage}
                    onChange={(e) => setReplyMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="상담 내용을 입력하세요..."
                    className="flex-1 bg-transparent px-4 focus:outline-none text-sm"
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={!replyMessage.trim()}
                    className="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all"
                  >
                    전송
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
