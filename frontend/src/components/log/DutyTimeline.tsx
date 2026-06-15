import type { DutyStatusEntry } from '../../types/trip'

const STATUS_COLORS: Record<string, string> = {
  off_duty: '#9CA3AF',
  sleeper_berth: '#3B82F6',
  driving: '#10B981',
  on_duty_not_driving: '#F59E0B',
}

const STATUS_LABELS: Record<string, string> = {
  off_duty: 'Off Duty',
  sleeper_berth: 'Sleeper Berth',
  driving: 'Driving',
  on_duty_not_driving: 'On Duty (Not Driving)',
}

const HOURS = Array.from({ length: 25 }, (_, i) => i)

interface DutyTimelineProps {
  entries: DutyStatusEntry[]
  date: string
  totals?: {
    driving_hours: number
    on_duty_hours: number
    off_duty_hours: number
    sleeper_hours: number
  }
}

export default function DutyTimeline({ entries, date, totals }: DutyTimelineProps) {
  const dateObj = new Date(date + 'T00:00:00')
  const dayStart = dateObj.getTime()

  const getTimePosition = (timeStr: string): number => {
    const time = new Date(timeStr)
    const hoursFromStart = (time.getTime() - dayStart) / (1000 * 60 * 60)
    return Math.max(0, Math.min(24, hoursFromStart))
  }

  const statusRows = [
    'off_duty',
    'sleeper_berth',
    'driving',
    'on_duty_not_driving',
  ] as const

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900">
          {dateObj.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
            year: 'numeric',
          })}
        </h3>
        {totals && (
          <div className="flex items-center space-x-3 text-xs">
            <span className="px-2 py-1 rounded" style={{ backgroundColor: '#10B98133' }}>
              Drive: {Number(totals.driving_hours || 0).toFixed(1)}h
            </span>
            <span className="px-2 py-1 rounded" style={{ backgroundColor: '#F59E0B33' }}>
              On Duty: {Number(totals.on_duty_hours || 0).toFixed(1)}h
            </span>
            <span className="px-2 py-1 rounded" style={{ backgroundColor: '#9CA3AF33' }}>
              Off: {Number(totals.off_duty_hours || 0).toFixed(1)}h
            </span>
            <span className="px-2 py-1 rounded" style={{ backgroundColor: '#3B82F633' }}>
              Sleeper: {Number(totals.sleeper_hours || 0).toFixed(1)}h
            </span>
          </div>
        )}
      </div>

      {/* Hour labels */}
      <div className="relative ml-32">
        <div className="flex">
          {HOURS.map((h) => (
            <div
              key={h}
              className="text-xs text-gray-400 text-center"
              style={{ width: `${100 / 24}%`, marginLeft: h === 0 ? 0 : undefined }}
            >
              {h === 0 ? 'M' : h === 12 ? 'N' : h < 12 ? h : h - 12}
            </div>
          ))}
        </div>
      </div>

      {/* Grid rows */}
      <div className="space-y-0">
        {statusRows.map((status) => (
          <div key={status} className="flex items-center">
            <div className="w-32 pr-2 text-xs text-gray-600 text-right flex-shrink-0">
              {STATUS_LABELS[status]}
            </div>
            <div className="flex-1 relative h-8 bg-gray-50 border border-gray-200">
              {/* Hour grid lines */}
              {HOURS.map((h) => (
                <div
                  key={h}
                  className="absolute top-0 bottom-0 border-l border-gray-200"
                  style={{ left: `${(h / 24) * 100}%` }}
                />
              ))}

              {/* Duty status bars */}
              {entries
                .filter((e) => e.status === status)
                .map((entry, idx) => {
                  const start = getTimePosition(entry.start_time)
                  const end = entry.end_time ? getTimePosition(entry.end_time) : start
                  const width = end - start
                  if (width <= 0) return null

                  return (
                    <div
                      key={idx}
                      className="absolute top-1 bottom-1 rounded-sm opacity-90 hover:opacity-100 transition-opacity cursor-pointer"
                      style={{
                        left: `${(start / 24) * 100}%`,
                        width: `${(width / 24) * 100}%`,
                        backgroundColor: STATUS_COLORS[status],
                      }}
                      title={`${entry.remarks || status}: ${new Date(entry.start_time).toLocaleTimeString()} - ${entry.end_time ? new Date(entry.end_time).toLocaleTimeString() : '...'}`}
                    />
                  )
                })}
            </div>
            <div className="w-12 pl-2 text-xs text-gray-600 text-right flex-shrink-0">
              {totals
                ? Number(status === 'driving'
                    ? totals.driving_hours
                    : status === 'on_duty_not_driving'
                      ? totals.on_duty_hours
                      : status === 'off_duty'
                        ? totals.off_duty_hours
                        : totals.sleeper_hours
                  || 0).toFixed(1)
                : ''}
            </div>
          </div>
        ))}
      </div>

      {/* Remarks */}
      {entries.some((e) => e.location) && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <p className="text-xs font-medium text-gray-500 mb-1">Remarks</p>
          <div className="flex flex-wrap gap-1">
            {entries
              .filter((e) => e.location)
              .map((e, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-0.5 bg-gray-100 rounded text-gray-600"
                >
                  {e.location}
                  {e.remarks ? ` - ${e.remarks}` : ''}
                </span>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
