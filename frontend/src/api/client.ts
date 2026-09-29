import axios, { type AxiosError } from 'axios'
import type { ErroApi } from './types'

export const TOKEN_KEY = 'almox.token'

export function lerToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function salvarToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage indisponível: a sessão fica só em memória */
  }
}

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = lerToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    // Token expirado ou usuário desativado: volta para o login
    if (error.response?.status === 401 && !error.config?.url?.endsWith('/auth/login')) {
      salvarToken(null)
      window.dispatchEvent(new Event('almox:logout'))
    }
    return Promise.reject(error)
  },
)

/** Mensagem do erro padronizado pela API: { erro, detalhes? }. */
export function mensagemErro(error: unknown): string {
  if (axios.isAxiosError<ErroApi>(error)) {
    const dados = error.response?.data
    if (dados?.detalhes) return Object.values(dados.detalhes).join(' ')
    if (dados?.erro) return dados.erro
    if (error.response?.status === 403) return 'Você não tem permissão para esta ação.'
  }
  return 'Não foi possível completar a operação. Tente novamente.'
}

/**
 * Baixa um PDF autenticado e abre em nova aba. A aba é aberta ANTES do await:
 * o navegador só libera pop-up disparado diretamente pelo clique.
 */
export async function abrirPdf(url: string): Promise<void> {
  const aba = window.open('', '_blank')
  try {
    const resp = await api.get<Blob>(url, { responseType: 'blob' })
    const href = URL.createObjectURL(resp.data)
    if (aba) aba.location.href = href
    else window.location.href = href
    setTimeout(() => URL.revokeObjectURL(href), 60_000)
  } catch (erro) {
    aba?.close()
    throw erro
  }
}

/** Endereço do painel do almoxarifado (templates Django). */
export const URL_PAINEL = import.meta.env.VITE_PAINEL_URL ?? 'http://localhost:8082/painel/'
