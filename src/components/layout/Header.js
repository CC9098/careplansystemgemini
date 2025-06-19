import React from 'react';
import {
  Box,
  Flex,
  Text,
  Button,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Avatar,
  HStack,
  useColorModeValue,
  Badge,
} from '@chakra-ui/react';
import { ChevronDownIcon } from '@chakra-ui/icons';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const Header = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const bg = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <Box bg={bg} px={4} borderBottom="1px" borderColor={borderColor}>
      <Flex h={16} alignItems="center" justifyContent="space-between">
        {/* Logo 和標題 */}
        <HStack spacing={4}>
          <Text
            fontSize="xl"
            fontWeight="bold"
            color="brand.500"
            cursor="pointer"
            onClick={() => navigate('/dashboard')}
          >
            AI Care Plan 管理系統
          </Text>
          {user?.is_premium && (
            <Badge colorScheme="yellow" variant="solid">
              Premium
            </Badge>
          )}
        </HStack>

        {/* 用戶菜單 */}
        <Menu>
          <MenuButton as={Button} rightIcon={<ChevronDownIcon />} variant="ghost">
            <HStack spacing={2}>
              <Avatar size="sm" name={user?.name || user?.email} src={user?.profile_picture} />
              <Text fontSize="sm">{user?.name || user?.email}</Text>
            </HStack>
          </MenuButton>
          <MenuList>
            <MenuItem onClick={() => navigate('/dashboard')}>
              儀表板
            </MenuItem>
            <MenuItem>
              帳戶設定
            </MenuItem>
            {!user?.is_premium && (
              <MenuItem>
                <Text color="brand.500" fontWeight="semibold">
                  升級到 Premium
                </Text>
              </MenuItem>
            )}
            <MenuItem onClick={handleLogout} color="red.500">
              登出
            </MenuItem>
          </MenuList>
        </Menu>
      </Flex>
      
      {/* 使用量提示 */}
      {!user?.is_premium && (
        <Box pb={2}>
          <Text fontSize="xs" color="gray.600" textAlign="center">
            本月剩餘 AI 分析次數: {user?.remaining_usage || 0} 次
          </Text>
        </Box>
      )}
    </Box>
  );
};

export default Header; 