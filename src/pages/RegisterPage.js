import React, { useState } from 'react';
import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Text,
  Alert,
  AlertIcon,
  Heading,
  Link,
  Divider,
  HStack,
  Card,
  CardBody,
  useToast,
} from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import GoogleLoginButton from '../components/GoogleLoginButton';

const RegisterPage = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { login } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!name || !email || !password) {
      setError('請填寫所有必填欄位');
      return;
    }

    if (password !== confirmPassword) {
      setError('密碼確認不符');
      return;
    }

    if (password.length < 6) {
      setError('密碼長度至少需要 6 個字符');
      return;
    }

    try {
      setIsLoading(true);
      setError('');
      
      const response = await apiClient.post('/auth/register', {
        name,
        email,
        password,
      });

      if (response.data.success) {
        login(response.data.data);
        toast({
          title: '註冊成功',
          description: `歡迎加入，${response.data.data.name}！`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        navigate('/dashboard');
      } else {
        setError(response.data.error?.message || '註冊失敗');
      }
    } catch (err) {
      setError(err.response?.data?.error?.message || '註冊時發生錯誤');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSuccess = (user) => {
    login(user);
    toast({
      title: '註冊成功',
      description: `歡迎加入，${user.name}！`,
      status: 'success',
      duration: 3000,
      isClosable: true,
    });
    navigate('/dashboard');
  };

  const handleGoogleError = (error) => {
    console.error('Google registration failed:', error);
  };

  return (
    <Container maxW="md" py={12}>
      <VStack spacing={8}>
        <Box textAlign="center">
          <Heading color="brand.500" mb={2}>
            註冊 AI Care Plan
          </Heading>
          <Text color="gray.600">
            創建您的帳戶，開始使用 AI 照護計劃管理
          </Text>
        </Box>

        <Card w="full">
          <CardBody>
            <VStack spacing={6}>
              {/* Google 註冊按鈕 */}
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

              {/* 傳統註冊表單 */}
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
                      <FormLabel>姓名</FormLabel>
                      <Input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="請輸入您的姓名"
                        disabled={isLoading}
                      />
                    </FormControl>

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
                        placeholder="請輸入密碼 (至少 6 個字符)"
                        disabled={isLoading}
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>確認密碼</FormLabel>
                      <Input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="請再次輸入密碼"
                        disabled={isLoading}
                      />
                    </FormControl>

                    <Button
                      type="submit"
                      colorScheme="brand"
                      size="lg"
                      width="full"
                      isLoading={isLoading}
                      loadingText="註冊中..."
                    >
                      註冊
                    </Button>
                  </VStack>
                </form>
              </Box>

              <Text fontSize="sm" color="gray.600" textAlign="center">
                已有帳戶？{' '}
                <Link as={RouterLink} to="/login" color="brand.500" fontWeight="semibold">
                  立即登入
                </Link>
              </Text>
            </VStack>
          </CardBody>
        </Card>
      </VStack>
    </Container>
  );
};

export default RegisterPage; 