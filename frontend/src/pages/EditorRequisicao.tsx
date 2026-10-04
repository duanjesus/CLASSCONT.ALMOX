import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useDeferredValue, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, mensagemErro } from '../api/client'
import type { Categoria, ItemPedido, Material, RequisicaoDetalhe } from '../api/types'
import { classeCampo, classeQuantidade, classeRotulo, cx } from '../components/estilos'
import { Alerta, Botao, CabecalhoPagina, Carregando, Cartao, Vazio } from '../components/ui'
import { formatarMoeda, formatarNumero } from '../utils/format'

interface LinhaCarrinho {
  material: Pick<Material, 'id' | 'codigo' | 'descricao' | 'unidade'> & Partial<Material>
  quantidade: number
}

/** Cria (/requisicoes/nova) ou edita um rascunho (/requisicoes/:id/editar). */
export function EditorRequisicao() {
  const { id } = useParams()
  const { data: existente } = useQuery({
    queryKey: ['requisicao', id],
    enabled: id !== undefined,
    queryFn: async () => (await api.get<RequisicaoDetalhe>(`/requisicoes/${id}`)).data,
  })
  if (id !== undefined && !existente) return <Carregando />
  // key: se trocar de requisição, o formulário é recriado com o novo estado inicial
  return <Formulario key={id ?? 'nova'} existente={existente} />
}

