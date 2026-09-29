const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const inteiro = new Intl.NumberFormat('pt-BR')

/** Aceita número ou o Decimal serializado como string pela API ("27.9000"). */
export function formatarMoeda(valor: number | string | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return moeda.format(Number(valor))
}

export const formatarNumero = (valor: number) => inteiro.format(valor)

/** "2026-09-27" → "27/09/2026" */
export function formatarData(iso: string | null): string {
  if (!iso) return '—'
  const [a, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${a}`
}

export function formatarDataHora(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/** Competência atual no formato AAAA-MM. */
export function competenciaAtual(): string {
  const hoje = new Date()
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}`
}

/** "2026-09" → "setembro de 2026" */
export function nomeCompetencia(competencia: string): string {
  const [a, m] = competencia.split('-').map(Number)
  return new Date(a, m - 1, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })
}

export function deslocarCompetencia(competencia: string, meses: number): string {
  const [a, m] = competencia.split('-').map(Number)
  const d = new Date(a, m - 1 + meses, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
