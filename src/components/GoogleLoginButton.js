import React, { useEffect, useState } from 'react';
import { Button, useToast } from '@chakra-ui/react';
import { FaGoogle } from 'react-icons/fa';
import { apiClient } from '../api/client';

const GoogleLoginButton = ({ onSuccess, onError, isLoading, setIsLoading }) => {
  const [isGoogleLoaded, setIsGoogleLoaded] = useState(false);
  const toast = useToast();

  useEffect(() => {
    // 動態載入 Google Identity Services
    const loadGoogleScript = () => {
      if (window.google) {
        setIsGoogleLoaded(true);
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = () => {
        if (window.google) {
          setIsGoogleLoaded(true);
          initializeGoogleSignIn();
        }
      };
      document.head.appendChild(script);
    };

    const initializeGoogleSignIn = () => {
      const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;
      if (!clientId) {
        console.error('Google Client ID not configured');
        return;
      }

      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: handleGoogleResponse,
        auto_select: false,
        cancel_on_tap_outside: true,
      });
    };

    loadGoogleScript();
  }, []);

  const handleGoogleResponse = async (response) => {
    try {
      setIsLoading(true);
      
      // 發送 ID token 到後端驗證
      const result = await apiClient.post('/auth/google', {
        token: response.credential
      });

      if (result.data.success) {
        toast({
          title: '登入成功',
          description: `歡迎回來，${result.data.data.user.name}！`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        
        if (onSuccess) {
          onSuccess(result.data.data.user);
        }
      } else {
        throw new Error(result.data.error?.message || 'Google 登入失敗');
      }
    } catch (error) {
      console.error('Google login error:', error);
      
      const errorMessage = error.response?.data?.error?.message || 
                          error.message || 
                          'Google 登入時發生錯誤';
      
      toast({
        title: '登入失敗',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      
      if (onError) {
        onError(error);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;
    
    // 開發者模式：如果沒有配置 Google Client ID，使用開發者模式
    if (!clientId || clientId === 'test-client-id-for-development') {
      try {
        setIsLoading(true);
        
        const result = await apiClient.post('/auth/google-dev', {
          email: 'dev@example.com',
          name: 'Developer User'
        });

        if (result.data.success) {
          toast({
            title: '開發者模式登入成功',
            description: `歡迎，${result.data.data.user.name}！`,
            status: 'success',
            duration: 3000,
            isClosable: true,
          });
          
          if (onSuccess) {
            onSuccess(result.data.data.user);
          }
        } else {
          throw new Error(result.data.error?.message || '開發者模式登入失敗');
        }
      } catch (error) {
        console.error('Dev mode login error:', error);
        
        const errorMessage = error.response?.data?.error?.message || 
                            error.message || 
                            '開發者模式登入時發生錯誤';
        
        toast({
          title: '登入失敗',
          description: errorMessage,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        
        if (onError) {
          onError(error);
        }
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // 正常 Google OAuth 流程
    if (!isGoogleLoaded || !window.google) {
      toast({
        title: '載入中',
        description: 'Google 登入服務正在載入，請稍候...',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    // 觸發 Google 登入彈窗
    window.google.accounts.id.prompt();
  };

  const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;
  const isDevMode = !clientId || clientId === 'test-client-id-for-development';

  return (
    <Button
      leftIcon={<FaGoogle />}
      colorScheme="red"
      variant="outline"
      onClick={handleGoogleLogin}
      isLoading={isLoading}
      loadingText="登入中..."
      disabled={!isDevMode && !isGoogleLoaded}
      width="full"
      size="lg"
    >
      {isDevMode ? '使用 Google 登入 (開發者模式)' : '使用 Google 登入'}
    </Button>
  );
};

export default GoogleLoginButton; 