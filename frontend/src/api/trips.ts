import api from './client'
import type { Trip, TripCreateRequest } from '../types/trip'

export async function createTrip(data: TripCreateRequest): Promise<Trip> {
  const response = await api.post('/trips/', data)
  return response.data
}

export async function getTrip(id: number): Promise<Trip> {
  const response = await api.get(`/trips/${id}/`)
  return response.data
}

export async function getTrips(): Promise<Trip[]> {
  const response = await api.get('/trips/')
  return response.data.results || response.data
}

export async function getTripLogs(id: number) {
  const response = await api.get(`/trips/${id}/logs/`)
  return response.data
}

export async function downloadTripPDF(id: number): Promise<Blob> {
  const response = await api.get(`/trips/${id}/pdf/`, {
    responseType: 'blob',
  })
  return response.data
}

export async function getRoute(
  origin: { lat: number; lng: number },
  destination: { lat: number; lng: number }
) {
  const response = await api.get('/maps/route/', {
    params: {
      origin: `${origin.lat},${origin.lng}`,
      destination: `${destination.lat},${destination.lng}`,
    },
  })
  return response.data
}

export interface GeocodeResult {
  name: string
  lat: number
  lng: number
  country: string
  region: string
}

export async function geocodeLocation(query: string): Promise<GeocodeResult[]> {
  const response = await api.get('/maps/geocode/', {
    params: { q: query },
  })
  return response.data.results || []
}
