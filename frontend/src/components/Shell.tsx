import { useQuery } from '@tanstack/react-query'
import { BarChart3, Boxes, LayoutGrid, PenLine, Video, Volume2, VolumeX } from 'lucide-react'
import { createContext, useContext, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '@/lib/api'
import { useLiveEvents } from '@/lib/live'
import { cn } from '@/lib/utils'
import { Tooltip } from './ui'

const NAV = [
  { to: '/', label: 'Command', icon: LayoutGrid, end: true },
  { to: '/cameras', label: 'Cameras', icon: Video },
  { to: '/zones', label: 'Zones', icon: PenLine },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/models', label: 'Models', icon: Boxes },
]

const TITLES: Record<string, string> = {
  '/': 'Command',
  '/cameras': 'Cameras',
  '/zones': 'Zones',
  '/analytics': 'Analytics',
  '/models': 'Models',
}

/** Wall clock shared by every relative timestamp, ticking once a second. */
const NowContext = createContext(Date.now() / 1000)
export const useNow = () => useContext(NowContext)

function Stat({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'warn' | 'alert' }) {
  const color = tone === 'alert' ? 'text-critical' : tone === 'warn' ? 'text-medium' : 'text-fg'
  return (
    <div className="flex items-baseline gap-1.5 border-l border-line pl-4">
      <span className="text-[11px] uppercase tracking-wider text-faint">{label}</span>
      <span className={cn('num text-[13px] font-medium', color)}>{value}</span>
    </div>
  )
}

export function Shell() {
  const [sound, setSound] = useState(() => localStorage.getItem('drishti.sound') === '1')
  const connected = useLiveEvents(sound)
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: connected ? false : 5000 })
  const [now, setNow] = useState(Date.now() / 1000)
  const loc = useLocation()

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000)
    return () => clearInterval(t)
  }, [])
  useEffect(() => localStorage.setItem('drishti.sound', sound ? '1' : '0'), [sound])

  const title = loc.pathname.startsWith('/incidents/') ? 'Incident' : (TITLES[loc.pathname] ?? 'Drishti')
  const camsDown = status ? status.cameras_total - status.cameras_online : 0

  return (
    <NowContext.Provider value={now}>
      <div className="flex h-full min-w-[1180px]">
        <nav className="flex w-14 shrink-0 flex-col items-center border-r border-line bg-surface py-3">
          <div className="mb-4 flex h-8 w-8 items-center justify-center rounded-md border border-line bg-bg" aria-label="Drishti">
            <svg viewBox="0 0 32 32" width="20" height="20" aria-hidden>
              <path d="M5 16c3-5.2 6.700-7.800 11-7.800S24 10.800 27 16c-3 5.200-6.700 7.800-11 7.800S8 21.200 5 16Z" fill="none" stroke="#3B82F6" strokeWidth="2.200" />
              <circle cx="16" cy="16" r="3.600" fill="#3B82F6" />
            </svg>
          </div>
          <div className="flex flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <Tooltip key={to} label={label}>
                <NavLink
                  to={to}
                  end={end}
                  aria-label={label}
                  className={({ isActive }) =>
                    cn('relative flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors duration-150 hover:bg-raised hover:text-fg', isActive && 'bg-accent-soft text-accent hover:bg-accent-soft hover:text-accent')
                  }
                >
                  <Icon size={17} strokeWidth={1.75} />
                </NavLink>
              </Tooltip>
            ))}
          </div>
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-12 shrink-0 items-center justify-between border-b border-line bg-surface px-4">
            <div className="flex items-baseline gap-3">
              <span className="text-[13px] font-semibold tracking-tight text-fg">Drishti</span>
              <span className="text-faint">/</span>
              <h1 className="text-[13px] font-medium text-muted">{title}</h1>
              {status?.demo && (
                <span className="ml-1 rounded-sm border border-line px-1.5 py-px text-[10px] font-medium uppercase tracking-wider text-muted">Demo replay</span>
              )}
            </div>
            <div className="flex items-center gap-4">
              {status ? (
                <>
                  <Stat label="Cameras" value={`${status.cameras_online}/${status.cameras_total}`} tone={camsDown ? 'warn' : undefined} />
                  <Stat label="Avg FPS" value={status.cameras_online ? status.fps_avg.toFixed(1) : '0.0'} />
                  <Stat label="Open" value={String(status.active_incidents)} tone={status.active_incidents ? 'alert' : undefined} />
                  <div className="hidden border-l border-line pl-4 text-[12px] text-faint xl:block">{status.inference}</div>
                </>
              ) : (
                <div className="skeleton h-4 w-64" />
              )}
              <div className="flex items-center gap-2 border-l border-line pl-4">
                <Tooltip label={sound ? 'Critical-incident sound is on' : 'Critical-incident sound is off'} side="bottom">
                  <button onClick={() => setSound((s) => !s)} aria-label="Toggle critical-incident sound" className={cn('flex h-7 w-7 items-center justify-center rounded-md transition-colors duration-150 hover:bg-raised', sound ? 'text-fg' : 'text-faint')}>
                    {sound ? <Volume2 size={15} strokeWidth={1.75} /> : <VolumeX size={15} strokeWidth={1.75} />}
                  </button>
                </Tooltip>
                <div className="flex items-center gap-1.5 text-[12px]">
                  <span className={cn('h-1.5 w-1.5 rounded-full', connected ? 'live-dot bg-ok' : 'bg-critical')} />
                  <span className={connected ? 'text-muted' : 'text-critical'}>{connected ? 'Live' : 'Disconnected'}</span>
                </div>
              </div>
            </div>
          </header>
          <main className="min-h-0 flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </NowContext.Provider>
  )
}
