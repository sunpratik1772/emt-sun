/** Demo auth bypass — enabled in dev unless explicitly disabled. */
export const DEMO_AUTH_ENABLED =
  import.meta.env.VITE_ENABLE_DEMO_AUTH === 'true' ||
  (import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEMO_AUTH !== 'false')

/** Cloud/K8s preview behind HTTPS ingress — enables WSS HMR in vite.config. */
export const PREVIEW_MODE = import.meta.env.VITE_PREVIEW_MODE === 'true'
