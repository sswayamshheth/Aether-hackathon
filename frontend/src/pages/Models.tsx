import { useQuery } from '@tanstack/react-query'
import { Boxes } from 'lucide-react'
import { Button, EmptyState, Panel, PanelHeader, Skeleton } from '@/components/ui'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Column { key: string; label: string; align?: 'right'; mono?: boolean }
interface Section { title: string; meta?: string; note?: string; columns: Column[]; rows: Record<string, string | number | null>[] }
interface Summary { generated: string; machine: string; sections: Section[] }

function Cell({ v }: { v: string | number | null | undefined }) {
  if (v === null || v === undefined || v === '') return <span className="text-faint">n/a</span>
  return <>{v}</>
}

export function Models() {
  const q = useQuery({ queryKey: ['models'], queryFn: api.models })
  const summary = q.data?.summary as Summary | null | undefined

  if (q.isLoading) return <div className="space-y-3 p-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-44 rounded-lg" />)}</div>
  if (q.isError) {
    return <EmptyState icon={Boxes} title="Could not load model results" action={<Button size="sm" onClick={() => q.refetch()}>Retry</Button>}>The backend did not answer.</EmptyState>
  }
  if (!summary?.sections?.length) {
    return (
      <EmptyState icon={Boxes} title="No measured results yet">
        This page only shows numbers produced by the scripts in training\. Run training\bench\make_summary.py to build docs\results\summary.json.
      </EmptyState>
    )
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-3 p-3">
      <p className="text-[12px] leading-relaxed text-muted">
        Every number below was measured on this machine (<span className="text-fg">{summary.machine}</span>) by a script in the repo, on the clips named in each table. Generated <span className="num text-fg">{summary.generated}</span>. Source files: docs\results\*.json and BENCH.md.
      </p>
      {summary.sections.map((s) => (
        <Panel key={s.title} className="overflow-hidden">
          <PanelHeader title={s.title} meta={s.meta} />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
                  {s.columns.map((c) => (
                    <th key={c.key} className={cn('h-8 whitespace-nowrap px-3 font-medium', c.align === 'right' && 'text-right')}>{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {s.rows.map((r, i) => (
                  <tr key={i} className="border-b border-line align-top last:border-0">
                    {s.columns.map((c, ci) => (
                      <td key={c.key} className={cn('px-3 py-2 leading-snug', ci === 0 ? 'text-[13px] font-medium text-fg' : 'text-muted', c.align === 'right' && 'text-right', (c.mono || c.align === 'right') && 'num text-fg')}>
                        <Cell v={r[c.key]} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {s.note && <p className="border-t border-line px-3 py-2 text-[12px] leading-relaxed text-muted">{s.note}</p>}
        </Panel>
      ))}
    </div>
  )
}
