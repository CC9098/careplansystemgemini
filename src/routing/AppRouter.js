import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Spinner, Center } from '@chakra-ui/react';

// 導入頁面組件
import LoginPage from '../pages/LoginPage';
import RegisterPage from '../pages/RegisterPage';
import DashboardPage from '../pages/DashboardPage';
import ResidentDetailPage from '../pages/ResidentDetailPage';
import ProtectedRoute from './ProtectedRoute';

const AppRouter = () => {
  const { loading } = useAuth();

  // 顯示載入中狀態
  if (loading) {
    return (
      <Center h="100vh">
        <Spinner size="xl" color="brand.500" />
      </Center>
    );
  }

  return (
    <Routes>
      {/* 公開路由 */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      
      {/* 受保護的路由 */}
      <Route 
        path="/dashboard" 
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/residents/:id" 
        element={
          <ProtectedRoute>
            <ResidentDetailPage />
          </ProtectedRoute>
        } 
      />
      
      {/* 共享頁面 (未來實現) */}
      {/* <Route path="/shared/:token" element={<SharedDashboardPage />} /> */}
      
      {/* 預設重定向 */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      
      {/* 404 頁面 */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default AppRouter; 