import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the board at http://localhost:5173 and opens it in the browser.
// The backend (uvicorn main:app --port 8000) allows this origin via CORS.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, open: true },
});
