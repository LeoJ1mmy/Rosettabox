import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Suppress Vite WebSocket errors when accessing through Cloudflare Tunnel
// These errors are harmless and only affect HMR (Hot Module Replacement) in development
if (import.meta.env.DEV) {
  const originalError = console.error;
  console.error = (...args) => {
    const errorMessage = args[0]?.toString() || '';
    // Filter out Vite WebSocket connection errors
    if (
      errorMessage.includes('WebSocket') ||
      errorMessage.includes('[vite]') ||
      errorMessage.includes('failed to connect')
    ) {
      return; // Suppress these errors
    }
    originalError.apply(console, args);
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)