module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  // Legacy simulated UI (src/App.tsx, src/components, src/i18n, src/index.css) is no longer
  // imported anywhere; it is excluded until it is deleted. schema.d.ts is generated.
  ignorePatterns: [
    'dist',
    '.eslintrc.cjs',
    'src/App.tsx',
    'src/components/**',
    'src/i18n/**',
    'src/api/schema.d.ts',
  ],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
  },
  overrides: [
    {
      // These modules intentionally export hooks and helpers next to their components.
      files: ['src/app/**/*.tsx'],
      rules: { 'react-refresh/only-export-components': 'off' },
    },
  ],
}
