import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env file from parent directory (project root)
  const envDir = process.cwd().endsWith('/frontend') ? '..' : process.cwd()
  const env = loadEnv(mode, envDir, '')

  const VITE_PORT = parseInt(env.VITE_PORT || '5173')
  // 開發環境優先使用 VITE_BACKEND_PORT (3082), 生產環境使用 PORT (3080)
  const BACKEND_PORT = parseInt(env.VITE_BACKEND_PORT || env.PORT || '3080')
  const BACKEND_URL = env.VITE_BACKEND_URL || `http://localhost:${BACKEND_PORT}`

  return {
    plugins: [react()],
    server: {
      port: VITE_PORT,
      strictPort: true, // 強制使用指定端口，如果被占用則報錯
      host: '0.0.0.0', // 允許外部訪問
      allowedHosts: ['rosettabox.leopilot.com', 'rosettanvc.leopilot.com', 'rosettanvpc.leopilot.com', 'rosettanvpc1.leopilot.com', 'rosettapro.leopilot.com'], // 允許 Cloudflare 域名訪問
      // 性能優化 - HMR 配置
      hmr: {
        // 當通過 Cloudflare Tunnel 訪問時，HMR 可能無法正常工作
        // 這不影響生產環境，只影響開發時的熱更新
        overlay: false, // 禁用錯誤覆蓋層
      },
      // 優化文件監聽
      watch: {
        usePolling: false,
        interval: 100,
      },
      proxy: {
        '/api': {
          target: BACKEND_URL,
          changeOrigin: true,
          secure: false,
          // 優化代理設置 - 增加超時時間以支持大文件上傳和AI處理
          timeout: 3600000,      // 60分鐘超時，支持大文件上傳（1+ hour audio files）
          proxyTimeout: 3600000, // 代理超時也增加到60分鐘
          // 關鍵：保持原始請求體，不進行任何轉換（對於 multipart/form-data 至關重要）
          // Vite 使用 http-proxy 內部，這些選項確保 body 被正確轉發
          ws: false, // 確保不干擾 websocket
          buffer: false, // 禁用緩衝，直接流式傳輸
          proxyReqBodyDecorator: function (bodyContent, srcReq) {
            // 對於大文件上傳，不修改body，直接返回
            return bodyContent;
          },
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('proxy error', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('Sending Request to the Target:', req.method, req.url);

              // 對於 multipart/form-data，確保所有必要的頭部都被正確傳遞
              if (req.headers['content-type'] && req.headers['content-type'].includes('multipart/form-data')) {
                // 保持原始的 content-type（包含 boundary）
                if (req.headers['content-length']) {
                  proxyReq.setHeader('Content-Length', req.headers['content-length']);
                }
                // 移除 Transfer-Encoding 以避免 Gunicorn 報錯
                proxyReq.removeHeader('Transfer-Encoding');
                console.log('🔧 Proxying multipart/form-data request with Content-Length:', req.headers['content-length']);
              }
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
            });
          },
        }
      }
    },
    // 構建優化
    build: {
      // 啟用 gzip 壓縮
      minify: 'terser',
      // 優化依賴預構建
      optimizeDeps: {
        include: ['react', 'react-dom']
      }
    },
    base: '/' // 確保基礎路徑正確
  }
})

