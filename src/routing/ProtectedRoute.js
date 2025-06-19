import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  // 如果還在載入中，不要重定向
  if (loading) {
    return null;
  }

  // 如果未認證，重定向到登入頁面
  if (!isAuthenticated) {
    return (
      <Navigate 
        to="/login" 
        state={{ from: location }} 
        replace 
      />
    );
  }

  // 如果已認證，渲染子組件
  return children;
};

export default ProtectedRoute; 