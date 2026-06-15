import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Download, MapPin, Clock, Truck, Loader2 } from 'lucide-react'
import RouteMap from '../components/map/RouteMap'
import DutyTimeline from '../components/log/DutyTimeline'
import { getTrip, downloadTripPDF } from '../api/trips'
import type { Trip, DailySummary } from '../types/trip'

export default function TripDetail() {
  const { id } = useParams<{ id: string }>()
  const [trip, setTrip] = useState<Trip | null>(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    if (id) {
      getTrip(parseInt(id))
        .then(setTrip)
        .catch(() => {})
        .finally(() => setLoading(false))
    }
  }, [id])

  const handleDownloadPDF = async () => {
    if (!trip) return
    setDownloading(true)
    try {
      const blob = await downloadTripPDF(trip.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `trip_${trip.id}_rods.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      alert('Failed to download PDF')
    } finally {
      setDownloading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    )
  }

  if (!trip) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Trip not found</p>
        <Link to="/" className="text-primary-600 hover:underline mt-2 inline-block">
          Back to Dashboard
        </Link>
      </div>
    )
  }

  const routeCoords: [number, number][] = trip.route_data?.coordinates
    ? trip.route_data.coordinates.map((c: number[]) => [c[1], c[0]] as [number, number])
    : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link
            to="/"
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-gray-500" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Trip #{trip.id}</h1>
            <p className="text-sm text-gray-500 flex items-center gap-2 mt-1">
              <MapPin className="h-3 w-3" />
              {trip.current_location} → {trip.pickup_location} → {trip.dropoff_location}
            </p>
          </div>
        </div>
        <button
          onClick={handleDownloadPDF}
          disabled={downloading}
          className="flex items-center gap-2 px-4 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
        >
          {downloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Download RODS PDF
        </button>
      </div>

      {/* Trip Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Distance</p>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {Number(trip.total_distance_miles || 0).toFixed(0)} <span className="text-sm font-normal">mi</span>
          </p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Driving Time</p>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {Number(trip.total_driving_hours || 0).toFixed(1)} <span className="text-sm font-normal">hrs</span>
          </p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Total Days</p>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {trip.total_trip_days || 1}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Stops</p>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {trip.stops?.length || 0}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Status</p>
          <p className="text-xl font-bold text-green-600 mt-1 capitalize">
            {trip.status}
          </p>
        </div>
      </div>

      {/* Map */}
      <RouteMap
        stops={trip.stops || []}
        routeCoordinates={routeCoords}
        className="h-[400px]"
      />

      {/* Stops List */}
      {trip.stops && trip.stops.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Stops</h2>
          <div className="space-y-3">
            {trip.stops.map((stop, idx) => (
              <div
                key={stop.sequence}
                className="flex items-center space-x-4 p-3 rounded-lg bg-gray-50"
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-sm font-bold">
                  {idx + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
                      {stop.stop_type.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="font-medium text-gray-900">{stop.location_name}</p>
                </div>
                <div className="text-right text-sm text-gray-500">
                  {stop.arrival_time && (
                    <p>{new Date(stop.arrival_time).toLocaleString()}</p>
                  )}
                  {stop.duration_minutes > 0 && (
                    <p className="text-xs text-gray-400">{stop.duration_minutes} min</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Daily Timelines */}
      {trip.daily_summaries && trip.daily_summaries.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Daily Duty Logs</h2>
          {trip.daily_summaries.map((day: DailySummary) => (
            <DutyTimeline
              key={day.date}
              date={day.date}
              entries={day.entries}
              totals={{
                driving_hours: day.driving_hours,
                on_duty_hours: day.on_duty_hours,
                off_duty_hours: day.off_duty_hours,
                sleeper_hours: day.sleeper_hours,
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
