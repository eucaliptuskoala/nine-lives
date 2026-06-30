/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    // Provide dummy Supabase env vars so the shared client (created at module
    // load time in src/hooks/useSupabase.ts) constructs harmlessly under test.
    // These are local placeholders only — never real credentials. Tests mock
    // any actual Supabase calls, so no network requests are made.
    env: {
      VITE_SUPABASE_URL: 'http://localhost',
      VITE_SUPABASE_ANON_KEY: 'test-anon-key',
    },
  },
})
