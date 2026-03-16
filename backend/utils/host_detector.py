"""
跨平台主機地址自動檢測工具
支持：WSL2、Docker、Ubuntu/Linux、macOS

業界最佳實踐：
1. 環境變量優先 (OLLAMA_URL)
2. 自動檢測環境類型
3. 智能選擇最佳主機地址
"""

import os
import socket
import subprocess
from typing import Optional


def is_wsl() -> bool:
    """檢測是否在 WSL 環境中運行"""
    try:
        # 方法 1: 檢查 /proc/version
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower() or 'wsl' in f.read().lower()
    except:
        pass

    try:
        # 方法 2: 檢查 WSL 環境變量
        return 'WSL' in os.environ.get('WSL_DISTRO_NAME', '')
    except:
        return False


def is_docker() -> bool:
    """檢測是否在 Docker 容器中運行"""
    # 方法 1: 檢查 .dockerenv 文件
    if os.path.exists('/.dockerenv'):
        return True

    # 方法 2: 檢查環境變量
    if os.getenv('DOCKER_ENV') == 'true':
        return True

    # 方法 3: 檢查 cgroup
    try:
        with open('/proc/1/cgroup', 'r') as f:
            return 'docker' in f.read()
    except:
        return False


def get_wsl_host_ip() -> Optional[str]:
    """獲取 WSL 環境下的 Windows 主機 IP"""
    # 方法 1: 從 ip route 獲取（最可靠）
    try:
        result = subprocess.run(
            ['ip', 'route', 'show', 'default'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            # default via 172.22.80.1 dev eth0
            parts = result.stdout.split()
            if 'via' in parts:
                return parts[parts.index('via') + 1]
    except:
        pass

    # 方法 2: 從 /etc/resolv.conf 讀取（備用方法）
    try:
        with open('/etc/resolv.conf', 'r') as f:
            for line in f:
                if line.startswith('nameserver'):
                    ip = line.split()[1]
                    # 驗證是否為私有 IP
                    if ip.startswith(('172.', '192.168.')):  # 排除 10.255.x.x (通常是 DNS)
                        return ip
    except:
        pass

    return None


def get_docker_host() -> str:
    """獲取 Docker 容器訪問主機的地址"""
    # Docker 18.03+ 支持 host.docker.internal
    # 但需要在 docker-compose.yml 中配置 extra_hosts
    return 'host.docker.internal'


def test_connection(host: str, port: int, timeout: float = 2.0) -> bool:
    """測試主機地址是否可連接"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def detect_ollama_host(default_port: int = 11434) -> str:
    """
    自動檢測 Ollama 服務的最佳主機地址

    優先級：
    1. 環境變量 OLLAMA_URL (提取 host)
    2. 環境變量 OLLAMA_HOST (解析 host)
    3. 自動檢測

    Returns:
        最佳主機地址（不含端口）
    """
    # 優先級 1: 檢查 OLLAMA_URL 環境變量
    env_url = os.getenv('OLLAMA_URL')
    if env_url:
        # 從 URL 提取 host（已在 .env 中明確指定）
        try:
            from urllib.parse import urlparse
            parsed = urlparse(env_url)
            if parsed.hostname:
                return parsed.hostname
        except:
            pass

    # 優先級 2: 檢查 OLLAMA_HOST 環境變量
    env_host = os.getenv('OLLAMA_HOST')
    if env_host:
        # 可能是 "0.0.0.0:11434" 或 "localhost:11434" 或 "http://host:11434" 格式
        try:
            # 如果包含 http://，使用 urlparse
            if env_host.startswith('http'):
                from urllib.parse import urlparse
                parsed = urlparse(env_host)
                if parsed.hostname:
                    return parsed.hostname
            else:
                # 否則按 host:port 格式拆分
                return env_host.split(':')[0]
        except:
            pass

    # 優先級 3: 自動檢測
    if is_docker():
        # Docker 環境：使用 host.docker.internal
        host = get_docker_host()
        print(f"🐳 Docker 環境檢測：使用 {host}")
        return host

    elif is_wsl():
        # WSL 環境：使用 Windows 主機 IP
        wsl_ip = get_wsl_host_ip()
        if wsl_ip:
            print(f"🪟 WSL 環境檢測：Windows 主機 IP = {wsl_ip}")
            # 測試連接
            if test_connection(wsl_ip, default_port):
                print(f"✅ Ollama 連接測試成功: {wsl_ip}:{default_port}")
                return wsl_ip
            else:
                print(f"⚠️ 無法連接到 {wsl_ip}:{default_port}，使用檢測到的 IP")
            return wsl_ip
        return 'localhost'

    else:
        # 原生 Linux/macOS：使用 localhost
        print(f"🖥️ 原生環境檢測：使用 localhost")
        return 'localhost'


def get_ollama_url(default_port: int = 11434) -> str:
    """
    獲取完整的 Ollama URL

    Returns:
        完整的 Ollama URL，例如 "http://172.22.80.1:11434"
    """
    # 如果環境變量已經提供完整 URL，直接使用
    env_url = os.getenv('OLLAMA_URL')
    if env_url and env_url.startswith('http'):
        return env_url

    # 否則自動檢測並構建 URL
    host = detect_ollama_host(default_port)
    return f"http://{host}:{default_port}"


# 測試函數
if __name__ == "__main__":
    print("=" * 60)
    print("🔍 環境檢測")
    print("=" * 60)
    print(f"WSL 環境: {is_wsl()}")
    print(f"Docker 環境: {is_docker()}")

    if is_wsl():
        print(f"WSL 主機 IP: {get_wsl_host_ip()}")

    print("\n" + "=" * 60)
    print("🎯 Ollama 配置")
    print("=" * 60)
    ollama_url = get_ollama_url()
    print(f"推薦 Ollama URL: {ollama_url}")

    # 測試連接
    from urllib.parse import urlparse
    parsed = urlparse(ollama_url)
    port = parsed.port or 11434
    print(f"\n測試連接到 {parsed.hostname}:{port}...")
    if test_connection(parsed.hostname, port):
        print("✅ 連接成功！")
    else:
        print("❌ 連接失敗！請確保 Ollama 已啟動")
