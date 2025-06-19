import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Heading,
  Button,
  Grid,
  GridItem,
  Card,
  CardBody,
  Text,
  Stat,
  StatLabel,
  StatNumber,
  HStack,
  VStack,
  Badge,
  Avatar,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  useDisclosure,
} from '@chakra-ui/react';
import { AddIcon } from '@chakra-ui/icons';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import { apiClient } from '../api/client';
import AddResidentModal from '../components/AddResidentModal';

const DashboardPage = () => {
  const [residents, setResidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { isOpen, onOpen, onClose } = useDisclosure();

  // 加載住民列表
  const fetchResidents = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/residents');
      if (response.data.success) {
        setResidents(response.data.data);
      } else {
        setError(response.data.error?.message || '無法載入住民列表');
      }
    } catch (err) {
      setError('載入住民列表時發生錯誤');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResidents();
  }, []);

  const handleAddResident = () => {
    onOpen();
  };

  const handleResidentAdded = (newResident) => {
    // 將新住民添加到列表中
    setResidents(prev => [...prev, newResident]);
  };

  const handleResidentClick = (residentId) => {
    navigate(`/residents/${residentId}`);
  };

  if (loading) {
    return (
      <Layout>
        <Center h="50vh">
          <Spinner size="xl" color="brand.500" />
        </Center>
      </Layout>
    );
  }

  return (
    <Layout>
      <Container maxW="7xl">
        <VStack spacing={6} align="stretch">
          {/* 頁面標題和操作 */}
          <HStack justify="space-between" align="center">
            <Heading color="brand.500">住民管理儀表板</Heading>
            <Button
              leftIcon={<AddIcon />}
              colorScheme="brand"
              onClick={handleAddResident}
            >
              新增住民
            </Button>
          </HStack>

          {/* 統計資訊 */}
          <Grid templateColumns={{ base: '1fr', md: 'repeat(3, 1fr)' }} gap={6}>
            <GridItem>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>總住民數</StatLabel>
                    <StatNumber color="brand.500">{residents.length}</StatNumber>
                  </Stat>
                </CardBody>
              </Card>
            </GridItem>
            <GridItem>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>本月 AI 分析</StatLabel>
                    <StatNumber color="green.500">
                      {residents.filter(r => r.current_care_plan).length}
                    </StatNumber>
                  </Stat>
                </CardBody>
              </Card>
            </GridItem>
            <GridItem>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>需要關注</StatLabel>
                    <StatNumber color="orange.500">
                      {residents.filter(r => !r.current_care_plan).length}
                    </StatNumber>
                  </Stat>
                </CardBody>
              </Card>
            </GridItem>
          </Grid>

          {error && (
            <Alert status="error">
              <AlertIcon />
              {error}
            </Alert>
          )}

          {/* 住民列表 */}
          <Box>
            <Heading size="md" mb={4}>住民列表</Heading>
            {residents.length === 0 ? (
              <Card>
                <CardBody textAlign="center" py={12}>
                  <Text color="gray.500" mb={4}>
                    您還沒有添加任何住民
                  </Text>
                  <Button
                    leftIcon={<AddIcon />}
                    colorScheme="brand"
                    onClick={handleAddResident}
                  >
                    新增第一位住民
                  </Button>
                </CardBody>
              </Card>
            ) : (
              <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' }} gap={6}>
                {residents.map((resident) => (
                  <GridItem key={resident.id}>
                    <Card
                      cursor="pointer"
                      _hover={{ transform: 'translateY(-2px)', boxShadow: 'lg' }}
                      transition="all 0.2s"
                      onClick={() => handleResidentClick(resident.id)}
                    >
                      <CardBody>
                        <VStack spacing={3} align="stretch">
                          <HStack>
                            <Avatar
                              name={resident.name}
                              size="md"
                              bg="brand.100"
                              color="brand.500"
                            />
                            <Box flex="1">
                              <Text fontWeight="bold" fontSize="lg">
                                {resident.name}
                              </Text>
                              <Text color="gray.600" fontSize="sm">
                                房間 {resident.room_number || '未分配'}
                              </Text>
                            </Box>
                          </HStack>

                          <HStack justify="space-between">
                            <Text fontSize="sm" color="gray.600">
                              年齡: {resident.age || '未提供'}
                            </Text>
                            <Badge
                              colorScheme={resident.current_care_plan ? 'green' : 'orange'}
                              variant="subtle"
                            >
                              {resident.current_care_plan ? '有照護計劃' : '待設定'}
                            </Badge>
                          </HStack>

                          {resident.medical_conditions && (
                            <Text fontSize="sm" color="gray.600" noOfLines={2}>
                              醫療狀況: {resident.medical_conditions}
                            </Text>
                          )}

                          <Text fontSize="xs" color="gray.500">
                            最後更新: {new Date(resident.updated_at).toLocaleDateString('zh-TW')}
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  </GridItem>
                ))}
              </Grid>
            )}
          </Box>
        </VStack>
      </Container>

      {/* 新增住民模態對話框 */}
      <AddResidentModal 
        isOpen={isOpen} 
        onClose={onClose} 
        onSuccess={handleResidentAdded}
      />
    </Layout>
  );
};

export default DashboardPage; 