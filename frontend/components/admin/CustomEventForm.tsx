'use client'

import { useState, useEffect } from 'react'
import { customEventsAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'
import { formatKSTDateTime } from '@/lib/utils/time'

const symbols = ['NQ1!', 'GOLD', 'CL1!', 'HSI1!', 'NVDA', 'AAPL', 'MSFT', 'TSLA', 'META', 'AMZN', 'GOOGL']

interface CustomEvent {
  id: number
  title: string
  event_date: string
  description: string | null
  target_symbol: string | null
  importance: string
  link: string | null
  is_active: boolean
}

const TIMEFRAMES = [
  { value: '1', label: '월봉', proOnly: false },
  { value: '1W', label: '주봉', proOnly: false },
  { value: '1D', label: '일봉', proOnly: false },
  { value: '1H', label: '60분봉', proOnly: false },
  { value: '30', label: '30분봉', proOnly: false },
  { value: '15', label: '15분봉', proOnly: false },
  { value: '5', label: '5분봉', proOnly: true },
  { value: '1', label: '1분봉', proOnly: true },
]

const IMPORTANCE_OPTIONS = [
  { value: 'low', label: '낮음' },
  { value: 'medium', label: '보통' },
  { value: 'high', label: '높음' },
  { value: 'critical', label: '매우 중요' },
]

const SYMBOL_OPTIONS = [
  { value: '', label: '전체' },
  { value: 'NQ1!', label: '나스닥선물' },
  { value: 'GOLD', label: '골드' },
  { value: 'CL1!', label: '원유' },
  { value: 'HSI1!', label: '항셍선물' },
  { value: 'NVDA', label: '엔비디아' },
  { value: 'AAPL', label: '애플' },
  { value: 'MSFT', label: '마이크로소프트' },
  { value: 'TSLA', label: '테슬라' },
  { value: 'META', label: '메타' },
  { value: 'AMZN', label: '아마존' },
  { value: 'GOOGL', label: '구글' },
]

function toUTC(isoString: string): string {
  if (!isoString) return ''
  try {
    const d = new Date(isoString)
    return d.toISOString()
  } catch {
    console.error('Invalid date format')
    return ''
  }
}

function formatDateTimeLocal(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day}T${h}:${min}`
}

export default function CustomEventForm() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState<'list' | 'create'>('list')
  const [events, setEvents] = useState<CustomEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [editingEvent, setEditingEvent] = useState<CustomEvent | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formData, setFormData] = useState({
    title: '',
    eventDate: '',
    hour: '0',
    minute: '0',
    description: '',
    targetSymbol: '',
    importance: 'high',
    link: '',
  })

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const summaryLines = {
    headline: '특별 이벤트',
    left: `총 ${events.length}건`,
    mid: activeTab === 'list' ? '이벤트 목록' : '새 이벤트 등록',
    right: '',
  }

  const eventList = events.map((event) => (
    <div
      key={event.id}
      className="bg-gray-800/50 rounded-xl p-4 border border-gray-700 hover:border-gray-600 transition-all"
    >
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-lg font-bold text-white">{event.title}</h3>
          <p className="text-sm text-gray-400">{event.description}</p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className={`px-3 py-1 rounded text-xs font-medium ${
            event.importance === 'critical' ? 'bg-red-500/20 text-red-400' :
            event.importance === 'high' ? 'bg-orange-500/20 text-orange-400' :
            'bg-gray-700 text-gray-300'
          }`}>
            <span className="text-gray-500 text-xs">
              {event.target_symbol || '전체'}
            </span>
          </span>
        </div>
      </div>
      <div className="flex justify-between items-center gap-4 mt-3">
        <span className="text-xs text-gray-500">
          {formatKSTDateTime(event.event_date)}
        </span>
        <button
          onClick={() => handleEdit(event)}
          className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg text-xs font-medium transition-all"
        >
          수정
        </button>
        <button
          onClick={() => handleDelete(event.id)}
          className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-medium transition-all"
        >
          삭제
        </button>
      </div>
    </div>
  ))

  // 이벤트 목록 불러오기
  useEffect(() => {
    if (activeTab === 'list' && String(user?.role).toLowerCase() === 'admin') {
      fetchEvents()
    }
  }, [activeTab, user])

  const fetchEvents = async () => {
    setLoading(true)
    try {
      const res = await customEventsAPI.getEvents()
      const list = Array.isArray(res.data) ? res.data : []
      setEvents(list)
    } catch (error) {
      console.error('Failed to fetch custom events:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.title.trim()) {
      toast.error('제목을 입력해주세요')
      return
    }

    if (!formData.eventDate) {
      toast.error('이벤트 날짜와 시간을 선택해주세요')
      return
    }

    // 중요도 검증
    const validImportance = ['critical', 'high', 'medium', 'low']
    if (!validImportance.includes(formData.importance)) {
      toast.error('중요도는 critical, high, medium, low 중 하나여 선택해야.')
      return
    }

    setIsSubmitting(true)
    try {
      const eventDateUTC = toUTC(formData.eventDate)
      
      const res = await customEventsAPI.createEvent({
        title: formData.title,
        event_date: eventDateUTC,
        description: formData.description,
        target_symbol: formData.targetSymbol,
        importance: formData.importance,
        link: formData.link,
      })

      toast.success('이벤트가 등록되었습니다')
      setFormData({
        title: '',
        eventDate: '',
        hour: '0',
        minute: '0',
        description: '',
        targetSymbol: '',
        importance: 'high',
        link: '',
      })
      await fetchEvents()
    } catch (error) {
      console.error('Failed to create custom event:', error)
      toast.error('이벤트 등록 실패했습니다.')
  } finally {
      setIsSubmitting(false)
    }
  }

  const handleEdit = (event: CustomEvent) => {
    setEditingEvent(event)
    setFormData({
      title: event.title,
      eventDate: formatDateTimeLocal(event.event_date),
      hour: '0',
      minute: '0',
      description: event.description || '',
      targetSymbol: event.target_symbol || '',
      importance: event.importance,
      link: event.link || '',
    })
  }

  const handleUpdate = async () => {
    if (!editingEvent) return

    setIsSubmitting(true)
    try {
      const eventDateUTC = toUTC(editingEvent.event_date)
      
      await customEventsAPI.updateEvent(editingEvent.id, {
        title: formData.title,
        event_date: eventDateUTC,
        description: formData.description,
        target_symbol: formData.targetSymbol,
        importance: formData.importance,
        link: formData.link,
      })

      toast.success('이벤트가 수정되었습니다')
      setEditingEvent(null)
      await fetchEvents()
    } catch (error) {
      console.error('Failed to update custom event:', error)
      toast.error('이벤트 수정 실패했습니다')
  } finally {
    setIsSubmitting(false)
  }
}

  const handleDelete = async (id: number) => {
    if (!confirm('정말 이 이벤트를 삭제하시겠습니까?')) return

    setIsSubmitting(true)
    try {
      await customEventsAPI.deleteEvent(id)
      toast.success('이벤트가 삭제되었습니다')
      await fetchEvents()
    } catch (error) {
      console.error('Failed to delete custom event:', error)
      toast.error('이벤트 삭제 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900/30 rounded-3xl border border-gray-800/50 overflow-hidden">
      {/* Header Area */}
      <div className="p-5 border-b border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold text-white">
            특별 이벤트 관리
          </h3>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveTab('list')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'list'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              이벤트 목록
            </button>
            <button
              onClick={() => setActiveTab('create')}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'create'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              새 이벤트
            </button>
          </div>
        </div>
      </div>

      {/* Content Area */}
      {activeTab === 'list' && (
        <div className="p-5">
          {/* Summary section */}
          <div className="flex justify-between items-center mb-6">
            <div className="text-xs text-gray-500">
              {summaryLines.headline}
            </div>
            <div className="text-xs text-gray-400">
              {summaryLines.left} · {summaryLines.mid} · {summaryLines.right}
            </div>
          </div>

          {/* Events List */}
          {events.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              등록된 특별 이벤트가 없습니다.
            </div>
          ) : (
            <div className="space-y-4">
              {eventList}
            </div>
          )}
        </div>
      )}

      {/* Create Tab */}
      {activeTab === 'create' && (
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              이벤트 제목 *
            </label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="예: 엔비디아 GTC 2024"
              required
            />
          </div>

          {/* Date and Time */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              이벤트 일시 (UTC) *
            </label>
            <div className="flex gap-3">
              <input
                type="datetime-local"
                name="eventDate"
                value={formData.eventDate}
                onChange={handleInputChange}
                className="flex-1 px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white focus:outline-none focus:border-blue-500"
                required
              />
              <div className="flex-1">
                <select
                  name="hour"
                  value={formData.hour}
                  onChange={handleInputChange}
                  className="w-20 px-3 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white focus:outline-none"
                >
                  <option value="">시간</option>
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i.toString()}>{i}</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <select
                  name="minute"
                  value={formData.minute}
                  onChange={handleInputChange}
                  className="w-20 px-3 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white focus:outline-none"
                >
                  <option value="">분</option>
                  {Array.from({ length: 60 }, (_, i) => (
                    <option key={i} value={i.toString().padStart(2, '0')}>{i.toString().padStart(2, '0')}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Symbol */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              관련 종목
            </label>
            <select
              name="targetSymbol"
              value={formData.targetSymbol}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">전체</option>
              {SYMBOL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Importance */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              중요도
            </label>
            <select
              name="importance"
              value={formData.importance}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white focus:outline-none focus:border-blue-500"
            >
              {IMPORTANCE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              설명
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              rows={3}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Link */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              관련 링크 (선택 사항)
            </label>
            <input
              type="text"
              name="link"
              value={formData.link}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Submit Button */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? '등록 중...' : '등록 이벤트'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}