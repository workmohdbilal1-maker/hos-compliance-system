import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapPin, Navigation, Package, Truck, Loader2, Search } from 'lucide-react'
import RouteMap from '../components/map/RouteMap'
import DutyTimeline from '../components/log/DutyTimeline'
import HosStatus from '../components/log/HosStatus'
import { createTrip, geocodeLocation } from '../api/trips'
import type { GeocodeResult } from '../api/trips'
import type { Trip, TripStop, HOSStatus as HOSStatusType, DailySummary } from '../types/trip'

// ---------------------------------------------------------------------------
// LocationInput — text field with debounced geocode autocomplete
// ---------------------------------------------------------------------------
function LocationInput({
  label,
  icon,
  name,
  lat,
  lng,
  onNameChange,
  onSelect,
}: {
  label: string
  icon: React.ReactNode
  name: string
  lat: string
  lng: string
  onNameChange: (v: string) => void
  onSelect: (name: string, lat: string, lng: string) => void
}) {
  const [suggestions, setSuggestions] = useState<GeocodeResult[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  // Close suggestions on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleInputChange = useCallback(
    (value: string) => {
      onNameChange(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)

      if (value.length < 2) {
        setSuggestions([])
        setShowSuggestions(false)
        return
      }

      debounceRef.current = setTimeout(async () => {
        setLoading(true)
        try {
          const results = await geocodeLocation(value)
          setSuggestions(results)
          setShowSuggestions(results.length > 0)
        } catch {
          setSuggestions([])
        } finally {
          setLoading(false)
        }
      }, 400)
    },
    [onNameChange],
  )

  const handleSelect = (result: GeocodeResult) => {
    onSelect(result.name, String(result.lat), String(result.lng))
    setShowSuggestions(false)
    setSuggestions([])
  }

  return (
    <div className="space-y-2" ref={wrapperRef}>
      <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
        {icon}
        {label}
      </label>
      <div className="relative">
        <input
          type="text"
          value={name}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          placeholder="Type a city or address..."
        />
        {loading && (
          <div className="absolute right-2 top-2.5">
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
          </div>
        )}
        {showSuggestions && (
          <ul className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
            {suggestions.map((s, i) => (
              <li
                key={i}
                onClick={() => handleSelect(s)}
                className="px-3 py-2 text-sm hover:bg-primary-50 cursor-pointer flex items-center gap-2"
              >
                <Search className="h-3 w-3 text-gray-400 flex-shrink-0" />
                <span className="truncate">{s.name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input
          type="number"
          step="any"
          value={lat}
          onChange={(e) => onSelect(name, e.target.value, lng)}
          className="px-3 py-1.5 border border-gray-300 rounded text-xs"
          placeholder="Latitude"
        />
        <input
          type="number"
          step="any"
          value={lng}
          onChange={(e) => onSelect(name, lat, e.target.value)}
          className="px-3 py-1.5 border border-gray-300 rounded text-xs"
          placeholder="Longitude"
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// TripPlanner page
// ---------------------------------------------------------------------------
export default function TripPlanner() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [trip, setTrip] = useState<Trip | null>(null)

  // Form state
  const [currentLat, setCurrentLat] = useState('40.7128')
  const [currentLng, setCurrentLng] = useState('-74.0060')
  const [currentName, setCurrentName] = useState('New York, NY')
  const [pickupLat, setPickupLat] = useState('39.9526')
  const [pickupLng, setPickupLng] = useState('-75.1652')
  const [pickupName, setPickupName] = useState('Philadelphia, PA')
  const [dropoffLat, setDropoffLat] = useState('33.7490')
  const [dropoffLng, setDropoffLng] = useState('-84.3880')
  const [dropoffName, setDropoffName] = useState('Atlanta, GA')
  const [cycleUsed, setCycleUsed] = useState('20')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const result = await createTrip({
        current_location: {
          lat: parseFloat(currentLat),
          lng: parseFloat(currentLng),
          name: currentName,
        },
        pickup_location: {
          lat: parseFloat(pickupLat),
          lng: parseFloat(pickupLng),
          name: pickupName,
        },
        dropoff_location: {
          lat: parseFloat(dropoffLat),
          lng: parseFloat(dropoffLng),
          name: dropoffName,
        },
        cycle_hours_used: parseFloat(cycleUsed),
      })
      setTrip(result)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to plan trip')
    } finally {
      setLoading(false)
    }
  }

  // Build stops for map preview (even before API call)
  const previewStops: TripStop[] = [
    {
      id: 1,
      stop_type: 'start',
      location_name: currentName,
      lat: parseFloat(currentLat) || 0,
      lon: parseFloat(currentLng) || 0,
      arrival_time: '',
      departure_time: null,
      sequence: 0,
      duration_minutes: 0,
    },
    {
      id: 2,
      stop_type: 'pickup',
      location_name: pickupName,
      lat: parseFloat(pickupLat) || 0,
      lon: parseFloat(pickupLng) || 0,
      arrival_time: '',
      departure_time: null,
      sequence: 1,
      duration_minutes: 0,
    },
    {
      id: 3,
      stop_type: 'dropoff',
      location_name: dropoffName,
      lat: parseFloat(dropoffLat) || 0,
      lon: parseFloat(dropoffLng) || 0,
      arrival_time: '',
      departure_time: null,
      sequence: 2,
      duration_minutes: 0,
    },
  ]

  const displayStops = trip?.stops || previewStops

  // Extract route coordinates for polyline
  const routeCoords: [number, number][] = trip?.route_data?.coordinates
    ? trip.route_data.coordinates.map((c: number[]) => [c[1], c[0]] as [number, number])
    : []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Plan a Trip</h1>
          <p className="text-sm text-gray-500 mt-1">
            Enter your route details and we'll generate an HOS-compliant schedule
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trip Form */}
        <div className="lg:col-span-1">
          <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
            <h2 className="font-semibold text-gray-800 flex items-center gap-2">
              <Navigation className="h-5 w-5 text-primary-500" />
              Route Details
            </h2>

            {/* Current Location */}
            <LocationInput
              label="Current Location"
              icon={<MapPin className="h-4 w-4 text-blue-500" />}
              name={currentName}
              lat={currentLat}
              lng={currentLng}
              onNameChange={setCurrentName}
              onSelect={(name, lat, lng) => {
                setCurrentName(name)
                setCurrentLat(lat)
                setCurrentLng(lng)
              }}
            />

            {/* Pickup */}
            <LocationInput
              label="Pickup Location"
              icon={<Package className="h-4 w-4 text-green-500" />}
              name={pickupName}
              lat={pickupLat}
              lng={pickupLng}
              onNameChange={setPickupName}
              onSelect={(name, lat, lng) => {
                setPickupName(name)
                setPickupLat(lat)
                setPickupLng(lng)
              }}
            />

            {/* Dropoff */}
            <LocationInput
              label="Drop-off Location"
              icon={<MapPin className="h-4 w-4 text-red-500" />}
              name={dropoffName}
              lat={dropoffLat}
              lng={dropoffLng}
              onNameChange={setDropoffName}
              onSelect={(name, lat, lng) => {
                setDropoffName(name)
                setDropoffLat(lat)
                setDropoffLng(lng)
              }}
            />

            {/* Cycle Hours */}
            <div className="space-y-2">
              <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
                <ClockIcon className="h-4 w-4 text-purple-500" />
                Current Cycle Hours Used
              </label>
              <input
                type="number"
                step="0.5"
                min="0"
                max="70"
                value={cycleUsed}
                onChange={(e) => setCycleUsed(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="Hours used in current cycle"
              />
              <p className="text-xs text-gray-400">Hours on-duty in last 8 days (70hr/8day cycle)</p>
            </div>

            {error && (
              <div className="p-3 bg-red-50 text-red-700 text-sm rounded-lg">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Planning Trip...
                </>
              ) : (
                <>
                  <Truck className="h-4 w-4" />
                  Plan Trip
                </>
              )}
            </button>
          </form>

          {/* Trip Summary */}
          {trip && (
            <div className="mt-4 bg-white rounded-lg border border-gray-200 p-5">
              <h3 className="font-semibold text-gray-800 mb-3">Trip Summary</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Distance</span>
                  <span className="font-medium">{Number(trip.total_distance_miles || 0).toFixed(0)} mi</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Est. Duration</span>
                  <span className="font-medium">{Number(trip.estimated_duration_hours || 0).toFixed(1)} hrs</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Total Days</span>
                  <span className="font-medium">{trip.total_trip_days || 1}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Driving Hours</span>
                  <span className="font-medium">{Number(trip.total_driving_hours || 0).toFixed(1)} hrs</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Stops</span>
                  <span className="font-medium">{trip.stops?.length || 0}</span>
                </div>
              </div>

              <button
                onClick={() => navigate(`/trips/${trip.id}`)}
                className="mt-4 w-full py-2 px-4 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
              >
                View Full Details & Download PDF
              </button>
            </div>
          )}
        </div>

        {/* Map + Timeline */}
        <div className="lg:col-span-2 space-y-4">
          <RouteMap
            stops={displayStops}
            routeCoordinates={routeCoords}
            className="h-[450px]"
          />

          {/* Daily Timelines */}
          {trip?.daily_summaries?.map((day: DailySummary) => (
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
      </div>
    </div>
  )
}

function ClockIcon(props: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}
