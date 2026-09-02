'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/lib/store'
import { adminAPI, supportAPI } from '@/lib/api'
import toast from 'react-hot-toast'
import { formatKSTDateTime, formatKSTTime } from '@/lib/utils/time'

export default function SupportPage() {
  const router = useRouter()
  const { user, isAdmin } = useAuthStore()
  const [supportChats, setSupportChats] = useState<any[]>([])
  const [selectedChat, setSelectedChat] = useState<any>(null)
  const [messages, setMessages] = useState<any[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 관리자용: PRO 요청 목록 로드
  useEffect(() => {
    if (isAdmin()) {
      loadAdminInbox()
    } else {
      loadMyChat()
    }
  }, [isAdmin])

  // 선택된 채팅의 메시지 로드
  useEffect(() => {
    if (selectedChat) {
      loadMessages(selectedChat.id)
    }
  }, [selectedChat])

  const loadAdminInbox = async () => {
    try {
      const res = await adminAPI.getSupportInbox()
      setSupportChats(res.data)
      if (res.data.length > 0 && !selectedChat) {
        setSelectedChat(res.data[0])
      }
    } catch (error) {
      console.error('Failed to load inbox:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadMyChat = async () => {
    try {
      const res = await supportAPI.getMyChat()
      setSelectedChat(res.data)
    } catch (error: any) {
      if (error.response?.status === 404) {
        // 채팅이 없으면 생성
        try {
          const createRes = await supportAPI.createChat()
          setSelectedChat(createRes.data)
        } catch (createError) {
          console.error('Failed to create chat:', createError)
        }
      }
    } finally {
      setLoading(false)
    }
  }

  const loadMessages = async (chatId: number) => {
    try {
      const res = isAdmin()
        ? await adminAPI.getSupportMessages(chatId)
        : await supportAPI.getMessages(chatId)
      setMessages(res.data)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || !selectedChat) return

    const messageContent = input.trim()
    setInput('')

    // 로컬에 즉시 추가
    const tempMessage = {
      id: Date.now(),
      content: messageContent,
      is_admin: isAdmin(),
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, tempMessage])

    try {
      if (isAdmin()) {
        await adminAPI.respondToSupport(selectedChat.id, messageContent)
      } else {
        await supportAPI.sendMessage(selectedChat.id, messageContent)
      }
      // 메시지 다시 로드
      loadMessages(selectedChat.id)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '메시지 전송 실패')
      // 실패 시 로컬 메시지 제거
      setMessages((prev) => prev.filter((m) => m.id !== tempMessage.id))
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-gray-400">로딩 중...</div>
      </div>
    )
  }

  // 관리자용: PRO 요청 목록 + 채팅
  if (isAdmin()) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <h1 className="text-2xl font-bold mb-6">상담 관리</h1>
        
        <div className="flex gap-4 h-[700px]">
          {/* PRO 요청 목록 */}
          <div className="w-80 bg-gray-800 rounded-lg flex flex-col">
            <div className="p-4 border-b border-gray-700">
              <h2 className="font-semibold">PRO 요청 목록</h2>
            </div>
            <div className="flex-1 overflow-y-auto">
              {supportChats.length === 0 ? (
                <div className="p-4 text-center text-gray-400 text-sm">
                  요청이 없습니다
                </div>
              ) : (
                supportChats.map((chat) => (
                  <div
                    key={chat.id}
                    onClick={() => setSelectedChat(chat)}
                    className={`p-4 border-b border-gray-700 cursor-pointer hover:bg-gray-700 ${
                      selectedChat?.id === chat.id ? 'bg-gray-700' : ''
                    }`}
                  >
                    <div className="font-semibold text-sm mb-1">
                      {chat.user_nickname || `User #${chat.user_id}`}
                    </div>
                    {chat.user_name && (
                      <div className="text-xs text-gray-400">
                        {chat.user_name} | {chat.user_phone} | {chat.user_email}
                      </div>
                    )}
                    <div className="text-xs text-gray-500 mt-1">
                      {formatKSTDateTime(chat.created_at)}
                    </div>
                    <div className={`text-xs mt-1 ${
                      chat.status === 'pending' ? 'text-yellow-400' :
                      chat.status === 'active' ? 'text-blue-400' :
                      'text-green-400'
                    }`}>
                      {chat.status === 'pending' ? '대기중' :
                       chat.status === 'active' ? '진행중' : '완료'}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* 채팅 영역 */}
          <div className="flex-1 bg-gray-800 rounded-lg flex flex-col">
            {selectedChat ? (
              <>
                <div className="p-4 border-b border-gray-700">
                  <h2 className="font-semibold">
                    {selectedChat.user_nickname || `User #${selectedChat.user_id}`}
                  </h2>
                  {selectedChat.user_name && (
                    <div className="text-sm text-gray-400 mt-1">
                      {selectedChat.user_name} | {selectedChat.user_phone} | {selectedChat.user_email}
                    </div>
                  )}
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.is_admin ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-xs p-3 rounded-lg ${
                          msg.is_admin
                            ? 'bg-blue-600'
                            : 'bg-gray-700'
                        }`}
                      >
                        <div className="text-sm">{msg.content}</div>
                        <div className="text-xs text-gray-400 mt-1">
                          {formatKSTTime(msg.created_at)}
                        </div>
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>
                <div className="p-4 border-t border-gray-700 flex gap-2">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="메시지 입력..."
                    className="flex-1 px-4 py-2 bg-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={handleSend}
                    className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded"
                  >
                    전송
                  </button>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-400">
                채팅을 선택해주세요
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // 사용자용: PRO 업그레이드 요청 또는 상담
  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <h1 className="text-2xl font-bold mb-6">상담</h1>

      {!selectedChat ? (
        <div className="bg-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-400 mb-6">
            PRO 업그레이드 또는 문의사항이 있으신가요?
          </p>
          <button
            onClick={() => router.push('/app/pro-upgrade')}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-semibold mr-4"
          >
            PRO 업그레이드 요청
          </button>
          <button
            onClick={async () => {
              try {
                const res = await supportAPI.createChat()
                setSelectedChat(res.data)
              } catch (error) {
                toast.error('상담 채팅 생성 실패')
              }
            }}
            className="px-6 py-3 bg-gray-600 hover:bg-gray-700 rounded-lg font-semibold"
          >
            일반 상담
          </button>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg flex flex-col h-[600px]">
          <div className="p-4 border-b border-gray-700">
            <h2 className="font-semibold">상담 채팅</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.is_admin ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs p-3 rounded-lg ${
                    msg.is_admin
                      ? 'bg-blue-600'
                      : 'bg-gray-700'
                  }`}
                >
                  <div className="text-sm">{msg.content}</div>
                  <div className="text-xs text-gray-400 mt-1">
                    {formatKSTTime(msg.created_at)}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          <div className="p-4 border-t border-gray-700 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="메시지 입력..."
              className="flex-1 px-4 py-2 bg-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSend}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 rounded"
            >
              전송
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
