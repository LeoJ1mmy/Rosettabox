#!/usr/bin/env python3
"""
維護模式服務器
顯示系統維護中的頁面
"""

from flask import Flask, render_template_string
import os

app = Flask(__name__)

MAINTENANCE_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>系統維護中 | RosettaNVPC</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Outfit:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --brand-primary: #06b6d4;
            --brand-secondary: #0891b2;
            --brand-accent: #14b8a6;
            --glass-100: rgba(255, 255, 255, 0.05);
            --glass-200: rgba(255, 255, 255, 0.08);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', system-ui, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            position: relative;
            overflow: hidden;

            /* 專案風格漸層背景 */
            background: linear-gradient(225deg,
                rgba(5, 5, 10, 1) 0%,
                rgba(13, 14, 18, 1) 16.667%,
                rgba(22, 23, 26, 1) 33.333%,
                rgba(30, 31, 34, 1) 50%,
                rgba(38, 39, 42, 1) 66.667%,
                rgba(44, 45, 48, 1) 83.333%,
                rgba(48, 49, 53, 1) 100%
            );
            background-attachment: fixed;
            color: var(--text-primary);
        }

        /* 動態光暈背景 */
        .bg-blobs {
            position: fixed;
            inset: 0;
            overflow: hidden;
            pointer-events: none;
            z-index: 0;
        }

        .blob {
            position: absolute;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.3;
            animation: blob 7s infinite;
        }

        .blob-1 {
            top: -10%;
            left: 20%;
            width: 400px;
            height: 400px;
            background: var(--brand-primary);
            animation-delay: 0s;
        }

        .blob-2 {
            top: 10%;
            right: 20%;
            width: 350px;
            height: 350px;
            background: var(--brand-secondary);
            animation-delay: 2s;
        }

        .blob-3 {
            bottom: -10%;
            left: 30%;
            width: 380px;
            height: 380px;
            background: var(--brand-accent);
            animation-delay: 4s;
        }

        @keyframes blob {
            0% { transform: translate(0px, 0px) scale(1); }
            33% { transform: translate(30px, -50px) scale(1.1); }
            66% { transform: translate(-20px, 20px) scale(0.9); }
            100% { transform: translate(0px, 0px) scale(1); }
        }

        /* 主容器 */
        .container {
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 480px;
            animation: slideUp 0.6s ease-out;
        }

        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Glass Panel 卡片 */
        .glass-panel {
            background: var(--glass-100);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 1rem;
            padding: 40px 32px;
            text-align: center;
            box-shadow:
                0 25px 50px -12px rgba(0, 0, 0, 0.4),
                inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
        }

        /* 圖標 */
        .icon-container {
            width: 88px;
            height: 88px;
            margin: 0 auto 28px;
            background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: pulse-slow 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
            box-shadow:
                0 20px 40px -10px rgba(6, 182, 212, 0.4),
                inset 0 1px 0 0 rgba(255, 255, 255, 0.2);
        }

        @keyframes pulse-slow {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.9; transform: scale(1.02); }
        }

        .icon-container svg {
            width: 44px;
            height: 44px;
            color: white;
        }

        /* 標題 */
        h1 {
            font-family: 'Outfit', system-ui, sans-serif;
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 12px;
            letter-spacing: 0.02em;
        }

        .subtitle {
            font-size: 15px;
            color: var(--text-secondary);
            line-height: 1.7;
            margin-bottom: 28px;
        }

        /* 時間區塊 */
        .time-block {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.2);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        }

        .time-label {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-bottom: 8px;
        }

        .time-label svg {
            width: 18px;
            height: 18px;
            color: #f59e0b;
        }

        .time-label span {
            font-size: 12px;
            font-weight: 600;
            color: #f59e0b;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .time-value {
            font-family: 'Outfit', system-ui, sans-serif;
            font-size: 24px;
            font-weight: 600;
            color: var(--text-primary);
        }

        /* 進度指示 */
        .progress-section {
            margin-bottom: 28px;
        }

        .progress-label {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            margin-bottom: 12px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--brand-primary);
            border-radius: 50%;
            animation: blink 1.5s ease-in-out infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        .progress-bar {
            height: 4px;
            background: var(--glass-200);
            border-radius: 2px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            width: 30%;
            background: linear-gradient(90deg, var(--brand-primary), var(--brand-accent));
            border-radius: 2px;
            animation: loading 2s ease-in-out infinite;
        }

        @keyframes loading {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(400%); }
        }

        /* 分隔線 */
        .divider {
            height: 1px;
            background: var(--glass-border);
            margin: 24px 0;
        }

        /* 聯繫區塊 */
        .contact-section {
            text-align: center;
        }

        .contact-label {
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        .contact-email {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: var(--glass-200);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            color: var(--brand-primary);
            font-size: 14px;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s ease;
        }

        .contact-email:hover {
            background: var(--glass-100);
            border-color: var(--brand-primary);
            box-shadow: 0 0 20px rgba(6, 182, 212, 0.2);
        }

        .contact-email svg {
            width: 16px;
            height: 16px;
        }

        /* Logo */
        .logo {
            margin-top: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            font-size: 13px;
            color: var(--text-muted);
        }

        .logo-icon {
            width: 20px;
            height: 20px;
            background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
            border-radius: 6px;
        }

        /* RWD */
        @media (max-width: 480px) {
            .glass-panel {
                padding: 32px 24px;
            }

            h1 {
                font-size: 24px;
            }

            .icon-container {
                width: 72px;
                height: 72px;
                border-radius: 16px;
            }

            .icon-container svg {
                width: 36px;
                height: 36px;
            }

            .time-value {
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <!-- 動態光暈背景 -->
    <div class="bg-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
        <div class="blob blob-3"></div>
    </div>

    <div class="container">
        <div class="glass-panel">
            <!-- 圖標 -->
            <div class="icon-container">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
                </svg>
            </div>

            <!-- 標題 -->
            <h1>系統維護中</h1>
            <p class="subtitle">
                我們正在進行系統更新與優化，<br>
                以提供您更好的服務體驗。
            </p>

            <!-- 維護時間 -->
            <div class="time-block">
                <div class="time-label">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                    </svg>
                    <span>固定維護時段</span>
                </div>
                <div class="time-value">週一至週五 15:30 - 18:30</div>
            </div>

            <!-- 進度指示 -->
            <div class="progress-section">
                <div class="progress-label">
                    <span class="status-dot"></span>
                    <span>維護作業進行中</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
            </div>

            <div class="divider"></div>

            <!-- 聯繫方式 -->
            <div class="contact-section">
                <div class="contact-label">如有緊急需求，請聯繫</div>
                <a href="mailto:jimmy@leosys.com" class="contact-email">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                    </svg>
                    jimmy@leosys.com
                </a>
            </div>
        </div>

        <!-- Logo -->
        <div class="logo">
            <div class="logo-icon"></div>
            <span>RosettaNVPC Voice Processor</span>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
@app.route('/<path:path>')
def maintenance(path=''):
    return render_template_string(MAINTENANCE_HTML), 503

if __name__ == '__main__':
    port = int(os.environ.get('MAINTENANCE_PORT', 8503))
    print(f"🔧 維護模式服務器啟動於 http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
