import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Check, ChevronDown, type LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'
import type { Severity } from '@/lib/api'
import { cn, SEVERITY_COLOR } from '@/lib/utils'

const button = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-colors duration-150 disabled:opacity-45 select-none',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-white hover:bg-[#2f6fe0]',
        secondary: 'border border-line bg-raised text-fg hover:border-line-strong hover:bg-[#1b222d]',
        ghost: 'text-muted hover:bg-raised hover:text-fg',
        danger: 'border border-line bg-raised text-[#f87171] hover:border-[#7f1d1d] hover:bg-[#2a1517]',
      },
      size: { sm: 'h-7 px-2.5 text-[12px]', md: 'h-8 px-3 text-[13px]', icon: 'h-8 w-8' },
    },
    defaultVariants: { variant: 'secondary', size: 'md' },
  },
)

export function Button({ className, variant, size, asChild, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(button({ variant, size }), className)} {...props} />
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn('h-8 w-full rounded-md border border-line bg-bg px-2.5 text-[13px] text-fg placeholder:text-faint transition-colors duration-150 hover:border-line-strong focus:border-accent focus:outline-none', className)}
      {...props}
    />
  )
}

export function Label({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-1 flex items-baseline justify-between">
      <span className="text-[12px] font-medium text-muted">{children}</span>
      {hint && <span className="text-[11px] text-faint">{hint}</span>}
    </div>
  )
}

export function Panel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-lg border border-line bg-surface', className)} {...props} />
}

export function PanelHeader({ title, meta, children }: { title: string; meta?: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-line px-3">
      <div className="flex min-w-0 items-baseline gap-2">
        <h2 className="truncate text-[13px] font-semibold text-fg">{title}</h2>
        {meta && <span className="truncate text-[12px] text-faint">{meta}</span>}
      </div>
      {children && <div className="flex shrink-0 items-center gap-1.5">{children}</div>}
    </div>
  )
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const color = SEVERITY_COLOR[severity]
  return (
    <span
      className={cn('inline-flex h-5 items-center gap-1.5 rounded-sm px-1.5 text-[11px] font-semibold uppercase tracking-wide', className)}
      style={{ color, background: `color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {severity}
    </span>
  )
}

export function Tag({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn('inline-flex h-5 items-center rounded-sm border border-line px-1.5 text-[11px] text-muted', className)}>{children}</span>
}

export function StatusDot({ status }: { status: string }) {
  const color = status === 'online' ? 'var(--color-ok)' : status === 'offline' || status === 'stopped' ? 'var(--color-critical)' : 'var(--color-medium)'
  return <span className={cn('inline-block h-1.5 w-1.5 shrink-0 rounded-full', status === 'online' && 'live-dot')} style={{ background: color }} />
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('skeleton', className)} />
}

export function EmptyState({ icon: Icon, title, children, action }: { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 px-6 py-8 text-center">
      <div className="flex h-9 w-9 items-center justify-center rounded-md border border-line bg-raised text-faint">
        <Icon size={16} strokeWidth={1.75} />
      </div>
      <div className="text-[13px] font-medium text-fg">{title}</div>
      {children && <div className="max-w-xs text-[12px] leading-relaxed text-muted">{children}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

export function Tooltip({ label, children, side = 'right' }: { label: string; children: ReactNode; side?: 'right' | 'bottom' | 'top' | 'left' }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content side={side} sideOffset={8} className="z-50 rounded-md border border-line-strong bg-raised px-2 py-1 text-[12px] text-fg shadow-lg shadow-black/40">
          {label}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <SwitchPrimitive.Root
      checked={checked}
      onCheckedChange={onChange}
      aria-label={label}
      className="relative h-[18px] w-8 shrink-0 rounded-full border border-line bg-raised transition-colors duration-150 data-[state=checked]:border-accent data-[state=checked]:bg-accent"
    >
      <SwitchPrimitive.Thumb className="block h-3 w-3 translate-x-0.5 rounded-full bg-muted transition-transform duration-150 data-[state=checked]:translate-x-[15px] data-[state=checked]:bg-white" />
    </SwitchPrimitive.Root>
  )
}

export function Select<T extends string>({ value, onChange, options, className }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; className?: string }) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={(v) => onChange(v as T)}>
      <SelectPrimitive.Trigger className={cn('flex h-8 w-full items-center justify-between gap-2 rounded-md border border-line bg-bg px-2.5 text-[13px] text-fg transition-colors duration-150 hover:border-line-strong', className)}>
        <SelectPrimitive.Value />
        <ChevronDown size={14} className="text-faint" />
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content position="popper" sideOffset={4} className="z-50 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-line-strong bg-raised p-1 shadow-xl shadow-black/50">
          <SelectPrimitive.Viewport>
            {options.map((o) => (
              <SelectPrimitive.Item key={o.value} value={o.value} className="flex h-7 cursor-pointer select-none items-center justify-between rounded-sm px-2 text-[13px] text-fg outline-none data-[highlighted]:bg-[#202835]">
                <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator><Check size={13} className="text-accent" /></SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: string; count?: number }[] }) {
  return (
    <div className="flex h-7 items-center rounded-md border border-line bg-bg p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn('flex h-full items-center gap-1.5 rounded-sm px-2 text-[12px] font-medium transition-colors duration-150', value === o.value ? 'bg-raised text-fg' : 'text-muted hover:text-fg')}
        >
          {o.label}
          {o.count !== undefined && <span className="num text-[11px] text-faint">{o.count}</span>}
        </button>
      ))}
    </div>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="num inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-sm border border-line bg-bg px-1 text-[10px] text-muted">{children}</kbd>
}

export const TooltipProvider = TooltipPrimitive.Provider
