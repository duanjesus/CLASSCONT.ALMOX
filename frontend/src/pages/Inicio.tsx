import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ConsumoSetor, Pagina, RequisicaoResumo, Resumo } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { BadgeStatus, BarraCota, CabecalhoPagina, Carregando, Cartao, Indicador, Vazio } from '../components/ui'
import { formatarDataHora } from '../utils/format'

export function Inicio() {
  const { usuario, temPapel } = useAuth()
  const setorChefiado = usuario?.setores_chefiados[0]

  const { data: resumo } = useQuery({
    queryKey: ['resumo'],
    queryFn: async () => (await api.get<Resumo>('/resumo')).data,
  })
  const { data: recentes, isLoading } = useQuery({
    queryKey: ['requisicoes', 'minhas', 'recentes'],
    queryFn: async () => (await api.get<Pagina<RequisicaoResumo>>('/requisicoes', { params: { escopo: 'minhas' } })).data,
  })
  const { data: consumo } = useQuery({
    queryKey: ['consumo', setorChefiado?.id, 'atual'],
    enabled: !!setorChefiado,
    queryFn: async () => (await api.get<ConsumoSetor>(`/setores/${setorChefiado!.id}/consumo`)).data,
  })

  const n = resumo?.minhas_por_status ?? {}
  const emAvaliacao = (n.ENVIADA ?? 0) + (n.AGUARDANDO_GESTOR ?? 0)
  const primeiroNome = usuario?.nome.split(' ')[0]

  return (
    <>
      <CabecalhoPagina
        titulo={`Olá, ${primeiroNome}`}
        subtitulo={`${usuario?.setor?.nome ?? ''} · matrícula ${usuario?.matricula}`}
        acoes={<Link to="/requisicoes/nova" className="rounded-lg bg-marca-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-marca-600">Nova requisição</Link>}
      />

      {(temPapel('CHEFIA') || temPapel('GESTOR')) && (resumo?.pendentes_avaliacao ?? 0) > 0 && (
        <Link to="/aprovacoes" className="mb-6 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-900 hover:bg-amber-100">
          <span>
            <strong>{resumo!.pendentes_avaliacao}</strong> requisiç{resumo!.pendentes_avaliacao === 1 ? 'ão aguarda' : 'ões aguardam'} a sua aprovação.
          </span>
          <span className="text-sm font-medium">Avaliar →</span>
        </Link>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Indicador rotulo="Rascunhos" valor={n.RASCUNHO ?? 0} detalhe="ainda não enviados" />
        <Indicador rotulo="Em avaliação" valor={emAvaliacao} detalhe="chefia ou gestor" destaque={emAvaliacao ? 'atencao' : undefined} />
        <Indicador rotulo="Aprovadas" valor={n.APROVADA ?? 0} detalhe="aguardando o almoxarifado" />
        <Indicador rotulo="Atendidas" valor={(n.ATENDIDA ?? 0) + (n.ATENDIDA_PARCIALMENTE ?? 0)} detalhe="material entregue" destaque="positivo" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Cartao className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <h2 className="font-semibold">Minhas últimas requisições</h2>
            <Link to="/requisicoes" className="text-sm font-medium text-marca-600 hover:underline">Ver todas</Link>
          </div>
          {isLoading ? (
            <Carregando />
          ) : !recentes?.results.length ? (
            <Vazio>
              Você ainda não fez requisições. <Link to="/requisicoes/nova" className="font-medium text-marca-600 hover:underline">Fazer a primeira</Link>
            </Vazio>
          ) : (
            <ul className="divide-y divide-slate-100">
              {recentes.results.slice(0, 6).map((r) => (
                <li key={r.id}>
                  <Link to={`/requisicoes/${r.id}`} className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-slate-50">
                    <span className="min-w-0">
                      <span className="font-medium text-marca-700">{r.numero}</span>
                      <span className="block truncate text-xs text-slate-500">
                        {r.total_itens} ite{r.total_itens === 1 ? 'm' : 'ns'} · {r.finalidade || 'sem finalidade'} · {formatarDataHora(r.criado_em)}
                      </span>
                    </span>
                    <BadgeStatus status={r.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Cartao>

        {consumo && (
          <Cartao className="p-5">
            <h2 className="font-semibold">Cota da {consumo.setor.sigla} neste mês</h2>
            <p className="mb-4 text-xs text-slate-500">Consumido + aprovado ainda não entregue.</p>
            <BarraCota cota={consumo.cota} />
            <Link to="/setor" className="mt-4 inline-block text-sm font-medium text-marca-600 hover:underline">Detalhes do consumo →</Link>
          </Cartao>
        )}
      </div>
    </>
  )
}
