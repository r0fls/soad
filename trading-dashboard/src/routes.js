import { createBrowserRouter, redirect } from 'react-router-dom';
import Layout from './Layout';
import Dashboard from './Dashboard';
import AccountView from './AccountView';
import Positions from './Positions';
import Trades from './Trades';
import Insights from './Insights';
import Login from './Login';
import App from './App';

const checkAuth = async () => {
  const token = localStorage.getItem('token');
  if (!token) {
    return redirect('/login');
  }
  return null;
};

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        path: '/',
        element: <Layout />,
        children: [
          {
            path: '/',
            element: <Dashboard />,
            loader: checkAuth,
          },
          {
            path: '/accounts',
            element: <AccountView />,
            loader: checkAuth,
          },
          {
            path: '/positions',
            element: <Positions />,
            loader: checkAuth,
          },
          {
            path: '/trades',
            element: <Trades />,
            loader: checkAuth,
          },
          {
            path: '/insights',
            element: <Insights />,
            loader: checkAuth,
          },
        ],
      },
      {
        path: '/login',
        element: <Login />,
      },
    ],
  },
]);

export default router;
