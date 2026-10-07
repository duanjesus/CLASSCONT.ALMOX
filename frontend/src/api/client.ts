import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ErroApi } from './types'

export const TOKEN_KEY = 'almox.token'
const REFRESH_KEY = 'almox.refresh'

function ler(chave: string): string | null {
  try {
    return localStorage.getItem(chave)
  } catch {
    return null
  }
}

function gravar(chave: string, valor: string | null): void {
  try {
    if (valor) localStorage.setItem(chave, valor)
    else localStorage.removeItem(chave)
  } catch {
    /* storage indisponível: a sessão fica só em memória */
  }
}

export const lerToken = () => ler(TOKEN_KEY)
export const lerRefresh = () => ler(REFRESH_KEY)

/** Guarda (ou apaga, com null) o par de tokens da sessão. */
export function salvarSessao(tokens: { access: string; refresh: string } | null): void {
  gravar(TOKEN_KEY, tokens?.access ?? null)
  gravar(REFRESH_KEY, tokens?.refresh ?? null)
}

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = lerToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// O access dura 15 min. Quando ele expira (401), trocamos o refresh por um par novo
// e repetimos a requisição, sem o usuário perceber. A renovação é única mesmo com
// várias requisições falhando juntas: o refresh é rotativo e só vale uma vez.
let renovacao: Promise<string> | null = null

function renovarAcesso(): Promise<string> {
  renovacao ??= axios
    .post<{ access: string; refresh: string }>('/api/auth/refresh', { refresh: lerRefresh() })
    .then(({ data }) => {
      salvarSessao(data)
      return data.access
    })
    .finally(() => {
      renovacao = null
    })
  return renovacao
}

function encerrarSessao(): void {
  salvarSessao(null)
  window.dispatchEvent(new Event('almox:logout'))
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { repetida?: boolean }) | undefined
    const expirou = error.response?.status === 401 && !original?.url?.startsWith('/auth/')
    if (!expirou || !original) return Promise.reject(error)

    // Já repetimos com token novo e ainda deu 401 (ex.: usuário desativado), ou não há refresh
    if (original.repetida || !lerRefresh()) {
      encerrarSessao()
      return Promise.reject(error)
    }
    try {
      const access = await renovarAcesso()
      original.repetida = true
      original.headers.Authorization = `Bearer ${access}`
      return api(original)
    } catch {
      encerrarSessao() // refresh expirado, já usado ou revogado: volta para o login
      return Promise.reject(error)
    }
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
