/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_DEMO_AUTH?: string
  readonly VITE_PREVIEW_MODE?: string
  readonly VITE_BACKEND_URL?: string
  readonly REACT_APP_BACKEND_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
