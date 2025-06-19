import React, { useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Heading,
  Text,
  Alert,
  AlertIcon,
  Container,
  Card,
  CardBody,
  Link,
  Divider,
  HStack,
  useToast,
} from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import GoogleLoginButton from '../components/GoogleLoginButton';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { login } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!email || !password) {
      setError('請輸入電子郵件和密碼');
      return;
    }

    try {
      setIsLoading(true);
      setError('');
      
      const response = await apiClient.post('/auth/login', {
        email,
        password,
      });

      if (response.data.success) {
        login(response.data.data);
        toast({
          title: '登入成功',
          description: `歡迎回來，${response.data.data.name}！`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        navigate('/dashboard');
      } else {
        setError(response.data.error?.message || '登入失敗');
      }
    } catch (err) {
      setError(err.response?.data?.error?.message || '登入時發生錯誤');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = (user) => {
    login(user);
    navigate('/dashboard');
  };

  const handleGoogleError = (error) => {
    console.error('Google login failed:', error);
  };

  return (
    <Container maxW="md" py={12}>
      <VStack spacing={8}>
        <Box textAlign="center">
          <Heading color="brand.500" mb={2}>
            登入 AI Care Plan
          </Heading>
          <Text color="gray.600">
            歡迎回來！請登入您的帳戶
          </Text>
        </Box>

        <Card w="full">
          <CardBody>
            <VStack spacing={6}>
              {/* Google 登入按鈕 */}
              <GoogleLoginButton 
                onSuccess={handleGoogleSuccess}
                onError={handleGoogleError}
                isLoading={isLoading}
                setIsLoading={setIsLoading}
              />

              <HStack w="full">
                <Divider />
                <Text fontSize="sm" color="gray.500" px={3}>
                  或
                </Text>
                <Divider />
              </HStack>

              {/* 傳統登入表單 */}
              <Box w="full">
                <form onSubmit={handleSubmit}>
                  <VStack spacing={4}>
                    {error && (
                      <Alert status="error">
                        <AlertIcon />
                        {error}
                      </Alert>
                    )}

                    <FormControl isRequired>
                      <FormLabel>電子郵件</FormLabel>
                      <Input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="請輸入您的電子郵件"
                        disabled={isLoading}
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>密碼</FormLabel>
                      <Input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="請輸入您的密碼"
                        disabled={isLoading}
                      />
                    </FormControl>

                    <Button
                      type="submit"
                      colorScheme="brand"
                      size="lg"
                      width="full"
                      isLoading={isLoading}
                      loadingText="登入中..."
                    >
                      登入
                    </Button>
                  </VStack>
                </form>
              </Box>

              <Text fontSize="sm" color="gray.600" textAlign="center">
                還沒有帳戶？{' '}
                <Link as={RouterLink} to="/register" color="brand.500" fontWeight="semibold">
                  立即註冊
                </Link>
              </Text>
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Container>
  );
};

export default LoginPage; 