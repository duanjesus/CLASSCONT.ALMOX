import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, lerToken, salvarToken } from '../api/client'
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

  const sair = useCallback(() => {
    salvarToken(null)
    setToken(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    window.addEventListener('almox:logout', sair)
    return () => window.removeEventListener('almox:logout', sair)
  }, [sair])

  const entrar = useCallback(async (email: string, senha: string) => {
    const { data } = await api.post<{ access: string; refresh: string }>('/auth/login', { email, password: senha })
    salvarToken(data.access)
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
