import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Pagina, RequisicaoResumo, StatusRequisicao } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { classeCampo, cx } from '../components/estilos'
import { BadgeStatus, Botao, CabecalhoPagina, Carregando, Cartao, Vazio } from '../components/ui'
import { formatarDataHora, formatarMoeda } from '../utils/format'
import { ROTULOS_STATUS } from '../utils/status'

type Escopo = 'minhas' | 'setor'

export function MinhasRequisicoes() {
  const { temPapel } = useAuth()
  const [escopo, setEscopo] = useState<Escopo>('minhas')
  const [status, setStatus] = useState<StatusRequisicao | ''>('')
  const [pagina, setPagina] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['requisicoes', escopo, status, pagina],
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (await api.get<Pagina<RequisicaoResumo>>('/requisicoes', { params: { escopo, status: status || undefined, page: pagina } })).data,
  })
  const totalPaginas = data ? Math.max(1, Math.ceil(data.count / 20)) : 1

  return (
    <>
      <CabecalhoPagina
        titulo={escopo === 'minhas' ? 'Minhas requisições' : 'Requisições do setor'}
        acoes={<Link to="/requisicoes/nova" className="rounded-lg bg-marca-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-marca-600">Nova requisição</Link>}
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        {temPapel('CHEFIA') && (
          <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5 text-sm shadow-sm" role="tablist">
            {(['minhas', 'setor'] as const).map((e) => (
              <button
                key={e}
                role="tab"
                aria-selected={escopo === e}
                className={cx('rounded-md px-3 py-1.5', escopo === e ? 'bg-marca-700 text-white' : 'text-slate-600 hover:bg-slate-50')}
                onClick={() => { setEscopo(e); setPagina(1) }}
              >
                {e === 'minhas' ? 'Minhas' : 'Do meu setor'}
              </button>
            ))}
          </div>
        )}
        <select aria-label="Filtrar por status" className={cx(classeCampo, 'w-auto')} value={status} onChange={(e) => { setStatus(e.target.value as StatusRequisicao | ''); setPagina(1) }}>
          <option value="">Todos os status</option>
          {Object.entries(ROTULOS_STATUS).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>{rotulo}</option>
          ))}
        </select>
      </div>

      <Cartao className="overflow-hidden">
        {isLoading ? (
          <Carregando />
        ) : !data?.results.length ? (
          <Vazio>Nenhuma requisição encontrada.</Vazio>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Número</th>
                  {escopo === 'setor' && <th className="px-4 py-2.5">Requisitante</th>}
                  <th className="px-4 py-2.5">Finalidade</th>
                  <th className="px-4 py-2.5">Criada em</th>
                  <th className="px-4 py-2.5 text-right">Itens</th>
                  <th className="px-4 py-2.5 text-right">Entregue</th>
                  <th className="px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.results.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5"><Link to={`/requisicoes/${r.id}`} className="font-medium text-marca-600 hover:underline">{r.numero}</Link></td>
                    {escopo === 'setor' && <td className="px-4 py-2.5">{r.requisitante}</td>}
                    <td className="max-w-64 truncate px-4 py-2.5 text-slate-500">{r.finalidade || '—'}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">{formatarDataHora(r.criado_em)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{r.total_itens}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatarMoeda(r.valor_atendido)}</td>
                    <td className="px-4 py-2.5"><BadgeStatus status={r.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.count > 20 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-sm">
            <span className="text-slate-500">Página {pagina} de {totalPaginas} · {data.count} requisições</span>
            <div className="flex gap-2">
              <Botao variante="secundario" disabled={!data.previous} onClick={() => setPagina((p) => p - 1)}>← Anterior</Botao>
              <Botao variante="secundario" disabled={!data.next} onClick={() => setPagina((p) => p + 1)}>Próxima →</Botao>
            </div>
          </div>
        )}
      </Cartao>
    </>
  )
}
