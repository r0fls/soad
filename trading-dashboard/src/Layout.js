import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

const Layout = () => {
  return (
    <>
      <Sidebar />
      <div className="container-fluid">
        <Outlet />
      </div>
    </>
  );
};

export default Layout;
