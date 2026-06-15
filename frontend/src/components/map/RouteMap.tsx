import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { TripStop } from '../../types/trip'

// Custom marker icons
const createIcon = (color: string) =>
  new L.DivIcon({
    className: 'custom-marker',
    html: `<div style="
      background-color: ${color};
      width: 24px;
      height: 24px;
      border-radius: 50%;
      border: 3px solid white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  })

const STOP_COLORS: Record<string, string> = {
  start: '#3B82F6',
  pickup: '#10B981',
  dropoff: '#EF4444',
  rest: '#8B5CF6',
  fuel: '#F59E0B',
  break: '#6B7280',
}

const STOP_LABELS: Record<string, string> = {
  start: 'Start',
  pickup: 'Pickup',
  dropoff: 'Drop-off',
  rest: '10hr Rest',
  fuel: 'Fuel Stop',
  break: '30min Break',
}

interface FitBoundsProps {
  positions: [number, number][]
}

function FitBounds({ positions }: FitBoundsProps) {
  const map = useMap()
  useEffect(() => {
    if (positions.length > 0) {
      const bounds = L.latLngBounds(positions)
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }, [positions, map])
  return null
}

interface RouteMapProps {
  routeCoordinates?: [number, number][]
  stops: TripStop[]
  center?: [number, number]
  className?: string
}

export default function RouteMap({
  routeCoordinates = [],
  stops,
  center = [39.8283, -98.5795],
  className = '',
}: RouteMapProps) {
  const allPositions: [number, number][] = stops.map((s) => [s.lat, s.lon])

  return (
    <div className={`rounded-lg overflow-hidden border border-gray-200 ${className}`}>
      <MapContainer
        center={center}
        zoom={5}
        style={{ height: '100%', width: '100%', minHeight: '400px' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {routeCoordinates.length > 0 && (
          <Polyline
            positions={routeCoordinates}
            pathOptions={{ color: '#3B82F6', weight: 4, opacity: 0.8 }}
          />
        )}

        {stops.map((stop) => (
          <Marker
            key={stop.sequence}
            position={[stop.lat, stop.lon]}
            icon={createIcon(STOP_COLORS[stop.stop_type] || '#6B7280')}
          >
            <Popup>
              <div className="text-sm">
                <p className="font-semibold">
                  {STOP_LABELS[stop.stop_type] || stop.stop_type}
                </p>
                <p className="text-gray-600">{stop.location_name}</p>
                {stop.arrival_time && (
                  <p className="text-gray-500 text-xs mt-1">
                    Arrive: {new Date(stop.arrival_time).toLocaleString()}
                  </p>
                )}
                {stop.duration_minutes > 0 && (
                  <p className="text-gray-500 text-xs">
                    Duration: {stop.duration_minutes} min
                  </p>
                )}
              </div>
            </Popup>
          </Marker>
        ))}

        {allPositions.length > 0 && <FitBounds positions={allPositions} />}
      </MapContainer>
    </div>
  )
}
