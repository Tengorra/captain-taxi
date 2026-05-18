import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import {
  Phone, PhoneCall, PhoneForwarded, AlertTriangle, Check,
  User, Bot, Wrench, Radio, X, RefreshCw,
} from 'lucide-react'
import clsx from 'clsx'
import { formatDistanceToNow } from 'date-fns'
import { api, callsStreamUrl } from '../lib/api'
import { BotCallEvent, BotCallEventType, BotCallSummary } from '../types'

// ── Event styling ──────────────────────────────────────────────────────────

const EVENT_META: Record<
  BotCallEventType,
  { label: string; icon: typeof Phone; color: string; bg: string }
> = {
  call_started:         { label: 'Call started',        icon: PhoneCall,        color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  user_message:         { label: 'Caller',              icon: User,             color: 'text-blue-300',    bg: 'bg-blue-500/10' },
  assistant_message:    { label: 'Bot',                 icon: Bot,              color: 'text-amber-300',   bg: 'bg-amber-500/10' },
  tool_call:            { label: 'Tool call',           icon: Wrench,           color: 'text-purple-300',  bg: 'bg-purple-500/10' },
  tool_result:          { label: 'Tool result',         icon: Check,            color: 'text-emerald-300', bg: 'bg-emerald-500/10' },
  tool_error:           { label: 'Tool error',          icon: AlertTriangle,    color: 'text-red-300',     bg: 'bg-red-500/10' },
  tool_unknown:         { label: 'Unknown tool',        icon: AlertTriangle,    color: 'text-orange-300',  bg: 'bg-orange-500/10' },
  trip_booked:          { label: 'Trip booked',         icon: Check,            color: 'text-emerald-300', bg: 'bg-emerald-500/10' },
  transferred_to_human: { label: 'Transferred',         icon: PhoneForwarded,   color: 'text-cyan-300',    bg: 'bg-cyan-500/10' },
  auto_transfer:        { label: 'Auto-transferred',    icon: PhoneForwarded,   color: 'text-cyan-300',    bg: 'bg-cyan-500/10' },
  manual_transfer:      { label: 'Manual transfer',     icon: PhoneForwarded,   color: 'text-cyan-300',    bg: 'bg-cyan-500/10' },
  call_ended:           { label: 'Call ended',          icon: X,                color: 'text-gray-400',    bg: 'bg-gray-700/40' },
  unknown_event:        { label: 'Unknown event',       icon: Radio,            color: 'text-gray-400',    bg: 'bg-gray-700/40' },
  ping:                 { label: 'ping',                icon: Radio,            color: 'text-gray-600',    bg: 'bg-transparent' },
}

const TRANSFER_EVENTS: BotCallEventType[] = [
  'transferred_to_human', 'auto_transfer', 'manual_transfer',
]

// ── Helpers ────────────────────────────────────────────────────────────────

function summariseCall(events: BotCallEvent[]): BotCallSummary {
  const callId = events[0]?.call_id ?? 'unknown'
  let started: number | undefined
  let ended: number | undefined
  let from: string | undefined
  let tripId: string | undefined
  let transferred = false
  let last = events[events.length - 1]

  for (const e of events) {
    if (e.event === 'call_started') {
      started = e.ts
      from = (e.data?.from as string | undefined) ?? from
    }
    if (e.event === 'call_ended') ended = e.ts
    if (e.event === 'trip_booked')
      tripId = (e.data?.trip_id as string | undefined) ?? tripId
    if (TRANSFER_EVENTS.includes(e.event)) transferred = true
  }

  return {
    call_id: callId,
    from,
    started_at: started,
    ended_at: ended,
    trip_id: tripId,
    transferred,
    last_event: last?.event ?? 'unknown_event',
    last_ts: last?.ts ?? 0,
    event_count: events.length,
  }
}

function extractText(e: BotCallEvent): string {
  const d = e.data || {}
  if (typeof d.text === 'string') return d.text
  if (e.event === 'tool_call')
    return `${d.tool ?? '?'}(${JSON.stringify(d.args ?? {})})`
  if (e.event === 'tool_result')
    return `${d.tool ?? '?'} → ${JSON.stringify(d.result ?? {})}`
  if (e.event === 'tool_error')
    return `${d.tool ?? '?'} failed: ${d.error ?? ''} (${d.consecutive_failures ?? 1} consecutive)`
  if (e.event === 'trip_booked')
    return `trip ${(d.trip_id as string | undefined)?.slice(0, 8) ?? '?'} in ${d.city ?? '?'}`
  if (TRANSFER_EVENTS.includes(e.event))
    return `→ ${d.to ?? '?'} (${d.reason ?? ''})`
  if (e.event === 'call_ended')
    return d.summary ? String(d.summary) : `duration ${d.duration_s ?? '?'}s`
  return JSON.stringify(d)
}

function fmtTs(ts?: number): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleTimeString()
}

