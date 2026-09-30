import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Incident, Severity } from './api'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const SEVERITY_COLOR: Record<Severity, string> = {
  Critical: 'var(--color-critical)',
  High: 'var(--color-high)',
  Medium: 'var(--color-medium)',
  Low: 'var(--color-low)',
}

const TYPE_TITLE: Record<string, string> = {
  accident: 'Traffic accident',
  crowd: 'Crowd anomaly',
  baggage: 'Unattended baggage',
}

export function titleOf(inc: Pick<Incident, 'type' | 'subtype'>) {
  if (inc.type === 'baggage') return inc.subtype === 'abandoned' ? 'Abandoned baggage' : 'Unattended baggage'
  if (inc.type === 'crowd') return inc.subtype === 'overcrowding' ? 'Overcrowding' : 'Crowd anomaly'
  return TYPE_TITLE[inc.type] ?? inc.type
}

export function relTime(ts: number, now: number) {
  const s = Math.max(0, Math.round(now - ts))
  if (s < 5) return 'just now'
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m ago`
  return `${Math.floor(s / 86400)}d ago`
}

export function clock(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString('en-GB', { hour12: false })
}

export function incidentId(id: number) {
  return `INC-${String(id).padStart(4, '0')}`
}

export function pct(v: number) {
  return `${Math.round(v * 100)}%`
}
