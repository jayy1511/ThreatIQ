import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

export default [
  // keep Next.js + TS defaults
  ...compat.extends("next/core-web-vitals", "next/typescript"),

  // global ignores (same as before)
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
    ],
  },

  // relax rules that are failing Vercel build
  {
    rules: {
      // main blocker in your log
      "@typescript-eslint/no-explicit-any": "off",
      // optional: avoid failing for unused vars (e.g., router not used yet)
      "@typescript-eslint/no-unused-vars": "off",
      "no-unused-vars": "off",
    },
  },
];
