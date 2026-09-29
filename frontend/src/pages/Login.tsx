import axios from 'axios'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { mensagemErro, URL_PAINEL } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { classeCampo, classeRotulo } from '../components/estilos'
import { Alerta, Botao } from '../components/ui'

export function Login() {
  const { usuario, entrar } = useAuth()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (usuario) return <Navigate to="/" replace />

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      await entrar(email, senha)
    } catch (err) {
      setErro(axios.isAxiosError(err) && err.response?.status === 401 ? 'E-mail ou senha inválidos.' : mensagemErro(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-marca-900 to-marca-700 px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center text-white">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-white/10 text-sm font-bold text-destaque">ALM</span>
          <h1 className="mt-4 text-2xl font-semibold">CLASSCONT.ALMOX</h1>
          <p className="mt-1 text-sm text-marca-100/80">Requisições de material do almoxarifado</p>
        </div>

        <form onSubmit={enviar} className="space-y-4 rounded-xl bg-white p-6 shadow-xl">
          {erro && <Alerta>{erro}</Alerta>}
          <div>
            <label htmlFor="email" className={classeRotulo}>E-mail</label>
            <input id="email" type="email" required autoFocus autoComplete="email" className={classeCampo} value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label htmlFor="senha" className={classeRotulo}>Senha</label>
            <input id="senha" type="password" required autoComplete="current-password" className={classeCampo} value={senha} onChange={(e) => setSenha(e.target.value)} />
          </div>
          <Botao type="submit" carregando={enviando} className="w-full">Entrar</Botao>
        </form>

        <p className="mt-6 text-center text-xs text-marca-100/70">
          A equipe do almoxarifado usa o <a className="underline hover:text-white" href={URL_PAINEL}>painel de estoque</a>.
        </p>
      </div>
    </div>
  )
}
