import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import type { ConsumoSetor as Consumo } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { classeCampo, cx } from '../components/estilos'
import { BarraCota, CabecalhoPagina, Carregando, Cartao, Indicador, SeletorCompetencia, Vazio } from '../components/ui'
import { competenciaAtual, formatarMoeda, formatarNumero } from '../utils/format'

export function ConsumoSetor() {
  const { usuario } = useAuth()
  const setores = usuario?.setores_chefiados ?? []
  const [setorId, setSetorId] = useState(setores[0]?.id)
  const [competencia, setCompetencia] = useState(competenciaAtual())

  const { data, isLoading } = useQuery({
    queryKey: ['consumo', setorId, competencia],
    enabled: setorId !== undefined,
    queryFn: async () => (await api.get<Consumo>(`/setores/${setorId}/consumo`, { params: { competencia } })).data,
  })

  const disponivel = data && data.cota.disponivel !== null ? Number(data.cota.disponivel) : null

  return (
    <>
      <CabecalhoPagina
        titulo="Consumo do setor"
        subtitulo="Material entregue ao setor no mês (pelo custo médio) e a situação da cota."
        acoes={
          <>
            {setores.length > 1 && (
              <select aria-label="Setor" className={cx(classeCampo, 'w-auto')} value={setorId} onChange={(e) => setSetorId(Number(e.target.value))}>
                {setores.map((s) => (
                  <option key={s.id} value={s.id}>{s.sigla}</option>
                ))}
              </select>
            )}
            <SeletorCompetencia valor={competencia} onChange={setCompetencia} maximo={competenciaAtual()} />
          </>
        }
      />

      {isLoading || !data ? (
        <Carregando />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Indicador rotulo="Cota mensal" valor={data.cota.cota === null ? 'Sem limite' : formatarMoeda(data.cota.cota)} />
            <Indicador rotulo="Consumido" valor={formatarMoeda(data.cota.consumido)} detalhe={`${data.atendidas} requisição(ões) atendida(s)`} />
            <Indicador rotulo="Comprometido" valor={formatarMoeda(data.cota.comprometido)} detalhe="aprovado, ainda não entregue" />
            <Indicador
              rotulo="Disponível"
              valor={disponivel === null ? '—' : formatarMoeda(disponivel)}
              destaque={disponivel === null ? undefined : disponivel < 0 ? 'negativo' : 'positivo'}
              detalhe={data.aguardando_avaliacao ? `${data.aguardando_avaliacao} aguardando avaliação` : undefined}
            />
          </div>

          <Cartao className="mt-6 p-5">
            <BarraCota cota={data.cota} />
          </Cartao>

          <Cartao className="mt-6 overflow-hidden">
            <h2 className="border-b border-slate-200 px-4 py-3 font-semibold">Materiais consumidos</h2>
            {!data.materiais.length ? (
              <Vazio>Nenhum material entregue ao setor neste mês.</Vazio>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5">Material</th>
                      <th className="px-4 py-2.5 text-right">Quantidade</th>
                      <th className="px-4 py-2.5 text-right">Valor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.materiais.map((m) => (
                      <tr key={m.codigo}>
                        <td className="px-4 py-2.5"><span className="font-mono text-xs text-slate-500">{m.codigo}</span> {m.descricao}</td>
                        <td className="px-4 py-2.5 text-right tabular-nums">{formatarNumero(m.quantidade)} {m.unidade}</td>
                        <td className="px-4 py-2.5 text-right tabular-nums">{formatarMoeda(m.valor)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Cartao>
        </>
      )}
    </>
  )
}
