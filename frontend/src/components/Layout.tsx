import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api, URL_PAINEL } from '../api/client'
import type { Resumo } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { cx } from './estilos'

interface ItemMenu {
  para: string
  rotulo: string
  icone: string
  avaliador?: boolean
  chefia?: boolean
}

const MENU: ItemMenu[] = [
  { para: '/', rotulo: 'Início', icone: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5Z' },
  { para: '/requisicoes/nova', rotulo: 'Nova requisição', icone: 'M12 5v14M5 12h14' },
  { para: '/requisicoes', rotulo: 'Minhas requisições', icone: 'M9 12h6M9 16h6M8 3h8l4 4v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h3Z' },
  { para: '/aprovacoes', rotulo: 'Aprovações', icone: 'm9 12 2 2 4-4M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z', avaliador: true },
  { para: '/setor', rotulo: 'Consumo do setor', icone: 'M3 12a9 9 0 1 0 9-9v9H3Z', chefia: true },
]

function Icone({ d }: { d: string }) {
  return (
    <svg className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

export function Layout() {
  const { usuario, sair, temPapel } = useAuth()
  const [menuAberto, setMenuAberto] = useState(false)
  const chefia = temPapel('CHEFIA')
  const avaliador = chefia || temPapel('GESTOR')
  const operaEstoque = temPapel('ALMOXARIFE') || temPapel('GESTOR')

  // Contador de pendências no menu "Aprovações"
  const { data: resumo } = useQuery({
    queryKey: ['resumo'],
    queryFn: async () => (await api.get<Resumo>('/resumo')).data,
    refetchInterval: 60_000,
  })
  const pendentes = resumo?.pendentes_avaliacao ?? 0

  const itens = MENU.filter((i) => (!i.avaliador || avaliador) && (!i.chefia || chefia))

  return (
    <div className="min-h-screen lg:flex">
      <aside className="bg-marca-900 text-marca-100 lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex h-16 items-center justify-between gap-3 px-5">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-marca-700 text-xs font-bold text-destaque">ALM</span>
            <div className="leading-tight">
              <div className="text-sm font-semibold text-white">CLASSCONT</div>
              <div className="text-xs text-marca-100/70">Requisições de material</div>
            </div>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 hover:bg-marca-700 lg:hidden"
            onClick={() => setMenuAberto((v) => !v)}
            aria-expanded={menuAberto}
            aria-label="Abrir menu"
          >
            <Icone d="M4 6h16M4 12h16M4 18h16" />
          </button>
        </div>

        <nav className={cx('px-3 pb-4 lg:block lg:flex-1', menuAberto ? 'block' : 'hidden')}>
          <ul className="space-y-1">
            {itens.map((item) => (
              <li key={item.para}>
                <NavLink
                  to={item.para}
                  end={item.para === '/' || item.para === '/requisicoes'}
                  onClick={() => setMenuAberto(false)}
                  className={({ isActive }) =>
                    cx(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition',
                      isActive ? 'bg-marca-700 text-white' : 'hover:bg-marca-700/50 hover:text-white',
                    )
                  }
                >
                  <Icone d={item.icone} />
                  <span className="flex-1">{item.rotulo}</span>
                  {item.avaliador && pendentes > 0 && (
                    <span className="rounded-full bg-destaque px-2 py-0.5 text-xs font-semibold text-marca-900">{pendentes}</span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
          {operaEstoque && (
            <a href={URL_PAINEL} className="mt-6 flex items-center gap-3 rounded-lg border border-marca-700 px-3 py-2 text-sm hover:bg-marca-700/50 hover:text-white">
              <Icone d="M20 7 12 3 4 7m16 0-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
              Painel do almoxarifado ↗
            </a>
          )}
        </nav>

        <div className={cx('border-t border-marca-700 px-5 py-4 text-sm lg:block', menuAberto ? 'block' : 'hidden')}>
          <p className="font-medium text-white">{usuario?.nome}</p>
          <p className="text-xs text-marca-100/70">
            {usuario?.setor?.sigla} · {usuario?.cargo}
          </p>
          <button type="button" onClick={sair} className="mt-2 text-xs text-destaque hover:underline">
            Sair
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 lg:pl-64">
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
