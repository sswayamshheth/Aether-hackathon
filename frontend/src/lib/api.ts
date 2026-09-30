export type Severity = 'Critical' | 'High' | 'Medium' | 'Low'
export type IncidentType = 'accident' | 'crowd' | 'baggage'
export type IncidentStatus = 'new' | 'confirmed' | 'dismissed'

export interface Reason { text: string; points: number }
export interface IncidentCamera { id: string; name: string; confidence: number }
export interface TimelineEntry { t: number; text: string }

export interface Incident {
  id: number
  type: IncidentType
  subtype: string
  status: IncidentStatus
  severity: Severity
  score: number
  confidence: number
  reasons: Reason[]
  cameras: IncidentCamera[]
  area: string
  first_ts: number
  last_ts: number
  details: Record<string, unknown>
  keyframe: string | null
  clip: string | null
  verification: Record<string, unknown> | null
  timeline: TimelineEntry[]
}

export interface Camera {
  id: string
  name: string
  source: string
  source_label: string
  kind: 'rtsp' | 'file'
  area: string
  profile: 'traffic' | 'public' | 'mixed'
  status: 'online' | 'connecting' | 'reconnecting' | 'offline' | 'stopped'
  fps: number
  latency_ms: number
  error: string
  frames: number
}

export interface Status {
  cameras_total: number
  cameras_online: number
  fps_avg: number
  active_incidents: number
  demo: boolean
  uptime_s: number
  inference: string
  vision_verify: boolean
  telegram: boolean
}

export interface Zone { id: number; camera_id: string; name: string; kind: ZoneKind; points: [number, number][] }
export type ZoneKind = 'lane' | 'restricted' | 'crowd' | 'ignore'

export interface SuppressedRow { id: number; ts: number; camera_id: string; type: string; reason: string; conf: number; duration: number }

export interface Analytics {
  bucket_s: number
  series: { t: number; accident: number; crowd: number; baggage: number; suppressed: number }[]
  by_type: Record<string, number>
  by_severity: Record<string, number>
  by_status: Record<string, number>
  incidents: number
  suppressed: number
  suppressed_by_check: Record<string, number>
  suppressed_by_type: Record<string, number>
  suppressed_recent: SuppressedRow[]
  fps: { ts: number; camera_id: string; fps: number; latency_ms: number }[]
  feedback: Record<string, number>
  thresholds: { camera_id: string; type: string; adj: number }[]
  cameras: Camera[]
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      if (body?.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* keep the status text */ }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  status: () => req<Status>('/api/status'),
  cameras: () => req<Camera[]>('/api/cameras'),
  addCamera: (b: { name: string; source: string; area: string; profile: string }) => req<Camera>('/api/cameras', json(b)),
  removeCamera: (id: string) => req<{ ok: boolean }>(`/api/cameras/${id}`, { method: 'DELETE' }),
  incidents: () => req<Incident[]>('/api/incidents'),
  incident: (id: number) => req<Incident>(`/api/incidents/${id}`),
  act: (id: number, action: 'confirm' | 'dismiss') => req<Incident>(`/api/incidents/${id}/${action}`, { method: 'POST' }),
  zones: () => req<Zone[]>('/api/zones'),
  addZone: (z: Omit<Zone, 'id'>) => req<{ id: number }>('/api/zones', json(z)),
  removeZone: (id: number) => req<{ ok: boolean }>(`/api/zones/${id}`, { method: 'DELETE' }),
  analytics: (minutes: number) => req<Analytics>(`/api/analytics?minutes=${minutes}`),
  models: () => req<Record<string, any>>('/api/models'),
  settings: () => req<Record<string, any>>('/api/settings'),
}

/** Upload with progress. fetch() cannot report upload progress, XHR can. */
export function uploadCamera(form: FormData, onProgress: (pct: number) => void): Promise<Camera> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/cameras/upload')
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100))
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText)
        if (xhr.status >= 200 && xhr.status < 300) resolve(body)
        else reject(new Error(body?.detail ?? `Upload failed (${xhr.status})`))
      } catch {
        reject(new Error(`Upload failed (${xhr.status})`))
      }
    }
    xhr.onerror = () => reject(new Error('Upload failed: the backend did not respond'))
    xhr.send(form)
  })
}
