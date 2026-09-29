import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import type { Papel } from './api/types'
import { useAuth } from './auth/useAuth'
import { Layout } from './components/Layout'
import { Alerta, Botao, Carregando } from './components/ui'
import { Aprovacoes } from './pages/Aprovacoes'
import { ConsumoSetor } from './pages/ConsumoSetor'
import { DetalheRequisicao } from './pages/DetalheRequisicao'
import { EditorRequisicao } from './pages/EditorRequisicao'
import { Inicio } from './pages/Inicio'
import { Login } from './pages/Login'
import { MinhasRequisicoes } from './pages/MinhasRequisicoes'

/** Rota que exige login (e, opcionalmente, um dos papéis informados). */
function Protegida({ children, papeis }: { children: ReactNode; papeis?: Papel[] }) {
  const { usuario, carregando, semConexao, tentarDeNovo, temPapel } = useAuth()
  if (carregando) return <Carregando texto="Validando sessão…" />
  if (semConexao)
    return (
      <div className="mx-auto mt-24 max-w-sm space-y-4 px-4 text-center">
        <Alerta>Não foi possível falar com o servidor.</Alerta>
        <Botao onClick={tentarDeNovo}>Tentar de novo</Botao>
      </div>
    )
  if (!usuario) return <Navigate to="/login" replace />
  if (papeis && !papeis.some(temPapel)) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protegida>
            <Layout />
          </Protegida>
        }
      >
        <Route index element={<Inicio />} />
        <Route path="requisicoes" element={<MinhasRequisicoes />} />
        <Route path="requisicoes/nova" element={<EditorRequisicao />} />
        <Route path="requisicoes/:id" element={<DetalheRequisicao />} />
        <Route path="requisicoes/:id/editar" element={<EditorRequisicao />} />
        <Route path="aprovacoes" element={<Protegida papeis={['CHEFIA', 'GESTOR']}><Aprovacoes /></Protegida>} />
        <Route path="setor" element={<Protegida papeis={['CHEFIA']}><ConsumoSetor /></Protegida>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
