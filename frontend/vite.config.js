import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/* The build writes into the Python package's static directory, which the wheel already ships
   (`only-include` covers `skills/career-agent`). That is what keeps `uvx japan-career-agent ui`
   working with no Node on the user's machine: the bundle is committed source as far as packaging
   is concerned, and the server serves it like any other static file.

   Filenames are fixed rather than content-hashed on purpose. The server answers `/static/<name>`
   from an explicit allowlist and never takes a path from the request; a hashed name would have to
   be discovered at runtime, which is exactly the lookup that allowlist exists to avoid. */
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../skills/career-agent/gui/static/app",
    emptyOutDir: true,
    // The shell HTML stays server-rendered so it keeps its localized copy and its no-JS fallback.
    rollupOptions: {
      input: "src/main.jsx",
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "app-[name].js",
        assetFileNames: "app.[ext]",
      },
    },
  },
});
