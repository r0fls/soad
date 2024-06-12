import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FaBars } from 'react-icons/fa';
import { AiFillCloseCircle } from 'react-icons/ai';
import './Sidebar.css';
import 'bootstrap/dist/css/bootstrap.min.css';

const Sidebar = () => {
  const [sidebar, setSidebar] = useState(false);

  const showSidebar = () => setSidebar(!sidebar);

  return (
    <>
      <div className="navbar">
        <Link to="#" className="menu-bars">
          <FaBars onClick={showSidebar} />
        </Link>
      </div>
      <nav className={sidebar ? 'nav-menu active' : 'nav-menu'}>
        <ul className="nav-menu-items">
          <li className="navbar-toggle">
            <Link to="#" className="menu-bars">
              <AiFillCloseCircle onClick={showSidebar} />
            </Link>
          </li>
          <li className="nav-text">
            <Link to="/">
              <span>Dashboard</span>
            </Link>
          </li>
          <li className="nav-text">
            <Link to="/accounts">
              <span>Account View</span>
            </Link>
          </li>
          <li className="nav-text">
            <Link to="/positions">
              <span>Positions</span>
            </Link>
          </li>
          <li className="nav-text">
            <Link to="/trades">
              <span>Trades</span>
            </Link>
          </li>
          <li className="nav-text">
            <Link to="/insights">
              <span>Insights</span>
            </Link>
          </li>
        </ul>
      </nav>
    </>
  );
};

export default Sidebar;
