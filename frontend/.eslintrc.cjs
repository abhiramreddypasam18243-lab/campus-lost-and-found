module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  // schema.d.ts is generated from the OpenAPI document (npm run gen:api).
  ignorePatterns: ['dist', '.eslintrc.cjs', 'src/api/schema.d.ts'],
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
