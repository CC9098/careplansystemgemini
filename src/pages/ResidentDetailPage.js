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
  VStack,
  HStack,
  Badge,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  Textarea,
  useToast,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
} from '@chakra-ui/react';
import { ArrowBackIcon } from '@chakra-ui/icons';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/layout/Layout';
import { apiClient } from '../api/client';

const ResidentDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  
  const [resident, setResident] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [dailyLog, setDailyLog] = useState('');

  // 加載住民詳細資訊
  const fetchResident = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get(`/residents/${id}`);
      if (response.data.success) {
        setResident(response.data.data);
      } else {
        setError(response.data.error?.message || '無法載入住民資訊');
      }
    } catch (err) {
      setError('載入住民資訊時發生錯誤');
    } finally {
      setLoading(false);
    }
  };

  // AI 分析
  const handleAnalyze = async () => {
    if (!dailyLog.trim()) {
      toast({
        title: '請輸入日常記錄',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    try {
      setAnalyzing(true);
      const response = await apiClient.post('/analyze', {
        daily_log: dailyLog,
        current_plan: resident.current_care_plan,
        resident_info: {
          name: resident.name,
          age: resident.age,
          medical_conditions: resident.medical_conditions,
          medications: resident.medications,
        },
      });

      if (response.data.success) {
        toast({
          title: 'AI 分析完成',
          description: '已生成照護建議',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        // TODO: 顯示分析結果
        console.log('Analysis result:', response.data.data.analysis);
      } else {
        throw new Error(response.data.error?.message);
      }
    } catch (err) {
      toast({
        title: 'AI 分析失敗',
        description: err.message || '請稍後再試',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    fetchResident();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <Layout>
        <Center h="50vh">
          <Spinner size="xl" color="brand.500" />
        </Center>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <Container maxW="4xl">
          <Alert status="error">
            <AlertIcon />
            {error}
          </Alert>
        </Container>
      </Layout>
    );
  }

  return (
    <Layout>
      <Container maxW="6xl">
        <VStack spacing={6} align="stretch">
          {/* 頁面標題和導航 */}
          <HStack justify="space-between" align="center">
            <HStack>
              <Button
                variant="ghost"
                leftIcon={<ArrowBackIcon />}
                onClick={() => navigate('/dashboard')}
              >
                返回
              </Button>
              <Heading color="brand.500">{resident.name}</Heading>
              <Badge colorScheme={resident.current_care_plan ? 'green' : 'orange'}>
                {resident.current_care_plan ? '有照護計劃' : '待設定'}
              </Badge>
            </HStack>
          </HStack>

          {/* 住民基本資訊 */}
          <Grid templateColumns={{ base: '1fr', lg: '1fr 2fr' }} gap={6}>
            <GridItem>
              <Card>
                <CardBody>
                  <VStack spacing={3} align="stretch">
                    <Heading size="md" color="brand.500">基本資訊</Heading>
                    <Box>
                      <Text fontWeight="semibold">姓名:</Text>
                      <Text>{resident.name}</Text>
                    </Box>
                    <Box>
                      <Text fontWeight="semibold">年齡:</Text>
                      <Text>{resident.age || '未提供'}</Text>
                    </Box>
                    <Box>
                      <Text fontWeight="semibold">性別:</Text>
                      <Text>{resident.gender || '未提供'}</Text>
                    </Box>
                    <Box>
                      <Text fontWeight="semibold">房間號碼:</Text>
                      <Text>{resident.room_number || '未分配'}</Text>
                    </Box>
                    <Box>
                      <Text fontWeight="semibold">緊急聯絡人:</Text>
                      <Text>{resident.emergency_contact_name || '未提供'}</Text>
                      {resident.emergency_contact_phone && (
                        <Text fontSize="sm" color="gray.600">
                          {resident.emergency_contact_phone}
                        </Text>
                      )}
                    </Box>
                  </VStack>
                </CardBody>
              </Card>
            </GridItem>

            <GridItem>
              <Tabs colorScheme="brand">
                <TabList>
                  <Tab>AI 分析</Tab>
                  <Tab>照護計劃</Tab>
                  <Tab>醫療資訊</Tab>
                  <Tab>照護任務</Tab>
                </TabList>

                <TabPanels>
                  {/* AI 分析面板 */}
                  <TabPanel p={0} pt={4}>
                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          <Heading size="md" color="brand.500">AI 照護分析</Heading>
                          <Text color="gray.600">
                            輸入今日的照護記錄，AI 將分析並提供專業建議：
                          </Text>
                          <Textarea
                            value={dailyLog}
                            onChange={(e) => setDailyLog(e.target.value)}
                            placeholder="請輸入今日的照護記錄，包括住民的狀況、行為、飲食、睡眠等..."
                            rows={6}
                          />
                          <Button
                            colorScheme="brand"
                            onClick={handleAnalyze}
                            isLoading={analyzing}
                            loadingText="AI 分析中..."
                          >
                            開始 AI 分析
                          </Button>
                        </VStack>
                      </CardBody>
                    </Card>
                  </TabPanel>

                  {/* 照護計劃面板 */}
                  <TabPanel p={0} pt={4}>
                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          <Heading size="md" color="brand.500">當前照護計劃</Heading>
                          {resident.current_care_plan ? (
                            <Box
                              p={4}
                              bg="gray.50"
                              borderRadius="md"
                              whiteSpace="pre-wrap"
                            >
                              {resident.current_care_plan}
                            </Box>
                          ) : (
                            <Text color="gray.500" textAlign="center" py={8}>
                              尚未設定照護計劃
                            </Text>
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </TabPanel>

                  {/* 醫療資訊面板 */}
                  <TabPanel p={0} pt={4}>
                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          <Heading size="md" color="brand.500">醫療資訊</Heading>
                          <Box>
                            <Text fontWeight="semibold" mb={2}>醫療狀況:</Text>
                            <Text>{resident.medical_conditions || '無特殊醫療狀況'}</Text>
                          </Box>
                          <Box>
                            <Text fontWeight="semibold" mb={2}>目前用藥:</Text>
                            <Text>{resident.medications || '無用藥記錄'}</Text>
                          </Box>
                          <Box>
                            <Text fontWeight="semibold" mb={2}>照護備註:</Text>
                            <Text>{resident.care_notes || '無特殊備註'}</Text>
                          </Box>
                        </VStack>
                      </CardBody>
                    </Card>
                  </TabPanel>

                  {/* 照護任務面板 */}
                  <TabPanel p={0} pt={4}>
                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          <Heading size="md" color="brand.500">照護任務</Heading>
                          {resident.care_tasks && resident.care_tasks.length > 0 ? (
                            <VStack spacing={2} align="stretch">
                              {resident.care_tasks.map((task) => (
                                <Box
                                  key={task.id}
                                  p={3}
                                  bg="gray.50"
                                  borderRadius="md"
                                  borderLeft="4px solid"
                                  borderColor={
                                    task.status === 'completed' ? 'green.500' :
                                    task.priority === 'high' ? 'red.500' :
                                    task.priority === 'medium' ? 'yellow.500' : 'blue.500'
                                  }
                                >
                                  <HStack justify="space-between">
                                    <Text fontWeight="semibold">{task.title}</Text>
                                    <Badge
                                      colorScheme={
                                        task.status === 'completed' ? 'green' :
                                        task.status === 'in_progress' ? 'blue' : 'gray'
                                      }
                                    >
                                      {task.status}
                                    </Badge>
                                  </HStack>
                                  {task.description && (
                                    <Text fontSize="sm" color="gray.600">
                                      {task.description}
                                    </Text>
                                  )}
                                </Box>
                              ))}
                            </VStack>
                          ) : (
                            <Text color="gray.500" textAlign="center" py={8}>
                              尚無照護任務
                            </Text>
                          )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </GridItem>
          </Grid>
        </VStack>
      </Container>
    </Layout>
  );
};

export default ResidentDetailPage; 