export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

export const classeCampo =
  'block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-marca-500 focus:outline-none focus:ring-2 focus:ring-marca-500/30'
export const classeRotulo = 'mb-1 block text-sm font-medium text-slate-700'

/** Campo numérico compacto (quantidades em tabelas e no carrinho). */
export const classeQuantidade =
  'w-20 rounded-lg border border-slate-300 bg-white px-2 py-1 text-right text-sm tabular-nums shadow-sm focus:border-marca-500 focus:outline-none focus:ring-2 focus:ring-marca-500/30'
