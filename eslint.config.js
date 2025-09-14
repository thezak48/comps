// ESLint flat config for v9+
import js from "@eslint/js";

/** @type {import("eslint").FlatConfig[]} */
export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: "module",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        // Add more browser/ES2021 globals as needed
      },
    },
    rules: {
      indent: ["error", 4],
      quotes: ["error", "double"],
      semi: ["error", "always"],
      "no-unused-vars": "warn",
      "no-console": "off",
    },
  },
];
