import React from 'react';
import { Box, Flex } from '@chakra-ui/react';
import Header from './Header';

const Layout = ({ children }) => {
  return (
    <Flex direction="column" minH="100vh">
      <Header />
      <Box flex="1" p={6}>
        {children}
      </Box>
    </Flex>
  );
};

export default Layout; 