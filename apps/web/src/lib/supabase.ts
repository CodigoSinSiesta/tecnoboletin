// Cliente Supabase compartido (browser). La publishable key es publica por
// diseno -- la seguridad real esta en las politicas RLS de cada tabla.
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://rjfrceapcdlhpukdsixo.supabase.co';
const SUPABASE_KEY = 'sb_publishable_rwEHLqlaHX0hHGLuWDrTWg_p54vU_PV';

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_KEY, {
      auth: {
        // Config explicita del callback de login (no depender de defaults).
        // Flujo implicit y no PKCE a proposito: el metodo principal es el
        // magic link por email, y con PKCE el enlace del correo solo
        // funcionaria en el mismo navegador que lo pidio (el code_verifier
        // vive en localStorage). Con implicit, el enlace completa la sesion
        // en cualquier navegador/dispositivo. detectSessionInUrl procesa el
        // #access_token del callback automaticamente al cargar /cuenta/.
        flowType: 'implicit',
        detectSessionInUrl: true,
        persistSession: true,
        autoRefreshToken: true,
      },
    });
  }
  return client;
}

/** URL absoluta de vuelta tras un login OAuth/magic-link, respetando el
 *  base path (/tecnoboletin) tanto en produccion como en local. */
export function accountUrl(): string {
  const base = (import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/');
  return new URL(`${base}cuenta/`, window.location.origin).toString();
}
