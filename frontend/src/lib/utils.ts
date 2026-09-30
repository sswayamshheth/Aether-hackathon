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
  fire: 'Fire',
  weapon: 'Weapon seen',
  violence: 'Fight or assault',
  medical: 'Person down',
  hazard: 'Hazard',
  security: 'Security alert',
}

const SUBTYPE_TITLE: Record<string, string> = {
  abandoned: 'Abandoned baggage',
  overcrowding: 'Overcrowding',
  smoke: 'Smoke',
  explosion: 'Explosion',
  pistol: 'Gun seen',
  knife: 'Knife seen',
  robbery: 'Robbery',
  fight: 'Fight or assault',
  fall: 'Person fallen',
  collapse: 'Person collapsed',
  flood: 'Flooding',
  vandalism: 'Vandalism',
  animal: 'Animal on the road',
  intrusion: 'Intrusion',
  loitering: 'Loitering',
  'wrong-way driving': 'Wrong-way driving',
  'stalled vehicle': 'Stalled vehicle',
  'pedestrian on road': 'Pedestrian on the road',
}

export function titleOf(inc: Pick<Incident, 'type' | 'subtype'>) {
  if (inc.subtype === 'abandoned' && inc.type !== 'baggage') return TYPE_TITLE[inc.type] ?? inc.type
  return SUBTYPE_TITLE[inc.subtype] ?? TYPE_TITLE[inc.type] ?? inc.type
}

/** Incident types grouped into five families for charts (colours validated for the dark
 *  surface with the dataviz palette checker, in this order). */
export const FAMILIES = [
  { key: 'fire', label: 'Fire & hazards', types: ['fire', 'hazard'], color: '#c98500' },
  { key: 'people', label: 'Crowd & medical', types: ['crowd', 'medical'], color: '#199e70' },
  { key: 'traffic', label: 'Traffic', types: ['accident'], color: '#3987e5' },
  { key: 'violence', label: 'Violence & weapons', types: ['violence', 'weapon'], color: '#d55181' },
  { key: 'security', label: 'Security & objects', types: ['security', 'baggage'], color: '#9085e9' },
] as const

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
