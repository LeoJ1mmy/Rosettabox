/**
 * API 服務層 - 統一管理所有 API 請求
 */
import axios from 'axios';

// 動態 API 基礎 URL - 支持 LAN 訪問和 Cloudflare Tunnel
const getApiBaseUrl = () => {
  const hostname = window.location.hostname;
  const protocol = window.location.protocol;
  const port = window.location.port;

  // 如果是 HTTPS（Cloudflare Tunnel）或標準端口，使用相對路徑
  // 這樣 API 請求會通過同一個域名/隧道
  if (protocol === 'https:' || !port || port === '80' || port === '443') {
    return '/api';
  }

  // 本地開發：localhost 或 127.0.0.1 使用 Vite proxy
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return '/api';
  }

  // LAN 訪問（非隧道）：使用同協議直連後端
  // 🔧 使用生產環境端口 3080
  return `${protocol}//${hostname}:3080/api`;
};

const API_BASE_URL = getApiBaseUrl();

// 創建 axios 實例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 1800000, // 30分鐘超時（與 Vite proxy 一致，支持大文件上傳）
  headers: {
    'Content-Type': 'application/json'
  }
});

// 請求攔截器
apiClient.interceptors.request.use(
  config => {
    // 可以在這裡添加 token 等
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// 響應攔截器
apiClient.interceptors.response.use(
  response => response.data,
  error => {
    return Promise.reject(error);
  }
);

// API 服務類
class ApiService {
  // 健康檢查
  async checkHealth() {
    return apiClient.get('/health');
  }

  // Whisper 模型相關
  async getWhisperModels() {
    return apiClient.get('/whisper/models');
  }

  async switchWhisperModel(model) {
    return apiClient.post('/whisper/switch-model', { model });
  }

  // AI 模型相關
  async getAiModels() {
    return apiClient.get('/ai/models');
  }

  // 文件上傳
  async uploadFile(formData, onProgress) {
    return apiClient.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 3600000, // 60分鐘超時（用於超大文件上傳，例如2小時音頻文件）
      onUploadProgress: progressEvent => {
        if (onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      }
    });
  }

  // 文字處理
  async processText(data) {
    return apiClient.post('/process-text', data);
  }

  // 任務相關
  async getTaskStatus(taskId) {
    return apiClient.get(`/task/${taskId}/status`);
  }

  async getTaskProgress(taskId) {
    return apiClient.get(`/task/${taskId}/progress`);
  }

  async cancelTask(taskId, userId) {
    return apiClient.post(`/task/${taskId}/cancel`, { user_id: userId });
  }

  async getUserTasks(userId) {
    return apiClient.get(`/user/${userId}/tasks`);
  }

  async verifyTask(taskId, userId) {
    return apiClient.get(`/task/${taskId}/verify`, {
      params: { user_id: userId }
    });
  }

  // 緩存清理
  async clearCache() {
    return apiClient.post('/clear-cache');
  }

  // 會議分析
  async analyzeMeeting(formData, onProgress) {
    return apiClient.post('/analyze-meeting', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: onProgress
    });
  }

  // 文字處理相關 API
  async processTextWithCustom(data) {
    return apiClient.post('/text/process', data);
  }

  async getProcessingModes() {
    return apiClient.get('/text/modes');
  }

  async getDetailLevels() {
    return apiClient.get('/text/detail-levels');
  }

  async validateCustomPrompt(prompt) {
    return apiClient.post('/text/custom-prompt/validate', { prompt });
  }

  async getCustomPromptSuggestions() {
    return apiClient.get('/text/custom-prompt/suggestions');
  }

  // 系統配置相關
  async getSystemConfig() {
    return apiClient.get('/network/config');
  }

  async getNetworkStatus() {
    return apiClient.get('/network/status');
  }

  // ============== Hot Words Admin API ==============

  async verifyAdminPassword(password) {
    return apiClient.post('/admin/hot-words/verify', { password });
  }

  async getHotWordsCategories(password) {
    return apiClient.get('/admin/hot-words/categories', {
      headers: { 'X-Admin-Password': password }
    });
  }

  async toggleHotWordsCategory(category, password) {
    return apiClient.post(`/admin/hot-words/categories/${encodeURIComponent(category)}/toggle`, null, {
      headers: { 'X-Admin-Password': password }
    });
  }

  async getHotWordsEntries(password) {
    return apiClient.get('/admin/hot-words/entries', {
      headers: { 'X-Admin-Password': password }
    });
  }

  async addHotWord(data, password) {
    return apiClient.post('/admin/hot-words/entries', data, {
      headers: { 'X-Admin-Password': password }
    });
  }

  async updateHotWord(word, data, password) {
    return apiClient.put(`/admin/hot-words/entries/${encodeURIComponent(word)}`, data, {
      headers: { 'X-Admin-Password': password }
    });
  }

  async deleteHotWord(word, password) {
    return apiClient.delete(`/admin/hot-words/entries/${encodeURIComponent(word)}`, {
      headers: { 'X-Admin-Password': password }
    });
  }

  async searchHotWords(query, password) {
    return apiClient.get('/admin/hot-words/search', {
      params: { q: query },
      headers: { 'X-Admin-Password': password }
    });
  }

  async getHotWordsStatistics(password) {
    return apiClient.get('/admin/hot-words/statistics', {
      headers: { 'X-Admin-Password': password }
    });
  }
}

// 導出單例
export default new ApiService();