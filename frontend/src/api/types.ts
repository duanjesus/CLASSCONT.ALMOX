// Contrato da API (DRF). Os campos seguem o snake_case do Django;
// valores monetários chegam como string (Decimal) para não perder precisão.

export type Papel = 'SERVIDOR' | 'CHEFIA' | 'ALMOXARIFE' | 'GESTOR'
export type Perfil = 'SERVIDOR' | 'ALMOXARIFE' | 'GESTOR'

export interface SetorResumo {
  id: number
  sigla: string
  nome: string
}

export interface Usuario {
  id: number
  nome: string
  email: string
  matricula: string
  cargo: string
  setor: SetorResumo | null
  perfil: Perfil
  papeis: Papel[]
  eh_chefia: boolean
  setores_chefiados: SetorResumo[]
}

export interface Categoria {
  id: number
  nome: string
}

export interface Material {
  id: number
  codigo: string
  descricao: string
  categoria: string
  unidade: string
  unidade_rotulo: string
  disponivel: number
  estoque_maximo: number
  custo_medio: string
}

export type StatusRequisicao =
  | 'RASCUNHO'
  | 'ENVIADA'
  | 'AGUARDANDO_GESTOR'
  | 'APROVADA'
  | 'RECUSADA'
  | 'ATENDIDA'
  | 'ATENDIDA_PARCIALMENTE'
  | 'CANCELADA'

export type AcaoRequisicao = 'editar' | 'enviar' | 'cancelar' | 'aprovar' | 'recusar' | 'atender' | 'guia_pdf'

export interface ItemRequisicao {
  id: number
  material: Pick<Material, 'id' | 'codigo' | 'descricao' | 'unidade' | 'custo_medio'>
  quantidade_solicitada: number
  quantidade_aprovada: number | null
  quantidade_reservada: number
  quantidade_atendida: number | null
  custo_unitario: string | null
  valor_atendido: string | null
}

export interface EventoHistorico {
  id: number
  de_status: StatusRequisicao | ''
  para_status: StatusRequisicao
  para_status_rotulo: string
  usuario: string
  quando: string
  observacao: string
}

export interface RequisicaoResumo {
  id: number
  numero: string
  status: StatusRequisicao
  status_rotulo: string
  setor: SetorResumo
  requisitante: string
  finalidade: string
  criado_em: string
  enviado_em: string | null
  atendido_em: string | null
  total_itens: number
  valor_atendido: string | null
}

export interface RequisicaoDetalhe extends RequisicaoResumo {
  itens: ItemRequisicao[]
  historico: EventoHistorico[]
  valor_estimado: string
  acoes: AcaoRequisicao[]
}

export interface Pagina<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Resumo {
  minhas_por_status: Partial<Record<StatusRequisicao, number>>
  pendentes_avaliacao: number
}

export interface SituacaoCota {
  cota: string | null
  consumido: string
  comprometido: string
  disponivel: string | null
  percentual_utilizado: string | null
}

export interface ConsumoSetor {
  setor: SetorResumo
  competencia: string
  cota: SituacaoCota
  materiais: { codigo: string; descricao: string; unidade: string; quantidade: number; valor: string }[]
  requisicoes_por_status: Partial<Record<StatusRequisicao, number>>
  aguardando_avaliacao: number
  atendidas: number
}

export interface ItemPedido {
  material_id: number
  quantidade: number
}

export interface ErroApi {
  erro: string
  detalhes?: Record<string, string>
}
