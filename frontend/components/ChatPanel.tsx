'use client'

import { useState, useEffect, useRef } from 'react'
import { useAuthStore } from '@/lib/store'
import { aiAPI, chatAPI } from '@/lib/api'
import { ChatWebSocket } from '@/lib/websocket'
import { formatKSTTime, getNowISOString } from '@/lib/utils/time'
import { Crown, LockKeyhole } from 'lucide-react'

function UserBadge({ role }: { role?: string | null }) {
  const r = (role || '').toString().toLowerCase()
  const isMaster = r === 'admin' || r === 'master'
  const isPro = r === 'pro'

  if (isMaster) {
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded ml-2 bg-purple-600 text-white font-bold">
        MASTER
      </span>
    )
  }

  if (isPro) {
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded ml-2 bg-yellow-500 text-yellow-900 font-bold">
        PRO
      </span>
    )
  }

  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded ml-2 bg-gray-600 text-gray-200">
      BASIC
    </span>
  )
}

function ImageLightbox({ src, onClose }: { src: string; onClose: () => void }) {
  useEffect(() => {
    const onEscape = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [onClose])
  return (
    <div
      className="fixed inset-0 z-[100] bg-black/90 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <img
        src={src}
        alt="확대"
        className="max-w-full max-h-full object-contain rounded"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  )
}

interface ChatPanelProps {
  symbol: string
}

interface Message {
  id: number
  user_id: number | null
  username: string | null
  nickname: string | null
  content: string
  is_bot: boolean
  user_role?: string
  created_at: string
  is_private?: boolean
}

const IMAGE_PREFIX = '[IMAGE]:'
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png']
const isImageContent = (content: string) =>
  content.startsWith('data:image') || content.startsWith(IMAGE_PREFIX)
const getImageSrc = (content: string) =>
  content.startsWith(IMAGE_PREFIX) ? content.slice(IMAGE_PREFIX.length) : content

export default function ChatPanel({ symbol }: ChatPanelProps) {
  const { user, isPro } = useAuthStore()
  const [channels, setChannels] = useState<any[]>([])
  const [currentChannel, setCurrentChannel] = useState<any>({ id: 1, name: 'Global', symbol: null })
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [ws, setWs] = useState<ChatWebSocket | null>(null)
  const [loading, setLoading] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null)
  const [isProModalOpen, setIsProModalOpen] = useState(false)
  const [proModalCopy, setProModalCopy] = useState<{ title: string; body: string } | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pendingTempIdRef = useRef<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const canUploadImage = isPro() // Pro 또는 Admin만 이미지 업로드
  const canZoomImage = (msg: Message) => {
    const role = (msg.user_role || '').toString().toLowerCase()
    return role === 'pro' || role === 'admin' || role === 'master'
  }

  const getUserColor = (name: string) => {
    const colors = [
      'text-red-400', 'text-orange-400', 'text-amber-400', 'text-yellow-400',
      'text-lime-400', 'text-green-400', 'text-emerald-400', 'text-teal-400',
      'text-cyan-400', 'text-sky-400', 'text-blue-400', 'text-indigo-400',
      'text-violet-400', 'text-purple-400', 'text-fuchsia-400', 'text-pink-400',
      'text-rose-400'
    ]
    let hash = 0
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash)
    }
    return colors[Math.abs(hash) % colors.length]
  }

  useEffect(() => {
    // 채널 목록 가져오기
    chatAPI.getChannels()
      .then((res) => {
        setChannels(res.data)
        // Global 또는 해당 심볼 채널 찾기
        const channel = res.data.find(
          (ch: any) => ch.symbol === symbol || ch.name === 'Global'
        ) || res.data[0] || { id: 1, name: 'Global', symbol: null }
        setCurrentChannel(channel)
        setLoading(false)
      })
      .catch(() => {
        // API 실패 시 기본 채널 사용
        setCurrentChannel({ id: 1, name: 'Global', symbol: null })
        setLoading(false)
      })
  }, [symbol])

  useEffect(() => {
    if (!currentChannel || loading) return

    // 채팅 히스토리 로드 (최근 메시지 먼저)
    chatAPI.getMessages(currentChannel.id, 50)
      .then((res) => {
        const list = Array.isArray(res?.data) ? res.data : []
        setMessages(list)
      })
      .catch((err) => {
        console.warn('[Chat] Failed to load history:', err?.response?.status, err?.message)
        setMessages([])
      })

    // WebSocket 연결 시도 (실패해도 계속 진행)
    try {
      const websocket = new ChatWebSocket(currentChannel.id, (data) => {
        setMessages((prev) => {
          // 중복 체크 (강력하게)
          // 1. 같은 ID가 이미 있는 경우
          if (data.id && prev.some(m => m.id === data.id)) return prev

          // 2. 내 메시지인 경우: 임시 메시지와 내용이 같은 게 있으면 교체 또는 무시
          if (data.user_id === user?.id) {
            // 내용이 같고 시간이 최근(1분 이내)인 메시지 찾기
            const isLocalDuplicate = prev.some(m =>
              m.content === data.content &&
              m.user_id === data.user_id &&
              (m.id >= 1000000000000) // 임시 ID는 보통 타임스탬프(큰 숫자)
            )
            if (isLocalDuplicate) {
              // 임시 메시지 제거하고 서버 데이터로 교체
              return prev.map(m => (m.content === data.content && m.user_id === data.user_id && m.id >= 1000000000000) ? data : m)
            }
          }

          // 3. 내용과 닉네임이 같고 시간차가 적은 중복 메시지 방지
          const isContentDuplicate = prev.some(m =>
            m.content === data.content &&
            m.nickname === data.nickname &&
            Math.abs(new Date(m.created_at).getTime() - new Date(data.created_at).getTime()) < 60000 // 1분 이내 동일 내용 방지
          )
          if (isContentDuplicate) return prev

          return [...prev, data]
        })
      })
      websocket.connect()
      setWs(websocket)
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : String(error)
      console.error(`[Chat] WebSocket connection failed for channel ${currentChannel?.id} (${currentChannel?.name}). Fallback: send via REST. Error:`, msg)
    }

    return () => {
      if (ws) {
        ws.disconnect()
      }
    }
  }, [currentChannel, loading, user, symbol])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!isProModalOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsProModalOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isProModalOpen])

  const handleSend = async () => {
    if (!input.trim() || !currentChannel || isSending) return

    const messageContent = input.trim()
    setInput('')
    setIsSending(true)

    // @커맨드: 퍼블릭 전송 차단 -> 프라이빗 AI 응답만 내 화면에 추가
    if (messageContent.startsWith('@')) {
      // BASIC 유저: 퍼블릭 전송 차단 + 업그레이드 모달 유도
      if (!isPro()) {
        setProModalCopy({
          title: '나만의 AI 트레이딩 비서를 호출해보세요!',
          body: '@ 명령어를 통한 실시간 AI 질문 기능은 PRO 멤버십 전용입니다.',
        })
        setIsProModalOpen(true)
        setIsSending(false)
        return
      }

      const tempUserId = Date.now()
      const tempBotId = tempUserId + 1
      const eventTimestamp = getNowISOString()

      const firstToken = messageContent.slice(1).trim().split(/\s+/)[0]?.toLowerCase() || ''
      const command: 'briefing' | 'news' | 'ask' =
        firstToken === '브리핑' || firstToken === 'briefing' ? 'briefing' :
          firstToken === '뉴스' || firstToken === 'news' ? 'news' :
            'ask'

      const loadingText =
        command === 'news'
          ? 'AI가 뉴스를 분석 중입니다...'
          : command === 'briefing'
            ? 'AI가 브리핑을 생성 중입니다...'
            : 'AI가 답변을 생성 중입니다...'

      const myPrivateCommand: Message = {
        id: tempUserId,
        user_id: user?.id || null,
        username: user?.username || null,
        nickname: user?.nickname || null,
        content: messageContent,
        is_bot: false,
        user_role: user?.role,
        created_at: eventTimestamp,
        is_private: true,
      }

      const privateLoading: Message = {
        id: tempBotId,
        user_id: null,
        username: 'private_ai',
        nickname: 'AI 비서(개인)',
        content: loadingText,
        is_bot: true,
        user_role: 'pro',
        created_at: eventTimestamp,
        is_private: true,
      }

      setMessages((prev) => [...prev, myPrivateCommand, privateLoading])

      try {
        const res = await aiAPI.ask({ command, symbol, message: messageContent })
        const answer = String(res?.data?.answer || '').trim() || '답변을 생성하지 못했습니다.'
        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempBotId
              ? {
                  ...m,
                  content: answer,
                  created_at: getNowISOString(),
                }
              : m
          )
        )
      } catch (e) {
        console.error('Private AI ask failed:', e)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempBotId
              ? {
                  ...m,
                  content: 'AI 호출에 실패했습니다. 잠시 후 다시 시도해 주세요.',
                  created_at: getNowISOString(),
                }
              : m
          )
        )
      } finally {
        setIsSending(false)
      }
      return
    }

    // 이벤트 발생 시점의 정확한 시간 캡처 (UTC ISO - 백엔드 전송용)
    const eventTimestamp = getNowISOString()

    // 임시 메시지 ID (중복 방지용)
    const tempId = Date.now()
    pendingTempIdRef.current = tempId

    // 로컬에 즉시 메시지 추가 (낙관적 업데이트) - 이벤트 발생 시점의 시간 사용
    const tempMessage: Message = {
      id: tempId,
      user_id: user?.id || null,
      username: user?.username || null,
      nickname: user?.nickname || null,
      content: messageContent,
      is_bot: false,
      user_role: user?.role,
      created_at: eventTimestamp
    }

    // 중복 체크 후 추가 (더 강력한 중복 방지)
    setMessages((prev) => {
      // 같은 내용의 메시지가 최근 3초 이내에 있으면 추가하지 않음
      const recentSameMessage = prev.find(
        m => m.content === messageContent &&
          m.user_id === user?.id &&
          Math.abs(new Date(m.created_at).getTime() - tempId) < 3000
      )
      if (recentSameMessage) {
        return prev
      }
      return [...prev, tempMessage]
    })


    // WebSocket 또는 API로 한 번만 전송
    let messageSent = false
    try {
      if (ws && ws.ws && ws.ws.readyState === WebSocket.OPEN) {
        ws.send(messageContent, symbol)
        messageSent = true
        // WebSocket으로 보냈으면 서버 응답을 기다림 (임시 메시지는 서버 응답으로 교체됨)
      } else {
        // WebSocket이 없거나 연결되지 않았으면 API로 전송
        const response = await chatAPI.sendMessage(currentChannel.id, messageContent)
        messageSent = true
        // 서버에서 받은 메시지로 임시 메시지 교체
        if (response.data) {
          setMessages((prev) => {
            // 임시 메시지 제거하고 서버 메시지로 교체
            const filtered = prev.filter(m => m.id !== tempId)
            pendingTempIdRef.current = null
            // 중복 체크
            const isDuplicate = filtered.some(m => m.id === response.data.id)
            if (isDuplicate) {
              return filtered
            }
            return [...filtered, response.data]
          })
        }
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      // 에러 시 임시 메시지 제거
      setMessages((prev) => {
        pendingTempIdRef.current = null
        return prev.filter(m => m.id !== tempId)
      })
    } finally {
      setIsSending(false)
    }
  }

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !ALLOWED_IMAGE_TYPES.includes(file.type) || !currentChannel || isSending) return
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = String(reader.result)
      if (dataUrl.length > 500 * 1024) return // 500KB 제한
      const contentToSend = IMAGE_PREFIX + dataUrl
      setInput('')
      setIsSending(true)
      const tempId = Date.now()
      pendingTempIdRef.current = tempId
      const tempMessage: Message = {
        id: tempId,
        user_id: user?.id || null,
        username: user?.username || null,
        nickname: user?.nickname || null,
        content: contentToSend,
        is_bot: false,
        user_role: user?.role,
        created_at: getNowISOString()
      }
      setMessages((prev) => [...prev, tempMessage])
      if (ws?.ws?.readyState === WebSocket.OPEN) {
        ws.send(contentToSend)
        setTimeout(() => setIsSending(false), 500)
      } else {
        chatAPI.sendMessage(currentChannel.id, contentToSend)
          .then((res) => res.data && setMessages((prev) => prev.map(m => m.id === tempId ? res.data : m)))
          .catch(() => setMessages((prev) => prev.filter(m => m.id !== tempId)))
          .finally(() => setIsSending(false))
      }
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-3 bg-gray-700 border-b border-gray-600">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-green-600 text-xs rounded font-semibold">LIVE</span>
            <div className="font-semibold text-sm">유저들 실시간 채팅</div>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-gray-400 text-sm">로딩 중...</div>
        </div>
        <div className="p-2 border-t border-gray-600">
          <input
            type="text"
            disabled
            placeholder="채팅입력하기"
            className="w-full px-3 py-2 bg-gray-700 rounded text-sm opacity-50"
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 bg-gray-700 border-b border-gray-600">
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-green-600 text-xs rounded font-semibold">LIVE</span>
          <div className="font-semibold text-sm">유저들 실시간 채팅</div>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {messages.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-4">메시지가 없습니다</div>
        ) : (
          messages.map((msg) => {
            const isOwnMessage = msg.user_id === user?.id
            return (
              <div
                key={msg.id}
                className={`flex ${isOwnMessage ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[90%] ${isOwnMessage ? 'order-2' : 'order-1'}`}>
                  {msg.is_private && (
                    <div className="px-1 mb-1">
                      <span className="inline-block text-[10px] px-2 py-1 rounded bg-violet-500/10 text-violet-200 border border-violet-500/20">
                        🔒 나에게만 보이는 AI 답변입니다
                      </span>
                    </div>
                  )}
                  {!isOwnMessage && (
                    <div className="flex items-center gap-1.5 mb-1 px-1">

                      <span className={`font-black text-[13px] ${getUserColor(msg.nickname || msg.username || '익명')}`}>
                        {msg.nickname || msg.username || '익명'}
                      </span>
                      <UserBadge role={msg.user_role} />
                      <span className="text-[10px] text-gray-500 ml-auto tabular-nums">
                        {(() => {
                          try {
                            return formatKSTTime(msg.created_at)
                          } catch { return '' }
                        })()}
                      </span>
                    </div>
                  )}
                  <div
                    className={`rounded-xl px-3 py-1.5 text-sm leading-relaxed shadow-sm ${
                      msg.is_private
                        ? 'bg-violet-900/40 text-violet-50 border border-violet-500/20'
                        : isOwnMessage
                          ? 'bg-blue-600 text-white rounded-tr-none'
                          : 'bg-gray-800/80 text-gray-100 border border-gray-700/50 rounded-tl-none'
                    }`}
                  >
                    {isImageContent(msg.content) ? (
                      canZoomImage(msg) ? (
                        <button
                          type="button"
                          onClick={() => setLightboxSrc(getImageSrc(msg.content))}
                          className="block text-left"
                        >
                          <img src={getImageSrc(msg.content)} alt="채팅 이미지" className="max-w-[240px] max-h-[200px] rounded object-contain cursor-zoom-in hover:opacity-90" />
                        </button>
                      ) : (
                        <img src={getImageSrc(msg.content)} alt="채팅 이미지" className="max-w-[240px] max-h-[200px] rounded object-contain" />
                      )
                    ) : (
                      msg.content
                    )}
                  </div>
                  {isOwnMessage && (
                    <div className="flex items-center gap-2 mt-1 justify-end px-1">
                      <span className="text-[9px] text-gray-500 tabular-nums">
                        {(() => {
                          try {
                            return formatKSTTime(msg.created_at)
                          } catch { return '' }
                        })()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
        <div ref={messagesEndRef} />
      </div>
      {lightboxSrc && (
        <ImageLightbox src={lightboxSrc} onClose={() => setLightboxSrc(null)} />
      )}

      {/* PRO Upgrade Modal (AI 비서 전용 카피 지원) */}
      {isProModalOpen && (
        <div
          className="fixed inset-0 z-[120] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
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
                {proModalCopy?.title || 'PRO 멤버십이 필요합니다'}
              </div>
              <div className="mt-2 text-sm text-gray-400 leading-relaxed">
                {proModalCopy?.body || '이 기능은 PRO 전용입니다. 업그레이드하고 모든 기능을 사용해 보세요.'}
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
              <a
                href="/app/pro-upgrade"
                onClick={() => setIsProModalOpen(false)}
                className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-500 text-gray-950 font-black hover:from-amber-400 hover:to-yellow-400 transition shadow-lg shadow-amber-500/20 text-center"
              >
                PRO 알아보기
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="p-2 border-t border-gray-600 flex gap-2 items-center">
        {canUploadImage && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png"
              className="hidden"
              onChange={handleImageSelect}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isSending}
              className="text-gray-400 hover:text-white p-1 disabled:opacity-50"
              title="이미지 올리기 (JPG, PNG) - PRO/관리자"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </button>
          </>
        )}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="메시지를 입력하거나, @를 눌러 AI 비서를 호출해보세요."
          className="flex-1 px-3 py-2 bg-gray-700 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim()}
          className="p-2 bg-blue-600 hover:bg-blue-700 rounded disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </button>
      </div>
    </div>
  )
}