function callIsLive(c: BotCallSummary): boolean {
  return !c.ended_at && !c.transferred
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function LiveCalls() {
  const [eventsByCall, setEventsByCall] = useState<Record<string, BotCallEvent[]>>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<number | null>(null)

  // ── WebSocket: subscribe to all calls ─────────────────────────────────────
  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return
    let ws: WebSocket
    try {
      ws = new WebSocket(callsStreamUrl())
    } catch (e) {
      setError(`Could not open WebSocket: ${(e as Error).message}`)
      return
    }
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }
    ws.onerror = () => setError('WebSocket error — retrying…')
    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      reconnectTimer.current = window.setTimeout(connect, 3000)
    }
    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as BotCallEvent | { event: 'ping' }
        if ((event as BotCallEvent).event === 'ping') return
        const e = event as BotCallEvent
        if (!e.call_id) return
        setEventsByCall((prev) => {
          const existing = prev[e.call_id] ?? []
          // Drop exact duplicates (history replay overlap on reconnect).
          if (existing.some((x) => x.ts === e.ts && x.event === e.event)) return prev
          return { ...prev, [e.call_id]: [...existing, e] }
        })
      } catch {
        /* ignore malformed frames */
      }
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  // ── Derived state ─────────────────────────────────────────────────────────
  const calls: BotCallSummary[] = useMemo(() => {
    return Object.values(eventsByCall)
      .map(summariseCall)
      .sort((a, b) => (b.started_at ?? b.last_ts) - (a.started_at ?? a.last_ts))
  }, [eventsByCall])

  // Auto-select the newest live call when nothing is selected.
  useEffect(() => {
    if (selectedId) return
    const live = calls.find(callIsLive) ?? calls[0]
    if (live) setSelectedId(live.call_id)
  }, [calls, selectedId])

  const selected = selectedId ? eventsByCall[selectedId] ?? [] : []
  const selectedSummary = selectedId ? calls.find((c) => c.call_id === selectedId) ?? null : null

  // ── Manual transfer ──────────────────────────────────────────────────────
  const [transferring, setTransferring] = useState(false)
  const [transferMsg, setTransferMsg] = useState<string | null>(null)

  const transfer = async () => {
    if (!selectedSummary) return
    const sid = window.prompt(
      'Twilio CallSid to transfer (visible in ElevenLabs/Twilio call console):',
    )
    if (!sid) return
    const city = window.prompt('City (saskatoon | regina):', 'saskatoon') ?? 'saskatoon'
    setTransferring(true)
    setTransferMsg(null)
    try {
      await api.transferCall(selectedSummary.call_id, {
        twilio_call_sid: sid,
        city,
        reason: 'manual transfer from dashboard',
      })
      setTransferMsg('Transfer requested')
    } catch (e) {
      setTransferMsg(`Failed: ${(e as Error).message}`)
    } finally {
      setTransferring(false)
    }
  }

  const reload = async () => {
    if (!selectedId) return
    try {
      const { events } = await api.callHistory(selectedId)
      setEventsByCall((prev) => ({ ...prev, [selectedId]: events }))
    } catch {
      /* the call may not exist server-side anymore */
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <PhoneCall size={20} className="text-amber-400" />
            Live Calls
          </h1>
          <p className="text-sm text-gray-500">
            ElevenLabs voice dispatcher — events stream as the call happens.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={clsx(
              'inline-flex items-center gap-1.5 px-2 py-1 rounded-md border',
              connected
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : 'bg-red-500/10 text-red-300 border-red-500/30',
            )}
          >
            <span
              className={clsx(
                'w-1.5 h-1.5 rounded-full',
                connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400',
              )}
            />
            {connected ? 'streaming' : 'disconnected'}
          </span>
          {error && <span className="text-red-400">{error}</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* ── Calls list ───────────────────────────────────────────────── */}
        <div className="card p-0 overflow-hidden lg:col-span-1">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-200">
              Recent calls ({calls.length})
            </h2>
            {calls.length > 0 && (
              <button
                className="btn-ghost text-xs text-gray-400 hover:text-gray-200"
                onClick={() => {
                  setEventsByCall({})
                  setSelectedId(null)
                }}
              >
                clear
              </button>
            )}
          </div>
          {calls.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-gray-500">
              <Phone className="mx-auto mb-2 text-gray-700" size={28} />
              Waiting for the next call…
            </div>
          ) : (
            <ul className="divide-y divide-gray-800 max-h-[70vh] overflow-y-auto">
              {calls.map((c) => {
                const live = callIsLive(c)
                const meta = EVENT_META[c.last_event] ?? EVENT_META.unknown_event
                return (
                  <li key={c.call_id}>
                    <button
                      onClick={() => setSelectedId(c.call_id)}
                      className={clsx(
                        'w-full text-left px-4 py-3 hover:bg-gray-800 transition-colors',
                        selectedId === c.call_id && 'bg-gray-800',
                      )}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs text-gray-400">
                          {c.call_id.slice(0, 12)}…
                        </span>
                        {live ? (
                          <span className="badge bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                            LIVE
                          </span>
                        ) : c.transferred ? (
                          <span className="badge bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                            TRANSFERRED
                          </span>
                        ) : (
                          <span className="badge bg-gray-700/40 text-gray-400 border border-gray-700">
                            ENDED
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-200">
                        {c.from ?? 'unknown caller'}
                      </div>
                      <div className="flex items-center justify-between mt-1 text-xs text-gray-500">
                        <span className={meta.color}>{meta.label}</span>
                        <span>
                          {c.last_ts
                            ? formatDistanceToNow(new Date(c.last_ts * 1000), { addSuffix: true })
                            : ''}
                        </span>
                      </div>
                      {c.trip_id && (
                        <div className="mt-1 text-xs text-emerald-400">
                          trip {c.trip_id.slice(0, 8)}…
                        </div>
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* ── Event log for selected call ─────────────────────────────── */}
        <div className="card p-0 overflow-hidden lg:col-span-2">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-200">
                {selectedSummary?.from ?? 'Select a call'}
              </h2>
              {selectedSummary && (
                <p className="text-xs text-gray-500 font-mono">
                  {selectedSummary.call_id}
                </p>
              )}
            </div>
            {selectedSummary && (
              <div className="flex items-center gap-2">
                <button
                  className="btn-ghost text-xs flex items-center gap-1 px-2 py-1 rounded-md border border-gray-700 hover:bg-gray-800"
                  onClick={reload}
                  title="Refetch history for this call"
                >
                  <RefreshCw size={12} /> reload
                </button>
                <button
                  className={clsx(
                    'text-xs flex items-center gap-1 px-2 py-1 rounded-md border',
                    'border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10',
                    transferring && 'opacity-50 cursor-not-allowed',
                  )}
                  disabled={transferring}
                  onClick={transfer}
                  title="Warm-transfer this call to a human dispatcher"
                >
                  <PhoneForwarded size={12} />
                  {transferring ? 'transferring…' : 'transfer to human'}
                </button>
              </div>
            )}
          </div>

          {!selectedSummary ? (
            <div className="px-4 py-16 text-center text-sm text-gray-500">
              Pick a call on the left to see its live event stream.
            </div>
          ) : (
            <>
              <div className="px-4 py-2 border-b border-gray-800 grid grid-cols-3 gap-3 text-xs">
                <div>
                  <p className="text-gray-500">Started</p>
                  <p className="text-gray-200">{fmtTs(selectedSummary.started_at)}</p>
                </div>
                <div>
                  <p className="text-gray-500">Ended</p>
                  <p className="text-gray-200">{fmtTs(selectedSummary.ended_at)}</p>
                </div>
                <div>
                  <p className="text-gray-500">Trip</p>
                  <p className="text-gray-200">
                    {selectedSummary.trip_id ? selectedSummary.trip_id.slice(0, 8) + '…' : '—'}
                  </p>
                </div>
              </div>
              {transferMsg && (
                <div className="px-4 py-2 text-xs bg-gray-800/40 text-gray-300 border-b border-gray-800">
                  {transferMsg}
                </div>
              )}
              <EventLog events={selected} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Event log ──────────────────────────────────────────────────────────────

function EventLog({ events }: { events: BotCallEvent[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [events.length])

  if (events.length === 0) {
    return (
      <div className="px-4 py-12 text-center text-sm text-gray-500">
        No events yet for this call.
      </div>
    )
  }

  return (
    <div ref={ref} className="max-h-[60vh] overflow-y-auto px-4 py-3 space-y-2">
      {events.map((e, i) => {
        const meta = EVENT_META[e.event] ?? EVENT_META.unknown_event
        const Icon = meta.icon
        return (
          <div
            key={`${e.ts}-${i}`}
            className={clsx(
              'rounded-md border border-gray-800 px-3 py-2 flex gap-3 items-start',
              meta.bg,
            )}
          >
            <Icon size={14} className={clsx(meta.color, 'mt-0.5 flex-shrink-0')} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 text-xs mb-0.5">
                <span className={clsx('font-medium', meta.color)}>{meta.label}</span>
                <span className="text-gray-600">{fmtTs(e.ts)}</span>
              </div>
              <div className="text-sm text-gray-200 break-words whitespace-pre-wrap">
                {extractText(e)}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
