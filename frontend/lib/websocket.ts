import { authAPI } from './api'

const RAW_WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

/** /ws 중복 방지: base가 이미 /ws로 끝나면 제거 후 한 번만 붙임 */
function getWebSocketBaseUrl(): string {
  const base = RAW_WS_BASE.replace(/\/ws\/?$/i, '').replace(/\/+$/, '')
  return base
}

export class ChatWebSocket {
  public ws: WebSocket | null = null
  private channelId: number
  private onMessage: (data: any) => void
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5

  constructor(channelId: number, onMessage: (data: any) => void) {
    this.channelId = channelId
    this.onMessage = onMessage
  }

  connect() {
    const token = localStorage.getItem('token')
    if (!token) {
      console.error('[WS] No token available for WebSocket connection')
      return
    }

    const base = getWebSocketBaseUrl()
    const wsUrl = `${base}/ws/chat/${this.channelId}?token=${token}`
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log(`[WS] Connected to channel ${this.channelId} (${wsUrl})`)
      this.reconnectAttempts = 0
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'news') {
          window.dispatchEvent(new CustomEvent('news_update', { detail: data }))
        } else {
          this.onMessage(data)
        }
      } catch (error) {
        console.error('[WS] Error parsing WebSocket message:', error)
      }
    }

    this.ws.onerror = () => {
      const reason = this.ws?.readyState !== undefined
        ? `readyState=${this.ws.readyState} (0=CONNECTING,1=OPEN,2=CLOSING,3=CLOSED)`
        : 'unknown'
      console.error(`[WS] Connection error url=${wsUrl} ${reason}. Check CORS, 403, or wrong path (e.g. /ws/ws/chat).`)
    }

    this.ws.onclose = (event) => {
      const code = event.code
      const reason = event.reason || ''
      const clean = event.wasClean ? 'clean' : 'unclean'
      console.warn(`[WS] Closed channel=${this.channelId} code=${code} reason=${reason} ${clean} url=${wsUrl}`)
      if (code === 1006) console.warn('[WS] 1006=abnormal closure (often 403/CORS or network).')
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++
        setTimeout(() => this.connect(), 1000 * this.reconnectAttempts)
      }
    }
  }

  send(content: string, symbol?: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ content, symbol: symbol ?? undefined }))
    } else {
      console.error('WebSocket is not connected')
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}
