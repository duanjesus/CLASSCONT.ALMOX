/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL do painel do almoxarifado (templates Django). */
  readonly VITE_PAINEL_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
