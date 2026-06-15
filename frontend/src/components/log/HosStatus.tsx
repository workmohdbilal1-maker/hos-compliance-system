import { AlertTriangle, CheckCircle, Clock, Fuel } from 'lucide-react'
import type { HOSStatus } from '../../types/trip'

interface HosStatusProps {
  status: HOSStatus
}

function ProgressBar({
  label,
  used,
  total,
  unit = 'hrs',
  color = 'bg-primary-500',
}: {
  label: string
  used: number
  total: number
  unit?: string
  color?: string
}) {
  const remaining = Math.max(0, total - used)
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0
  const warningLevel = pct > 90 ? 'text-red-600' : pct > 75 ? 'text-amber-600' : 'text-gray-700'

  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-sm font-medium text-gray-600">{label}</span>
        <span className={`text-sm font-bold ${warningLevel}`}>
          {remaining.toFixed(1)} {unit} left
        </span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all ${
            pct > 90 ? 'bg-red-500' : pct > 75 ? 'bg-amber-500' : color
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-400 mt-0.5">
        {used.toFixed(1)} / {total.toFixed(0)} {unit} used
      </p>
    </div>
  )
}

export default function HosStatus({ status }: HosStatusProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">HOS Status</h3>
        {status.can_drive ? (
          <span className="flex items-center text-sm text-green-600 font-medium">
            <CheckCircle className="h-4 w-4 mr-1" />
            Can Drive
          </span>
        ) : (
          <span className="flex items-center text-sm text-red-600 font-medium">
            <AlertTriangle className="h-4 w-4 mr-1" />
            Cannot Drive
          </span>
        )}
      </div>

      <div className="space-y-4">
        <ProgressBar
          label="Driving Time (11hr limit)"
          used={Number(status.driving_hours_used || 0)}
          total={11}
          color="bg-green-500"
        />
        <ProgressBar
          label="Duty Window (14hr limit)"
          used={Number(status.window_hours_used || 0)}
          total={14}
          color="bg-blue-500"
        />
        <ProgressBar
          label={`Cycle (${status.cycle_type === '70_8' ? '70hr/8day' : '60hr/7day'})`}
          used={Number(status.cycle_hours_used || 0)}
          total={status.cycle_type === '70_8' ? 70 : 60}
          color="bg-purple-500"
        />

        {/* 30-min break status */}
        <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50">
          <div className="flex items-center space-x-2">
            <Clock className="h-4 w-4 text-gray-500" />
            <span className="text-sm text-gray-600">30-Min Break</span>
          </div>
          <span
            className={`text-sm font-medium ${
              status.break_required ? 'text-red-600' : 'text-green-600'
            }`}
          >
            {status.break_required
              ? 'Break Required!'
              : `${(8 - Number(status.break_hours_driving_since_last || 0)).toFixed(1)}h until required`}
          </span>
        </div>
      </div>

      {/* Violations */}
      {status.violations.length > 0 && (
        <div className="mt-4 space-y-2">
          <h4 className="text-sm font-semibold text-red-700">Violations</h4>
          {status.violations.map((v, i) => (
            <div
              key={i}
              className="flex items-start space-x-2 text-sm text-red-600 bg-red-50 p-2 rounded"
            >
              <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>{v.description}</span>
            </div>
          ))}
        </div>
      )}

      {/* Explanations */}
      {status.explanations.length > 0 && (
        <div className="mt-4 pt-3 border-t border-gray-200">
          <p className="text-xs font-medium text-gray-500 mb-1">Rule Explanations</p>
          {status.explanations.map((exp, i) => (
            <p key={i} className="text-xs text-gray-400">
              {exp}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
