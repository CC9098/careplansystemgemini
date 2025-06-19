import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../api/client';

const AuthContext = createContext({});

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // 檢查用戶登入狀態
  const checkAuthStatus = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/auth/me');
      if (response.data.success) {
        setUser(response.data.data);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  // 登入
  const login = async (email, password) => {
    try {
      const response = await apiClient.post('/auth/login', {
        email,
        password,
      });

      if (response.data.success) {
        setUser(response.data.data);
        setIsAuthenticated(true);
        return { success: true };
      } else {
        return { 
          success: false, 
          error: response.data.error?.message || '登入失敗' 
        };
      }
    } catch (error) {
      console.error('Login failed:', error);
      return { 
        success: false, 
        error: error.response?.data?.error?.message || '登入失敗，請稍後再試' 
      };
    }
  };

  // 註冊
  const register = async (email, password, name) => {
    try {
      const response = await apiClient.post('/auth/register', {
        email,
        password,
        name,
      });

      if (response.data.success) {
        setUser(response.data.data);
        setIsAuthenticated(true);
        return { success: true };
      } else {
        return { 
          success: false, 
          error: response.data.error?.message || '註冊失敗' 
        };
      }
    } catch (error) {
      console.error('Registration failed:', error);
      return { 
        success: false, 
        error: error.response?.data?.error?.message || '註冊失敗，請稍後再試' 
      };
    }
  };

  // 登出
  const logout = async () => {
    try {
      await apiClient.post('/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  // Google 登入 (待實現)
  const loginWithGoogle = async () => {
    // TODO: 實現 Google OAuth 流程
    console.log('Google login not implemented yet');
    return { success: false, error: 'Google 登入功能尚未實現' };
  };

  // 更新用戶資料
  const updateUser = (newUserData) => {
    setUser(prevUser => ({ ...prevUser, ...newUserData }));
  };

  // 應用載入時檢查認證狀態
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const value = {
    user,
    loading,
    isAuthenticated,
    login,
    register,
    logout,
    loginWithGoogle,
    updateUser,
    checkAuthStatus,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}; 