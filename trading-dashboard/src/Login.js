import React, { useState } from 'react';
import axiosInstance from './axiosInstance';
import { useNavigate, useOutletContext } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import loginImage from './assets/login-image.png';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { setToken } = useOutletContext();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); // Reset error state on form submission
    console.log('Form submitted with:', { username, password }); // Debug log
    try {
      const response = await axiosInstance.post('/login', { username, password });
      console.log('Login response:', response); // Debug log to verify response
      if (response.status === 200 && response.data.access_token) {
        setToken(response.data.access_token);
        console.log('Token set, navigating to /'); // Debug log for navigation
        setTimeout(navigate, 0, "/");
      } else {
        setError('Invalid username or password');
      }
    } catch (err) {
      console.error('Login error:', err); // Debug log for errors
      setError('Invalid username or password');
    }
  };

  return (
    <div className="container mt-5">
      <div className="row justify-content-center">
        <div className="col-md-6">
          <h2 className="text-center mb-4">Login</h2>
          {error && <p className="text-danger">{error}</p>}
          <form onSubmit={handleSubmit}>
            <div className="form-group mb-3">
              <label>Username</label>
              <input
                type="text"
                className="form-control"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  if (error) setError(''); // Reset error when user starts typing
                }}
                required
              />
            </div>
            <div className="form-group mb-3">
              <label>Password</label>
              <input
                type="password"
                className="form-control"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError(''); // Reset error when user starts typing
                }}
                required
              />
            </div>
            <button type="submit" className="btn btn-primary btn-block">Login</button>
          </form>
        </div>
      </div>
      <div className="row justify-content-center mt-5">
        <div className="col-md-6">
          <img src={loginImage} alt="Login" className="img-fluid" />
        </div>
      </div>
    </div>
  );
};

export default Login;
