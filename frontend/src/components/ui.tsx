import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { SituacaoCota, StatusRequisicao } from '../api/types'
import { deslocarCompetencia, formatarMoeda, nomeCompetencia } from '../utils/format'
import { ROTULOS_STATUS } from '../utils/status'
import { cx } from './estilos'

type Variante = 'primario' | 'secundario' | 'perigo' | 'fantasma'

const variantes: Record<Variante, string> = {
  primario: 'bg-marca-700 text-white hover:bg-marca-600 shadow-sm',
  secundario: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 shadow-sm',
  perigo: 'bg-red-600 text-white hover:bg-red-700 shadow-sm',
  fantasma: 'text-slate-600 hover:bg-slate-100',
}

export function Botao({
  variante = 'primario',
  carregando = false,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; carregando?: boolean }) {
  return (
    <button
      {...props}
      disabled={disabled || carregando}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-marca-500 focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variantes[variante],
        className,
      )}
    >
      {carregando && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  )
}

export function Cartao({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>{children}</div>
}

export function CabecalhoPagina({ titulo, subtitulo, acoes }: { titulo: ReactNode; subtitulo?: ReactNode; acoes?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold text-slate-900">{titulo}</h1>
        {subtitulo && <p className="mt-1 text-sm text-slate-500">{subtitulo}</p>}
      </div>
      {acoes && <div className="flex flex-wrap items-center gap-3">{acoes}</div>}
    </div>
  )
}

export function Spinner({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg className={cx('animate-spin text-current', className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z" />
    </svg>
  )
}

export function Carregando({ texto = 'Carregando…' }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-slate-500" role="status">
      <Spinner className="h-5 w-5 text-marca-500" /> {texto}
    </div>
  )
}

export function Vazio({ children }: { children: ReactNode }) {
  return <div className="px-6 py-12 text-center text-sm text-slate-500">{children}</div>
}

export function Alerta({ tipo = 'erro', children }: { tipo?: 'erro' | 'sucesso' | 'aviso'; children: ReactNode }) {
  const cores = {
    erro: 'border-red-200 bg-red-50 text-red-800',
    sucesso: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    aviso: 'border-amber-200 bg-amber-50 text-amber-900',
  }
  return (
    <div role={tipo === 'erro' ? 'alert' : 'status'} className={cx('rounded-lg border px-4 py-3 text-sm', cores[tipo])}>
      {children}
    </div>
  )
}

const coresStatus: Record<StatusRequisicao, string> = {
  RASCUNHO: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  ENVIADA: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  AGUARDANDO_GESTOR: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  APROVADA: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  RECUSADA: 'bg-red-50 text-red-700 ring-red-600/20',
  ATENDIDA: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  ATENDIDA_PARCIALMENTE: 'bg-teal-50 text-teal-700 ring-teal-600/20',
  CANCELADA: 'bg-slate-100 text-slate-500 ring-slate-500/20',
}

export function BadgeStatus({ status }: { status: StatusRequisicao }) {
  return (
    <span className={cx('inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', coresStatus[status])}>
      {ROTULOS_STATUS[status]}
    </span>
  )
}

export function SeletorCompetencia({ valor, onChange, maximo }: { valor: string; onChange: (c: string) => void; maximo?: string }) {
  const proxima = deslocarCompetencia(valor, 1)
  const bloqueiaProxima = maximo !== undefined && proxima > maximo
  return (
    <div className="inline-flex items-center rounded-lg border border-slate-300 bg-white text-sm shadow-sm">
      <button type="button" className="px-3 py-2 text-slate-500 hover:text-marca-700" onClick={() => onChange(deslocarCompetencia(valor, -1))} aria-label="Mês anterior">
        ←
      </button>
      <span className="min-w-40 border-x border-slate-200 px-3 py-2 text-center font-medium first-letter:uppercase">{nomeCompetencia(valor)}</span>
      <button
        type="button"
        className="px-3 py-2 text-slate-500 hover:text-marca-700 disabled:opacity-30"
        onClick={() => onChange(proxima)}
        disabled={bloqueiaProxima}
        aria-label="Próximo mês"
      >
        →
      </button>
    </div>
  )
}

export function Indicador({ rotulo, valor, detalhe, destaque }: { rotulo: string; valor: ReactNode; detalhe?: ReactNode; destaque?: 'positivo' | 'negativo' | 'atencao' }) {
  return (
    <Cartao className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{rotulo}</p>
      <p
        className={cx(
          'mt-1 text-2xl font-semibold tabular-nums',
          destaque === 'positivo' && 'text-emerald-700',
          destaque === 'negativo' && 'text-red-600',
          destaque === 'atencao' && 'text-amber-600',
          !destaque && 'text-slate-900',
        )}
      >
        {valor}
      </p>
      {detalhe && <p className="mt-0.5 text-xs text-slate-500">{detalhe}</p>}
    </Cartao>
  )
}

/** Barra de utilização da cota: consumido (sólido) + comprometido (hachurado) + estimativa opcional. */
export function BarraCota({ cota, estimativa }: { cota: SituacaoCota; estimativa?: number }) {
  if (cota.cota === null) return <p className="text-sm text-slate-500">Setor sem limite de cota mensal.</p>
  const total = Number(cota.cota)
  const pct = (v: number) => (total > 0 ? Math.min(100, (v / total) * 100) : 0)
  const consumido = Number(cota.consumido)
  const comprometido = Number(cota.comprometido)
  const extra = estimativa ?? 0
  const utilizado = consumido + comprometido + extra
  const estoura = utilizado > total
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`Cota utilizada: ${formatarMoeda(utilizado)} de ${formatarMoeda(total)}`}>
        <div className="bg-marca-500" style={{ width: `${pct(consumido)}%` }} />
        <div className="bg-sky-400" style={{ width: `${pct(comprometido)}%` }} />
        {extra > 0 && <div className={estoura ? 'bg-red-500' : 'bg-amber-400'} style={{ width: `${pct(extra)}%` }} />}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-marca-500" />Consumido {formatarMoeda(consumido)}</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-sky-400" />Comprometido {formatarMoeda(comprometido)}</span>
        {extra > 0 && (
          <span><span className={cx('mr-1 inline-block h-2 w-2 rounded-full', estoura ? 'bg-red-500' : 'bg-amber-400')} />Esta requisição {formatarMoeda(extra)}</span>
        )}
        <span className="ml-auto font-medium">Cota {formatarMoeda(total)}</span>
      </div>
    </div>
  )
}
