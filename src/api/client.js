import axios from 'axios';

// 創建 axios 實例
const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:5001/api/v1',
  timeout: 30000, // 30 秒超時
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // 包含 cookies (用於 session 認證)
});

// 請求攔截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在這裡添加認證 token (未來使用 JWT 時)
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 響應攔截器
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // 處理常見錯誤
    if (error.response?.status === 401) {
      // 未授權，可能需要重新登入
      console.warn('Unauthorized access - user may need to login');
      // 可以觸發登出邏輯
      // store.dispatch(logout());
    } else if (error.response?.status === 403) {
      // 禁止訪問
      console.warn('Access forbidden');
    } else if (error.response?.status >= 500) {
      // 服務器錯誤
      console.error('Server error:', error.response);
    }

    return Promise.reject(error);
  }
);

export { apiClient };

// API 端點定義
export const API_ENDPOINTS = {
  // 認證
  AUTH: {
    LOGIN: '/auth/login',
    REGISTER: '/auth/register',
    LOGOUT: '/auth/logout',
    ME: '/auth/me',
    GOOGLE_CALLBACK: '/auth/google-callback',
  },
  
  // 住民管理
  RESIDENTS: {
    LIST: '/residents',
    CREATE: '/residents',
    GET: (id) => `/residents/${id}`,
    UPDATE: (id) => `/residents/${id}`,
    DELETE: (id) => `/residents/${id}`,
    CARE_PLAN: (id) => `/residents/${id}/care-plan`,
    CARE_PLAN_HISTORY: (id) => `/residents/${id}/care-plan/history`,
    CREATE_TASKS: (id) => `/residents/${id}/tasks`,
  },

  // AI 分析與照護計劃
  AI: {
    ANALYZE: '/analyze',
    GENERATE_CARE_PLAN: '/generate-care-plan',
  },

  // 照護任務
  TASKS: {
    UPDATE: (id) => `/tasks/${id}`,
  },

  // 照護計劃歷史
  CARE_PLAN_HISTORY: {
    GET: (id) => `/care-plan-history/${id}`,
  },

  // 共享功能
  SHARES: {
    CREATE: '/shares',
    META: (token) => `/shares/${token}/meta`,
    AUTHENTICATE: (token) => `/shares/${token}/authenticate`,
    DASHBOARD: (token) => `/shares/${token}/dashboard`,
  },
}; 