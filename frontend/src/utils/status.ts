import type { StatusRequisicao } from '../api/types'

export const ROTULOS_STATUS: Record<StatusRequisicao, string> = {
  RASCUNHO: 'Rascunho',
  ENVIADA: 'Aguardando aprovação',
  AGUARDANDO_GESTOR: 'Aguardando gestor',
  APROVADA: 'Aprovada',
  RECUSADA: 'Recusada',
  ATENDIDA: 'Atendida',
  ATENDIDA_PARCIALMENTE: 'Atendida parcialmente',
  CANCELADA: 'Cancelada',
}
