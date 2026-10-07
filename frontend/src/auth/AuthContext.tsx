import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, lerRefresh, lerToken, salvarSessao } from '../api/client'
import type { Usuario } from '../api/types'
import { AuthContext, type AuthState } from './contexto'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = useState<string | null>(lerToken)

  const { data: usuario, isLoading, isError, refetch } = useQuery({
    queryKey: ['me', token],
    queryFn: async () => (await api.get<Usuario>('/me')).data,
    enabled: !!token,
    // 401 já desloga (interceptor); outras falhas (rede, servidor reiniciando) tentam de novo
    retry: (tentativas, erro) => !(axios.isAxiosError(erro) && erro.response?.status === 401) && tentativas < 3,
  })

  // Limpa a sessão local (usado também quando o servidor recusa o refresh)
  const limpar = useCallback(() => {
    salvarSessao(null)
    setToken(null)
    queryClient.clear()
  }, [queryClient])

  // Logout pedido pelo usuário: além de limpar, invalida o refresh no servidor (blacklist)
  const sair = useCallback(() => {
    const refresh = lerRefresh()
    if (refresh) api.post('/auth/logout', { refresh }).catch(() => undefined)
    limpar()
  }, [limpar])

  useEffect(() => {
    window.addEventListener('almox:logout', limpar)
    return () => window.removeEventListener('almox:logout', limpar)
  }, [limpar])

  const entrar = useCallback(async (email: string, senha: string) => {
    const { data } = await api.post<{ access: string; refresh: string }>('/auth/login', { email, password: senha })
    salvarSessao(data)
    setToken(data.access)
  }, [])

  const valor = useMemo<AuthState>(
    () => ({
      usuario: token ? (usuario ?? null) : null,
      carregando: !!token && isLoading,
      semConexao: !!token && isError,
      tentarDeNovo: () => void refetch(),
      entrar,
      sair,
      temPapel: (papel) => !!usuario?.papeis.includes(papel),
    }),
    [token, usuario, isLoading, isError, refetch, entrar, sair],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}
