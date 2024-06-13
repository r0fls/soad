import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from "react-router-dom";
import router from './routes';
import './index.css';
import 'bootstrap/dist/css/bootstrap.min.css';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <div>
      <header className="App-banner">
        System Of A Dow
      </header>
      <RouterProvider router={router} />
    </div>
  </React.StrictMode>
);

reportWebVitals();