function Formulario({ existente }: { existente?: RequisicaoDetalhe }) {
  const id = existente?.id
  const editando = existente !== undefined
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [busca, setBusca] = useState('')
  const [categoria, setCategoria] = useState('')
  const buscaAdiada = useDeferredValue(busca) // evita uma requisição a cada tecla
  const [carrinho, setCarrinho] = useState<LinhaCarrinho[]>(
    () => existente?.itens.map((i) => ({ material: i.material, quantidade: i.quantidade_solicitada })) ?? [],
  )
  const [finalidade, setFinalidade] = useState(existente?.finalidade ?? '')
  const [erro, setErro] = useState<string | null>(null)

  const { data: categorias = [] } = useQuery({
    queryKey: ['categorias'],
    queryFn: async () => (await api.get<Categoria[]>('/categorias')).data,
  })
  const { data: materiais = [], isLoading } = useQuery({
    queryKey: ['materiais', buscaAdiada, categoria],
    queryFn: async () =>
      (await api.get<Material[]>('/materiais', { params: { busca: buscaAdiada || undefined, categoria: categoria || undefined } })).data,
  })
  const porId = new Map(materiais.map((m) => [m.id, m]))
  const detalhe = (linha: LinhaCarrinho) => porId.get(linha.material.id) ?? linha.material
  const estimativa = carrinho.reduce((soma, l) => soma + l.quantidade * Number(detalhe(l).custo_medio ?? 0), 0)

  // O servidor recusa pedido acima do estoque máximo do material: a tela nem deixa digitar
  const limitar = (quantidade: number, maximo?: number) => Math.min(maximo || Infinity, Math.max(1, quantidade))

  function adicionar(material: Material) {
    setCarrinho((atual) =>
      atual.some((l) => l.material.id === material.id)
        ? atual.map((l) => (l.material.id === material.id ? { ...l, quantidade: limitar(l.quantidade + 1, material.estoque_maximo) } : l))
        : [...atual, { material, quantidade: 1 }],
    )
  }
  const alterar = (materialId: number, quantidade: number) =>
    setCarrinho((atual) => atual.map((l) => (l.material.id === materialId ? { ...l, quantidade } : l)))
  const remover = (materialId: number) => setCarrinho((atual) => atual.filter((l) => l.material.id !== materialId))

  // Trava síncrona: um clique duplo chega antes de o React desabilitar o botão
  const salvando = useRef(false)
  const salvar = useMutation({
    mutationFn: async (enviar: boolean) => {
      const corpo = {
        finalidade,
        itens: carrinho.map<ItemPedido>((l) => ({ material_id: l.material.id, quantidade: l.quantidade })),
      }
      const { data } = editando
        ? await api.put<RequisicaoDetalhe>(`/requisicoes/${id}`, corpo)
        : await api.post<RequisicaoDetalhe>('/requisicoes', corpo)
      if (enviar) await api.post(`/requisicoes/${data.id}/enviar`)
      return data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['requisicoes'] })
      queryClient.invalidateQueries({ queryKey: ['requisicao', String(data.id)] })
      queryClient.invalidateQueries({ queryKey: ['resumo'] })
      navigate(`/requisicoes/${data.id}`)
    },
    onError: (e) => setErro(mensagemErro(e)),
    onSettled: () => {
      salvando.current = false
    },
  })
  function acionar(enviar: boolean) {
    if (salvando.current) return
    salvando.current = true
    setErro(null)
    salvar.mutate(enviar)
  }

  return (
    <>
      <CabecalhoPagina
        titulo={editando ? `Editar requisição ${existente?.numero}` : 'Nova requisição'}
        subtitulo="Escolha os materiais no catálogo. A chefia do seu setor aprova e o almoxarifado separa."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
        <Cartao className="overflow-hidden">
          <div className="flex flex-wrap gap-3 border-b border-slate-200 p-4">
            <input
              type="search"
              placeholder="Buscar por código ou descrição"
              aria-label="Buscar material"
              className={cx(classeCampo, 'min-w-48 flex-1')}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
            <select aria-label="Categoria" className={cx(classeCampo, 'w-auto')} value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              <option value="">Todas as categorias</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>{c.nome}</option>
              ))}
            </select>
          </div>
          {isLoading ? (
            <Carregando />
          ) : !materiais.length ? (
            <Vazio>Nenhum material encontrado.</Vazio>
          ) : (
            <ul className="max-h-[32rem] divide-y divide-slate-100 overflow-y-auto">
              {materiais.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium">{m.descricao}</p>
                    <p className="text-xs text-slate-500">
                      <span className="font-mono">{m.codigo}</span> · {m.categoria} ·{' '}
                      <span className={m.disponivel === 0 ? 'text-red-600' : undefined}>
                        {formatarNumero(m.disponivel)} {m.unidade} disponíve{m.disponivel === 1 ? 'l' : 'is'}
                      </span>
                    </p>
                  </div>
                  <Botao variante="secundario" className="shrink-0 px-3 py-1.5" onClick={() => adicionar(m)} aria-label={`Adicionar ${m.descricao}`}>
                    + Adicionar
                  </Botao>
                </li>
              ))}
            </ul>
          )}
        </Cartao>

        <Cartao className="flex h-fit flex-col p-5 lg:sticky lg:top-6">
          <h2 className="font-semibold">Itens da requisição</h2>
          {!carrinho.length ? (
            <p className="py-6 text-center text-sm text-slate-500">Adicione materiais do catálogo.</p>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100">
              {carrinho.map((linha) => {
                const m = detalhe(linha)
                const acimaDoDisponivel = m.disponivel !== undefined && linha.quantidade > m.disponivel
                return (
                  <li key={linha.material.id} className="py-3 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium">{m.descricao}</p>
                      <button type="button" className="text-xs text-slate-400 hover:text-red-600" onClick={() => remover(linha.material.id)} aria-label={`Remover ${m.descricao}`}>
                        remover
                      </button>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <input
                        type="number"
                        min={1}
                        max={m.estoque_maximo || undefined}
                        aria-label={`Quantidade de ${m.descricao}`}
                        className={classeQuantidade}
                        value={linha.quantidade}
                        onChange={(e) => alterar(linha.material.id, limitar(Number(e.target.value) || 1, m.estoque_maximo))}
                      />
                      <span className="text-xs text-slate-500">
                        {m.unidade}
                        {m.estoque_maximo ? ` · máx. ${m.estoque_maximo}` : ''}
                      </span>
                      <span className="ml-auto text-xs tabular-nums text-slate-500">{formatarMoeda(linha.quantidade * Number(m.custo_medio ?? 0))}</span>
                    </div>
                    {acimaDoDisponivel && (
                      <p className="mt-1 text-xs text-amber-700">Acima do disponível ({m.disponivel}): pode ser atendido parcialmente.</p>
                    )}
                  </li>
                )
              })}
            </ul>
          )}

          <div className="mt-2 flex justify-between border-t border-slate-200 pt-3 text-sm">
            <span className="text-slate-500">Valor estimado</span>
            <span className="font-semibold tabular-nums">{formatarMoeda(estimativa)}</span>
          </div>

          <label htmlFor="finalidade" className={cx(classeRotulo, 'mt-4')}>Finalidade (opcional)</label>
          <textarea
            id="finalidade"
            rows={2}
            maxLength={300}
            className={classeCampo}
            placeholder="Ex.: reposição das impressoras do 2º andar"
            value={finalidade}
            onChange={(e) => setFinalidade(e.target.value)}
          />

          {erro && <div className="mt-4"><Alerta>{erro}</Alerta></div>}

          <div className="mt-4 grid gap-2">
            <Botao disabled={!carrinho.length || salvar.isPending} carregando={salvar.isPending && salvar.variables === true} onClick={() => acionar(true)}>
              Enviar para aprovação
            </Botao>
            <Botao variante="secundario" disabled={!carrinho.length || salvar.isPending} carregando={salvar.isPending && salvar.variables === false} onClick={() => acionar(false)}>
              Salvar rascunho
            </Botao>
            {editando && <Link to={`/requisicoes/${id}`} className="text-center text-sm text-slate-500 hover:underline">Cancelar edição</Link>}
          </div>
        </Cartao>
      </div>
    </>
  )
}
