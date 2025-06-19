import React, { useState } from 'react';
import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Input,
  Stack,
  Text,
  Alert,
  AlertIcon,
  Heading,
  Link,
  Divider,
  HStack,
} from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const result = await login(email, password);
      if (result.success) {
        navigate('/dashboard');
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError('登入過程中發生錯誤，請稍後再試');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');

    try {
      const result = await loginWithGoogle();
      if (result.success) {
        navigate('/dashboard');
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError('Google 登入過程中發生錯誤');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxW="md" py={12}>
      <Box
        bg="white"
        p={8}
        borderRadius="lg"
        boxShadow="md"
        border="1px solid"
        borderColor="gray.200"
      >
        <Stack spacing={6}>
          <Box textAlign="center">
            <Heading color="brand.500" mb={2}>
              歡迎回來
            </Heading>
            <Text color="gray.600">
              登入您的 AI Care Plan 管理帳戶
            </Text>
          </Box>

          {error && (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <Stack spacing={4}>
              <FormControl isRequired>
                <FormLabel>電子郵件</FormLabel>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="請輸入您的電子郵件"
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>密碼</FormLabel>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="請輸入您的密碼"
                />
              </FormControl>

              <Button
                type="submit"
                colorScheme="brand"
                size="lg"
                isLoading={loading}
                loadingText="登入中..."
              >
                登入
              </Button>
            </Stack>
          </form>

          <HStack>
            <Divider />
            <Text px="3" color="gray.500" fontSize="sm">
              或
            </Text>
            <Divider />
          </HStack>

          <Button
            variant="outline"
            size="lg"
            onClick={handleGoogleLogin}
            isLoading={loading}
            loadingText="Google 登入中..."
          >
            使用 Google 帳戶登入
          </Button>

          <Box textAlign="center">
            <Text color="gray.600">
              還沒有帳戶？{' '}
              <Link as={RouterLink} to="/register" color="brand.500" fontWeight="semibold">
                立即註冊
              </Link>
            </Text>
          </Box>
        </Stack>
      </Box>
    </Container>
  );
};

export default LoginPage; 