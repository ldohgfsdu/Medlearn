const { defineConfig } = require('eslint/config')
const expoConfig = require('eslint-config-expo/flat')

module.exports = defineConfig([
  ...expoConfig,
  {
    ignores: [
      'generated/**',
      'scripts/**',
      'supabase/functions/**',
      'textbook/**',
    ],
  },
])
