import { Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { Escalation } from '../types'
import clsx from 'clsx'

interface Props {
  escalation: Escalation
  onApprove?: (id: number) => void
  onDeny?: (id: number) => void
  loading?: boolean
}

export default function EscalationCard({ escalation, onApprove, onDeny, loading }: Props) {
  const isPending = escalation.status === 'pending'

  return (
    <div className={clsx(
      'card border-l-4',
      isPending ? 'border-l-amber-500' : escalation.status === 'approved'
        ? 'border-l-emerald-500' : 'border-l-red-500'
    )}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={14} className="text-amber-400 flex-shrink-0" />
            <span className="text-xs text-gray-500 uppercase tracking-wide font-medium">
              {escalation.source_agent}
            </span>
            <span className={clsx('badge ml-auto', {
              'bg-amber-500/10 text-amber-400 border border-amber-500/20': isPending,
              'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20': escalation.status === 'approved',
              'bg-red-500/10 text-red-400 border border-red-500/20': escalation.status === 'denied',
              'bg-gray-700 text-gray-400': escalation.status === 'expired',
            })}>
              {escalation.status}
            </span>
          </div>
          <p className="font-semibold text-white text-sm mb-1">{escalation.title}</p>
          <p className="text-sm text-gray-400">{escalation.description}</p>
          {escalation.decision_note && (
            <p className="text-xs text-gray-500 mt-1 italic">Note: {escalation.decision_note}</p>
          )}
          <p className="text-xs text-gray-600 mt-2 flex items-center gap-1">
            <Clock size={11} />
            {formatDistanceToNow(new Date(escalation.created_at), { addSuffix: true })}
            {escalation.expires_at && isPending && (
              <span className="text-amber-600 ml-2">
                · expires {formatDistanceToNow(new Date(escalation.expires_at), { addSuffix: true })}
              </span>
            )}
          </p>
        </div>
      </div>

      {isPending && onApprove && onDeny && (
        <div className="flex gap-2 mt-4">
          <button
            className="btn-success flex-1"
            onClick={() => onApprove(escalation.id)}
            disabled={loading}
          >
            <CheckCircle size={15} /> Approve
          </button>
          <button
            className="btn-danger flex-1"
            onClick={() => onDeny(escalation.id)}
            disabled={loading}
          >
            <XCircle size={15} /> Deny
          </button>
        </div>
      )}
    </div>
  )
}
