import { createContext } from 'react'
import type { Papel, Usuario } from '../api/types'

export interface AuthState {
  usuario: Usuario | null
  carregando: boolean
  /** Há token, mas o servidor não respondeu (ex.: fora do ar): não é motivo para deslogar. */
  semConexao: boolean
  tentarDeNovo: () => void
  entrar: (email: string, senha: string) => Promise<void>
  sair: () => void
  temPapel: (papel: Papel) => boolean
}

export const AuthContext = createContext<AuthState | null>(null)
