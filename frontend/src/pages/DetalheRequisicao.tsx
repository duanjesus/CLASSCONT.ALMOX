import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { abrirPdf, api, mensagemErro } from '../api/client'
import type { ConsumoSetor, RequisicaoDetalhe } from '../api/types'
import { classeCampo, classeQuantidade, classeRotulo, cx } from '../components/estilos'
import { Alerta, BadgeStatus, BarraCota, Botao, CabecalhoPagina, Carregando, Cartao } from '../components/ui'
import { formatarDataHora, formatarMoeda, formatarNumero } from '../utils/format'

export function DetalheRequisicao() {
  const { id } = useParams()
  const queryClient = useQueryClient()
  const [erro, setErro] = useState<string | null>(null)
  const [aprovadas, setAprovadas] = useState<Record<number, number>>({})
  const [observacao, setObservacao] = useState('')
  const [motivo, setMotivo] = useState('')
  const [recusando, setRecusando] = useState(false)

  const { data: r, isLoading } = useQuery({
    queryKey: ['requisicao', id],
    queryFn: async () => (await api.get<RequisicaoDetalhe>(`/requisicoes/${id}`)).data,
  })
  const avaliando = !!r?.acoes.includes('aprovar')

  // Quem avalia vê o impacto na cota do setor
  const { data: consumo } = useQuery({
    queryKey: ['consumo', r?.setor.id, 'atual'],
    enabled: avaliando,
    queryFn: async () => (await api.get<ConsumoSetor>(`/setores/${r!.setor.id}/consumo`)).data,
  })

  const acao = useMutation({
    mutationFn: async ({ caminho, corpo }: { caminho: string; corpo?: object }) =>
      (await api.post<RequisicaoDetalhe>(`/requisicoes/${id}/${caminho}`, corpo ?? {})).data,
    onSuccess: (dados) => {
      queryClient.setQueryData(['requisicao', id], dados)
      queryClient.invalidateQueries({ queryKey: ['requisicoes'] })
      queryClient.invalidateQueries({ queryKey: ['resumo'] })
      queryClient.invalidateQueries({ queryKey: ['consumo'] })
      setRecusando(false)
      setErro(null)
    },
    onError: (e) => setErro(mensagemErro(e)),
  })

  if (isLoading) return <Carregando />
  if (!r) return <Alerta>Requisição não encontrada ou sem acesso.</Alerta>

  const quantidadeAprovada = (itemId: number, padrao: number) => aprovadas[itemId] ?? padrao
  // Estimativa com as quantidades que o avaliador está digitando × custo médio atual
  const estimativa = r.itens.reduce(
    (soma, i) => soma + quantidadeAprovada(i.id, i.quantidade_aprovada ?? i.quantidade_solicitada) * Number(i.material.custo_medio),
    0,
  )

  function aprovar() {
    const itens = r!.itens.map((i) => ({ id: i.id, quantidade: quantidadeAprovada(i.id, i.quantidade_aprovada ?? i.quantidade_solicitada) }))
    acao.mutate({ caminho: 'aprovar', corpo: { itens, observacao } })
  }

  return (
    <>
      <Link to="/requisicoes" className="text-sm text-slate-500 hover:text-marca-700">← Requisições</Link>
      <CabecalhoPagina
        titulo={
          <span className="flex flex-wrap items-center gap-3">
            Requisição {r.numero} <BadgeStatus status={r.status} />
          </span>
        }
        subtitulo={`${r.setor.sigla} · ${r.requisitante}${r.finalidade ? ` · ${r.finalidade}` : ''}`}
        acoes={
          <>
            {r.acoes.includes('guia_pdf') && (
              <Botao variante="secundario" onClick={() => abrirPdf(`/requisicoes/${r.id}/guia`).catch((e) => setErro(mensagemErro(e)))}>
                Guia de saída (PDF)
              </Botao>
            )}
            {r.acoes.includes('editar') && (
              <Link to={`/requisicoes/${r.id}/editar`} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
                Editar
              </Link>
            )}
            {r.acoes.includes('cancelar') && (
              <Botao
                variante="fantasma"
                carregando={acao.isPending && acao.variables?.caminho === 'cancelar'}
                onClick={() => window.confirm('Cancelar esta requisição?') && acao.mutate({ caminho: 'cancelar' })}
              >
                Cancelar
              </Botao>
            )}
            {r.acoes.includes('enviar') && (
              <Botao carregando={acao.isPending && acao.variables?.caminho === 'enviar'} onClick={() => acao.mutate({ caminho: 'enviar' })}>
                Enviar para aprovação
              </Botao>
            )}
          </>
        }
      />

      {erro && <div className="mb-4"><Alerta>{erro}</Alerta></div>}
      {r.status === 'AGUARDANDO_GESTOR' && !avaliando && (
        <div className="mb-4"><Alerta tipo="aviso">A chefia aprovou, mas o valor passa da cota mensal do setor: aguardando autorização do gestor.</Alerta></div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Cartao className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Material</th>
                  <th className="px-4 py-2.5 text-right">Solicitada</th>
                  <th className="px-4 py-2.5 text-right">Aprovada</th>
                  <th className="px-4 py-2.5 text-right">Entregue</th>
                  <th className="px-4 py-2.5 text-right">Valor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {r.itens.map((i) => (
                  <tr key={i.id}>
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs text-slate-500">{i.material.codigo}</span> {i.material.descricao}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatarNumero(i.quantidade_solicitada)} {i.material.unidade}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      {avaliando ? (
                        <input
                          type="number"
                          min={0}
                          max={i.quantidade_aprovada ?? i.quantidade_solicitada}
                          aria-label={`Quantidade aprovada de ${i.material.descricao}`}
                          className={classeQuantidade}
                          value={quantidadeAprovada(i.id, i.quantidade_aprovada ?? i.quantidade_solicitada)}
                          onChange={(e) => setAprovadas((a) => ({ ...a, [i.id]: Math.max(0, Number(e.target.value) || 0) }))}
                        />
                      ) : (
                        i.quantidade_aprovada ?? '—'
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{i.quantidade_atendida ?? '—'}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{formatarMoeda(i.valor_atendido)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-slate-200 font-medium">
                <tr>
                  <td className="px-4 py-3" colSpan={4}>{r.valor_atendido !== null ? 'Total entregue' : 'Valor estimado (custo médio atual)'}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatarMoeda(r.valor_atendido ?? r.valor_estimado)}</td>
                </tr>
              </tfoot>
            </table>
          </Cartao>

          {avaliando && (
            <Cartao className="p-5">
              <h2 className="font-semibold">Avaliação</h2>
              <p className="mb-4 text-sm text-slate-500">
                Você pode reduzir as quantidades acima. Ao aprovar, o saldo fica reservado para o setor.
                {r.status === 'ENVIADA' && ' Se passar da cota mensal, a requisição sobe para o gestor.'}
              </p>
              {consumo && (
                <div className="mb-5 rounded-lg bg-slate-50 p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Cota da {consumo.setor.sigla} neste mês</p>
                  <BarraCota cota={consumo.cota} estimativa={estimativa} />
                </div>
              )}

              {!recusando ? (
                <>
                  <label htmlFor="observacao" className={classeRotulo}>Observação (opcional)</label>
                  <textarea id="observacao" rows={2} className={classeCampo} value={observacao} onChange={(e) => setObservacao(e.target.value)} />
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Botao carregando={acao.isPending && acao.variables?.caminho === 'aprovar'} onClick={aprovar}>Aprovar</Botao>
                    <Botao variante="secundario" onClick={() => setRecusando(true)}>Recusar…</Botao>
                  </div>
                </>
              ) : (
                <>
                  <label htmlFor="motivo" className={classeRotulo}>Motivo da recusa</label>
                  <textarea id="motivo" rows={3} className={classeCampo} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Botao
                      variante="perigo"
                      disabled={motivo.trim().length < 5}
                      carregando={acao.isPending && acao.variables?.caminho === 'recusar'}
                      onClick={() => acao.mutate({ caminho: 'recusar', corpo: { motivo } })}
                    >
                      Confirmar recusa
                    </Botao>
                    <Botao variante="fantasma" onClick={() => setRecusando(false)}>Voltar</Botao>
                  </div>
                </>
              )}
            </Cartao>
          )}
        </div>

        <Cartao className="h-fit p-5">
          <h2 className="mb-4 font-semibold">Histórico</h2>
          <ol className="relative space-y-5 border-l border-slate-200 pl-5">
            {r.historico.map((h, i) => (
              <li key={h.id}>
                <span className={cx('absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white', i === r.historico.length - 1 ? 'bg-marca-600' : 'bg-slate-300')} />
                <p className="text-sm font-medium">{h.para_status_rotulo}</p>
                <p className="text-xs text-slate-500">{formatarDataHora(h.quando)} · {h.usuario}</p>
                {h.observacao && <p className="mt-1 rounded bg-slate-50 px-2 py-1 text-xs text-slate-600">{h.observacao}</p>}
              </li>
            ))}
          </ol>
        </Cartao>
      </div>
    </>
  )
}
