import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Pagina, RequisicaoResumo } from '../api/types'
import { BadgeStatus, CabecalhoPagina, Carregando, Cartao, Vazio } from '../components/ui'
import { formatarDataHora } from '../utils/format'

/** Fila de avaliação: da chefia (setores que chefia) e do gestor (estouros de cota e requisições de chefes). */
export function Aprovacoes() {
  const { data, isLoading } = useQuery({
    queryKey: ['requisicoes', 'pendentes'],
    queryFn: async () => (await api.get<Pagina<RequisicaoResumo>>('/requisicoes', { params: { escopo: 'pendentes' } })).data,
  })

  return (
    <>
      <CabecalhoPagina
        titulo="Aprovações"
        subtitulo="Requisições aguardando a sua avaliação. Ninguém avalia a própria requisição: as suas vão para o gestor."
      />
      <Cartao className="overflow-hidden">
        {isLoading ? (
          <Carregando />
        ) : !data?.results.length ? (
          <Vazio>Nada pendente por aqui.</Vazio>
        ) : (
          <ul className="divide-y divide-slate-100">
            {data.results.map((r) => (
              <li key={r.id}>
                <Link to={`/requisicoes/${r.id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 hover:bg-slate-50">
                  <div className="min-w-0">
                    <p className="font-medium text-marca-700">
                      {r.numero} <span className="font-normal text-slate-500">· {r.setor.sigla} · {r.requisitante}</span>
                    </p>
                    <p className="truncate text-sm text-slate-500">
                      {r.total_itens} ite{r.total_itens === 1 ? 'm' : 'ns'} · {r.finalidade || 'sem finalidade informada'} · enviada {formatarDataHora(r.enviado_em)}
                    </p>
                  </div>
                  <span className="flex items-center gap-3">
                    <BadgeStatus status={r.status} />
                    <span className="text-sm font-medium text-marca-600">Avaliar →</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </>
  )
}
