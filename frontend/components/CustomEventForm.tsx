'use client'

import { useState, useEffect } from 'react'
import { customEventsAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import toast from 'react-hot-toast'
import { formatKSTDateTime } from '@/lib/utils/time'

const symbols = ['NQ1!', 'GOLD', 'CL1!', 'HSI1!', 'NVDA', 'AAPL', 'MSFT', 'TSLA', 'META', 'AMZN', 'GOOGL']

export default function CustomEventForm() {
  const { user } = useAuthStore()
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'list' | 'create'>('list')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [editingEvent, setEditingEvent] = useState<any | null>(null)
  const [formData, setFormData] = useState({
    title: '',
    event_date: '',
    description: '',
    target_symbol: '',
    importance: 'high',
    link: '',
  })

  const fetchEvents = async () => {
    try {
      const res = await customEventsAPI.getEvents()
      setEvents(res.data || [])
    } catch (error) {
      console.error('Failed to fetch events:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEvents()
  }, [])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleEdit = (event: any) => {
    setEditingEvent(event)
    setFormData({
      title: event.title,
      event_date: event.event_date.slice(0, 16),
      description: event.description || '',
      target_symbol: event.target_symbol || '',
      importance: event.importance,
      link: event.link || '',
    })
    setActiveTab('create')
  }

  const handleDelete = async (eventId: number) => {
    if (!confirm('정말 삭제하시겠습니까?')) return

    try {
      await customEventsAPI.deleteEvent(eventId)
      toast.success('이벤트가 삭제되었습니다.')
      await fetchEvents()
    } catch (error) {
      toast.error('삭제에 실패했습니다.')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.title.trim() || !formData.event_date) {
      setFormError('제목과 이벤트 날짜는 필수입니다.');
      return
    }

    setIsSubmitting(true)
    setFormError(null)

    try {
      if (editingEvent) {
        await customEventsAPI.updateEvent(editingEvent.id, formData)
        toast.success('이벤트가 수정되었습니다.')
        setEditingEvent(null)
      } else {
        await customEventsAPI.createEvent({
          title: formData.title.trim(),
          event_date: formData.event_date,
          description: formData.description || undefined,
          target_symbol: formData.target_symbol || undefined,
          importance: formData.importance || 'high',
          link: formData.link || undefined,
        })
        toast.success('이벤트가 등록되었습니다!')
      }

      setIsSubmitting(false)
      setFormData({
        title: '',
        event_date: '',
        description: '',
        target_symbol: '',
        importance: 'high',
        link: '',
      })
      setActiveTab('list')
      await fetchEvents()
    } catch (error: any) {
      console.error('이벤트 등록/수정 실패:', error)
      setFormError(error.response?.data?.detail || '등록에 실패했습니다.')
      setIsSubmitting(false)
    }
  }

  if (!user || String(user.role).toLowerCase() !== 'admin') {
    return (
      <div className="p-6 text-center text-gray-400">
        관리자 권한이 필요합니다.
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-white">특별 이벤트 관리</h2>
        <div className="flex gap-2">
          <button
            onClick={() => { setActiveTab('list'); setEditingEvent(null); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'list'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            이벤트 목록
          </button>
          <button
            onClick={() => setActiveTab('create')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'create'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            새 이벤트 등록
          </button>
        </div>
      </div>

      {/* Event List */}
      {activeTab === 'list' && (
        <div className="space-y-4">
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : events.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              등록된 이벤트가 없습니다.
            </div>
          ) : (
            <div className="space-y-4">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="bg-gray-800/50 rounded-xl p-4 border border-gray-700 hover:border-gray-600 transition-all"
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="text-lg font-bold text-white">{event.title}</h3>
                      <p className="text-sm text-gray-400">
                        {event.description || '설명 없음'}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 text-sm text-gray-400">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        event.importance === 'critical' ? 'bg-red-500/20 text-red-400' :
                        event.importance === 'high' ? 'bg-orange-500/20 text-orange-400' :
                        'bg-gray-700 text-gray-300'
                      }`}>
                        {event.importance}
                      </span>
                      {event.target_symbol && (
                        <span className="px-2 py-1 rounded bg-blue-500/20 text-blue-400 text-xs">
                          {event.target_symbol}
                        </span>
                      )}
                      <span className="text-gray-500 text-xs">
                        {formatKSTDateTime(event.event_date)}
                      </span>
                    </div>
                    <div className="flex gap-2 mt-3">
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
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Create/Edit Form */}
      {activeTab === 'create' && (
        <form onSubmit={handleSubmit} className="space-y-4">
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

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              이벤트 일시 (UTC) *
            </label>
            <input
              type="datetime-local"
              name="event_date"
              value={formData.event_date}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              설명 *
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              rows={3}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              관련 심볼 (선택)
            </label>
            <select
              name="target_symbol"
              value={formData.target_symbol}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white focus:outline-none focus:border-blue-500"
            >
              <option value="">전체</option>
              {symbols.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              중요도 *
            </label>
            <select
              name="importance"
              value={formData.importance}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white focus:outline-none focus:border-blue-500"
            >
              <option value="low">낮음</option>
              <option value="medium">보통</option>
              <option value="high">높음</option>
              <option value="critical">최상</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              참고 링크 *
            </label>
            <input
              type="url"
              name="link"
              value={formData.link}
              onChange={handleInputChange}
              className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
              placeholder="https://..."
            />
          </div>

          {formError && (
            <div className="text-red-400 text-sm">{formError}</div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? '처리 중...' : editingEvent ? '이벤트 수정' : '이벤트 등록'}
          </button>
        </form>
      )}
    </div>
  );
}
