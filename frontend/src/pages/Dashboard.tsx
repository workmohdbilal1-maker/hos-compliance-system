import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, MapPin, Truck, ArrowRight, Clock } from 'lucide-react'
import { getTrips } from '../api/trips'
import type { Trip } from '../types/trip'

export default function Dashboard() {
  const [trips, setTrips] = useState<Trip[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTrips()
      .then(setTrips)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            ELD Trip Planner - FMCSA Hours of Service Compliance
          </p>
        </div>
        <Link
          to="/trips/new"
          className="flex items-center gap-2 px-4 py-2.5 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Trip
        </Link>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Truck className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{trips.length}</p>
              <p className="text-sm text-gray-500">Total Trips</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <Clock className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">11.0</p>
              <p className="text-sm text-gray-500">Max Drive (hrs)</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Clock className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">14.0</p>
              <p className="text-sm text-gray-500">Duty Window (hrs)</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-amber-100 rounded-lg">
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">70.0</p>
              <p className="text-sm text-gray-500">Cycle Limit (hrs)</p>
            </div>
          </div>
        </div>
      </div>

      {/* HOS Rules Summary */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">FMCSA HOS Rules (Property Carriers)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
          <div className="p-3 bg-blue-50 rounded-lg">
            <p className="font-medium text-blue-800">14-Hour Driving Window</p>
            <p className="text-blue-600 mt-1">Cannot drive after 14th hour from start of work. Resets after 10hr off-duty.</p>
          </div>
          <div className="p-3 bg-green-50 rounded-lg">
            <p className="font-medium text-green-800">11-Hour Driving Limit</p>
            <p className="text-green-600 mt-1">Max 11 hours driving within the 14-hour window.</p>
          </div>
          <div className="p-3 bg-amber-50 rounded-lg">
            <p className="font-medium text-amber-800">30-Minute Break</p>
            <p className="text-amber-600 mt-1">Must take 30min break after 8 cumulative driving hours.</p>
          </div>
          <div className="p-3 bg-purple-50 rounded-lg">
            <p className="font-medium text-purple-800">70-Hour/8-Day Limit</p>
            <p className="text-purple-600 mt-1">Cannot drive after 70 on-duty hours in 8 consecutive days.</p>
          </div>
          <div className="p-3 bg-indigo-50 rounded-lg">
            <p className="font-medium text-indigo-800">34-Hour Restart</p>
            <p className="text-indigo-600 mt-1">34+ consecutive hours off resets weekly cycle to zero.</p>
          </div>
          <div className="p-3 bg-red-50 rounded-lg">
            <p className="font-medium text-red-800">10-Hour Off-Duty</p>
            <p className="text-red-600 mt-1">Must take 10 consecutive hours off-duty between shifts.</p>
          </div>
        </div>
      </div>

      {/* Recent Trips */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Recent Trips</h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400">Loading trips...</div>
        ) : trips.length === 0 ? (
          <div className="p-8 text-center">
            <Truck className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 mb-4">No trips planned yet</p>
            <Link
              to="/trips/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700"
            >
              <Plus className="h-4 w-4" />
              Plan Your First Trip
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {trips.map((trip) => (
              <Link
                key={trip.id}
                to={`/trips/${trip.id}`}
                className="flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center space-x-4">
                  <div className="flex-shrink-0 p-2 bg-gray-100 rounded-lg">
                    <Truck className="h-5 w-5 text-gray-500" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2 text-sm font-medium text-gray-900">
                      <MapPin className="h-3 w-3 text-blue-500" />
                      <span>{trip.current_location}</span>
                      <ArrowRight className="h-3 w-3 text-gray-400" />
                      <span>{trip.dropoff_location}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {Number(trip.total_distance_miles || 0).toFixed(0)} mi
                      {trip.total_driving_hours ? ` | ${Number(trip.total_driving_hours).toFixed(1)} hrs driving` : ''}
                      {trip.total_trip_days ? ` | ${trip.total_trip_days} day(s)` : ''}
                    </p>
                  </div>
                </div>
                <div className="text-xs text-gray-400">
                  {new Date(trip.created_at).toLocaleDateString()}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
