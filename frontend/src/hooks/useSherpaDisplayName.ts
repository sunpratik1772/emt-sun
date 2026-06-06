import { useAuthStore } from '../store/authStore'
import { firstNameFromDisplayName } from '../lib/sherpaGreeting'

/** Display name for Sherpa greetings (first name when available). */
export function useSherpaDisplayName(): string {
  const name = useAuthStore((s) => s.user?.name)
  const first = firstNameFromDisplayName(name)
  return first === 'there' ? '' : first
}
