import React, { useState } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  VStack,
  HStack,
  Select,
  useToast,
  Alert,
  AlertIcon,
} from '@chakra-ui/react';
import { apiClient } from '../api/client';

const AddResidentModal = ({ isOpen, onClose, onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const toast = useToast();

  const [formData, setFormData] = useState({
    name: '',
    age: '',
    gender: '',
    room_number: '',
    contact_info: '',
    emergency_contact: '',
    medical_conditions: '',
    medications: '',
    care_notes: '',
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // 基本驗證
    if (!formData.name.trim()) {
      setError('請輸入住民姓名');
      return;
    }

    try {
      setLoading(true);
      setError('');
      
      const response = await apiClient.post('/residents', formData);
      
      if (response.data.success) {
        toast({
          title: '新增成功',
          description: `已成功新增住民：${formData.name}`,
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        
        // 重置表單
        setFormData({
          name: '',
          age: '',
          gender: '',
          room_number: '',
          contact_info: '',
          emergency_contact: '',
          medical_conditions: '',
          medications: '',
          care_notes: '',
        });
        
        // 通知父組件刷新列表
        if (onSuccess) {
          onSuccess(response.data.data);
        }
        
        onClose();
      } else {
        setError(response.data.error?.message || '新增住民失敗');
      }
    } catch (err) {
      console.error('Add resident error:', err);
      setError(err.response?.data?.error?.message || '新增住民時發生錯誤');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setError('');
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <form onSubmit={handleSubmit}>
          <ModalHeader>新增住民</ModalHeader>
          <ModalCloseButton />
          
          <ModalBody>
            <VStack spacing={4}>
              {error && (
                <Alert status="error">
                  <AlertIcon />
                  {error}
                </Alert>
              )}

              <HStack spacing={4} w="full">
                <FormControl isRequired>
                  <FormLabel>姓名</FormLabel>
                  <Input
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    placeholder="請輸入住民姓名"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>年齡</FormLabel>
                  <Input
                    name="age"
                    type="number"
                    value={formData.age}
                    onChange={handleInputChange}
                    placeholder="年齡"
                  />
                </FormControl>
              </HStack>

              <HStack spacing={4} w="full">
                <FormControl>
                  <FormLabel>性別</FormLabel>
                  <Select
                    name="gender"
                    value={formData.gender}
                    onChange={handleInputChange}
                    placeholder="請選擇性別"
                  >
                    <option value="male">男性</option>
                    <option value="female">女性</option>
                    <option value="other">其他</option>
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>房間號碼</FormLabel>
                  <Input
                    name="room_number"
                    value={formData.room_number}
                    onChange={handleInputChange}
                    placeholder="房間號碼"
                  />
                </FormControl>
              </HStack>

              <FormControl>
                <FormLabel>聯絡資訊</FormLabel>
                <Input
                  name="contact_info"
                  value={formData.contact_info}
                  onChange={handleInputChange}
                  placeholder="電話號碼或其他聯絡方式"
                />
              </FormControl>

              <FormControl>
                <FormLabel>緊急聯絡人</FormLabel>
                <Input
                  name="emergency_contact"
                  value={formData.emergency_contact}
                  onChange={handleInputChange}
                  placeholder="緊急聯絡人姓名及電話"
                />
              </FormControl>

              <FormControl>
                <FormLabel>醫療狀況</FormLabel>
                <Textarea
                  name="medical_conditions"
                  value={formData.medical_conditions}
                  onChange={handleInputChange}
                  placeholder="請描述住民的醫療狀況、疾病史等"
                  rows={3}
                />
              </FormControl>

              <FormControl>
                <FormLabel>用藥情況</FormLabel>
                <Textarea
                  name="medications"
                  value={formData.medications}
                  onChange={handleInputChange}
                  placeholder="目前用藥情況、藥物名稱、劑量等"
                  rows={3}
                />
              </FormControl>

              <FormControl>
                <FormLabel>照護備註</FormLabel>
                <Textarea
                  name="care_notes"
                  value={formData.care_notes}
                  onChange={handleInputChange}
                  placeholder="其他需要注意的照護事項"
                  rows={3}
                />
              </FormControl>
            </VStack>
          </ModalBody>

          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={handleClose} disabled={loading}>
              取消
            </Button>
            <Button
              type="submit"
              colorScheme="brand"
              isLoading={loading}
              loadingText="新增中..."
            >
              新增住民
            </Button>
          </ModalFooter>
        </form>
      </ModalContent>
    </Modal>
  );
};

export default AddResidentModal; 