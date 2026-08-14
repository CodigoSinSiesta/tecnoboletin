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

export type Role = 'user' | 'admin';

/**
 * Rol de la sesion actual, o null si no hay sesion.
 *
 * El rol vive en la tabla `user_profiles`, no en `app_metadata`: en un
 * sitio estatico no hay backend con service_role, y app_metadata solo se
 * puede escribir con esa clave. Con la tabla, la RLS es a la vez la
 * barrera real (quien puede cambiar roles) y el dato que la interfaz lee,
 * y la gestion se puede hacer desde la propia web (/cuenta/usuarios/).
 *
 * Un usuario no puede autoascenderse: la politica de UPDATE exige
 * is_admin(auth.uid()), evaluada en Postgres.
 */
export async function fetchRole(): Promise<Role | null> {
  const supabase = getSupabase();
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) return null;
  const { data } = await supabase
    .from('user_profiles')
    .select('role')
    .eq('id', session.user.id)
    .maybeSingle();
  return (data?.role as Role) ?? 'user';
}

/** Atajo de lectura: ¿la sesion actual es de administracion? */
export async function isAdmin(): Promise<boolean> {
  return (await fetchRole()) === 'admin';
}

/** URL absoluta de vuelta tras un login OAuth/magic-link, respetando el
 *  base path (/tecnoboletin) tanto en produccion como en local. */
export function accountUrl(): string {
  const base = (import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/');
  return new URL(`${base}cuenta/`, window.location.origin).toString();
}
