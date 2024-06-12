import React, { useState } from 'react';
import axiosInstance from './axiosInstance';
import { useNavigate, useOutletContext } from 'react-router-dom';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { setToken } = useOutletContext();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axiosInstance.post('/login', { username, password });
      console.log('Login response:', response); // Debug log to verify response
      if (response.status === 200 && response.data.access_token) {
        setToken(response.data.access_token);
        navigate('/');
      } else {
        setError('Invalid username or password');
      }
    } catch (err) {
      console.error('Login error:', err); // Debug log for errors
      setError('Invalid username or password');
    }
  };

  return (
    <div>
      <h2>Login</h2>
      {error && <p>{error}</p>}
      <form onSubmit={handleSubmit}>
        <div>
          <label>Username</label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div>
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button type="submit">Login</button>
      </form>
    </div>
  );
};

export default Login;
