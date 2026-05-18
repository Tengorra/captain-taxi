export type City = 'saskatoon' | 'regina'

export type DriverStatus = 'active' | 'offline' | 'on_trip' | 'suspended' | 'pending'

// ── Dispatch types ─────────────────────────────────────────────────────────

export type DispatchDriverStatus = 'online' | 'offline' | 'on_trip' | 'break' | 'parked' | 'dropping' | 'bidding'

export type TripStatus = 'pending' | 'assigned' | 'en_route' | 'arrived' | 'in_progress' | 'completed' | 'cancelled' | 'noshow'

export type BookingSource = 'phone' | 'app' | 'web' | 'whatsapp' | 'agent'

export interface DispatchTrip {
  id: string
  customer_name: string
  customer_phone: string
  customer_email: string
  pickup_address: string
  pickup_lat?: number
  pickup_lng?: number
  dropoff_address: string
  dropoff_lat?: number
  dropoff_lng?: number
  via_address: string
  city: string
  notes: string
  instructions: string
  site: string
  priority: number  // 0=normal, 1=high, 2=urgent
  fare_estimate?: number
  fare_final?: number
  status: TripStatus
  booking_source: BookingSource
  driver_id?: string
  assigned_at?: string
  assignment_attempts: number
  ai_reasoning: string
  requested_at: string
  driver_en_route_at?: string
  driver_arrived_at?: string
  pickup_at?: string
  completed_at?: string
  cancelled_at?: string
  cancellation_reason: string
  noshow_at?: string
  scheduled_for?: string
  created_at: string
}

export interface DispatchDriver {
  id: string
  name: string
  phone: string
  vehicle_plate: string
  vehicle_model: string
  city: string
  status: DispatchDriverStatus
  rating: number
  total_trips: number
  is_active: boolean
  last_lat?: number
  last_lng?: number
  last_location_at?: string
  created_at: string
}

export interface QueueTrip {
  trip_id: string
  customer_name: string
  customer_phone: string
  customer_email: string
  pickup_address: string
  dropoff_address: string
  via_address: string
  city: string
  driver_id?: string
  priority: number
  instructions: string
  site: string
  requested_at?: string
  scheduled_for?: string
  assigned_at?: string
  completed_at?: string
  cancelled_at?: string
  noshow_at?: string
  fare_estimate?: number
  fare_final?: number
  notes: string
  booking_source: string
  status: TripStatus
}

export interface DispatchQueue {
  dispatch: QueueTrip[]
  pre_booked: QueueTrip[]
  booked: QueueTrip[]
  in_progress: QueueTrip[]
  completed: QueueTrip[]
  cancelled: QueueTrip[]
  noshow: QueueTrip[]
}

export interface MapDriver {
  driver_id: string
  name: string
  status: DispatchDriverStatus
  city: string
  vehicle_plate: string
  vehicle_model: string
  rating: number
  lat?: number
  lng?: number
}

export interface MapTrip {
  trip_id: string
  status: TripStatus
  city: string
  pickup_address: string
  pickup_lat?: number
  pickup_lng?: number
  dropoff_address: string
  dropoff_lat?: number
  dropoff_lng?: number
  driver_id?: string
  customer_name: string
  requested_at?: string
}

export interface DispatchMapData {
  drivers: MapDriver[]
  trips: MapTrip[]
}

export interface DispatchStats {
  window_hours: number
  completed_trips: number
  trips_per_hour: number
  avg_wait_minutes?: number
  active_drivers: number
  pending_trips: number
  by_city: Record<string, number>
}

export interface TripCreatePayload {
  customer_name?: string
  customer_phone: string
  customer_email?: string
  pickup_address: string
  dropoff_address: string
  via_address?: string
  city: string
  notes?: string
  instructions?: string
  site?: string
  priority?: number
  fare_estimate?: number
  booking_source?: BookingSource
  scheduled_for?: string
}

export interface Driver {
  id: string
  // Core
  name: string
  phone: string
  email?: string
  city: City
  status: DriverStatus
  performance_score: number
  commission_rate: number
  vehicle_plate?: string
  vehicle_model?: string
  total_trips?: number
  total_earnings?: number
  documents?: DriverDocument[]
  notes?: string
  created_at?: string

  // Personal
  first_name?: string
  last_name?: string
  aka?: string
  address?: string
  mobile_phone?: string
  other_phone?: string
  sex?: 'male' | 'female' | 'other'

  // Professional
  driver_type?: 'regular' | 'wheelchair' | 'executive' | 'school'

  // Licensing
  badge_number?: string
  badge_expiry?: string
  badge_type?: string
  licence_number?: string
  licence_expiry?: string
  tax_number?: string

  // Attributes
  accept_discount?: boolean
  accept_account?: boolean
  accept_cash_work?: boolean
  accept_fixed_fares?: boolean

  // Device
  device_imei?: string

  // Payments
  payment_on?: string
  payment_type?: string
  bank_name?: string
  bank_account_number?: string
  sort_code?: string

  // Sites
  primary_site?: string

  // Suspension
  suspension_reason?: string
  suspended_at?: string

  // iCabbi linkage / activity
  icabbi_ref?: string
  icabbi_driver_id?: string
  vehicle_ref?: string
  is_active_flag?: boolean
  is_deleted?: boolean
  start_date?: string
  last_active_at?: string
  last_updated_at?: string
  mobile?: string
  gender?: string
  phone_os?: string
  phone_model?: string
}

export interface ActivityLog {
  id: string
  driver_id: string
  action: string
  details: string
  performed_by: string
  created_at: string
}

export interface DriverDocument {
  id?: number
  type: string
  status: 'valid' | 'expiring' | 'expiring_soon' | 'expired' | 'missing'
  expiry_date?: string
  uploaded_at?: string
}

export interface Trip {
  id: string
  city: City
  status: string
  pickup: string
  dropoff: string
  fare: number
  completed_at?: string
}

export interface Alert {
  id: number
  title: string
  message: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  source_agent: string
  is_read: boolean
  driver_id?: number
  created_at: string
}

export interface Escalation {
  id: number
  title: string
  description: string
  source_agent: string
  status: 'pending' | 'approved' | 'denied' | 'expired'
  decision?: string
  decision_note?: string
  metadata?: Record<string, unknown>
  created_at: string
  resolved_at?: string
  expires_at?: string
}

export interface OverviewStats {
  drivers_online: { saskatoon: number; regina: number; total: number }
  active_trips: { saskatoon: number; regina: number; total: number }
  today: { trips: number; revenue: number; revenue_change_pct: number }
  alerts: { unread: number; critical: number }
  pending_escalations: number
  timestamp: string
}

export interface ComplianceDriver {
  driver_id: number
  driver_name: string
  city: City
  overall_status: 'green' | 'amber' | 'red'
  documents: Record<string, string>
}

export interface RevenueData {
  start_date: string
  end_date: string
  total_trips: number
  total_revenue: number
  company_revenue: number
  driver_pay: number
  by_city: Record<string, { trips: number; revenue: number }>
  daily: Record<string, { trips: number; revenue: number }>
}

export interface ChartPoint {
  date: string
  label: string
  revenue: number
  trips: number
}

export interface AppSettings {
  [key: string]: { value: string; description: string }
}
