export interface Location {
  lat: number
  lng: number
  name?: string
}

export interface TripStop {
  id: number
  stop_type: 'start' | 'pickup' | 'dropoff' | 'rest' | 'fuel' | 'break'
  location_name: string
  lat: number
  lon: number
  arrival_time: string
  departure_time: string | null
  sequence: number
  duration_minutes: number
}

export interface DutyStatusEntry {
  status: 'off_duty' | 'sleeper_berth' | 'driving' | 'on_duty_not_driving'
  start_time: string
  end_time: string | null
  location: string | null
  remarks: string | null
}

export interface DailySummary {
  date: string
  driving_hours: number
  on_duty_hours: number
  off_duty_hours: number
  sleeper_hours: number
  entries: DutyStatusEntry[]
}

export interface Trip {
  id: number
  status: string
  created_at: string
  current_location: string
  current_lat: number
  current_lon: number
  pickup_location: string
  pickup_lat: number
  pickup_lon: number
  dropoff_location: string
  dropoff_lat: number
  dropoff_lon: number
  total_distance_miles: number | null
  estimated_duration_hours: number | null
  total_trip_days: number | null
  total_driving_hours: number | null
  route_data: any | null
  stops: TripStop[]
  daily_summaries: DailySummary[]
}

export interface TripCreateRequest {
  current_location: Location
  pickup_location: Location
  dropoff_location: Location
  cycle_hours_used: number
}

export interface HOSStatus {
  driving_hours_used: number
  driving_hours_remaining: number
  window_hours_used: number
  window_hours_remaining: number
  break_hours_driving_since_last: number
  break_required: boolean
  cycle_hours_used: number
  cycle_hours_remaining: number
  cycle_type: string
  can_drive: boolean
  violations: { rule: string; description: string; severity: string }[]
  explanations: string[]
}
