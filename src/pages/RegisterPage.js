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

const RegisterPage = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { register, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // 驗證密碼確認
    if (password !== confirmPassword) {
      setError('密碼確認不匹配');
      return;
    }

    if (password.length < 6) {
      setError('密碼長度至少需要 6 個字符');
      return;
    }

    setLoading(true);

    try {
      const result = await register(email, password, name);
      if (result.success) {
        navigate('/dashboard');
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError('註冊過程中發生錯誤，請稍後再試');
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
      setError('Google 註冊過程中發生錯誤');
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
              建立新帳戶
            </Heading>
            <Text color="gray.600">
              開始使用 AI Care Plan 管理系統
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
                <FormLabel>姓名</FormLabel>
                <Input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="請輸入您的姓名"
                />
              </FormControl>

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
                  placeholder="請輸入密碼 (至少 6 個字符)"
                />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>確認密碼</FormLabel>
                <Input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="請再次輸入密碼"
                />
              </FormControl>

              <Button
                type="submit"
                colorScheme="brand"
                size="lg"
                isLoading={loading}
                loadingText="註冊中..."
              >
                註冊
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
            loadingText="Google 註冊中..."
          >
            使用 Google 帳戶註冊
          </Button>

          <Box textAlign="center">
            <Text color="gray.600">
              已經有帳戶了？{' '}
              <Link as={RouterLink} to="/login" color="brand.500" fontWeight="semibold">
                立即登入
              </Link>
            </Text>
          </Box>
        </Stack>
      </Box>
    </Container>
  );
};

export default RegisterPage; 