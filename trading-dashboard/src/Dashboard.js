import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import { Spinner, Table } from 'react-bootstrap';
import Select from 'react-select';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import 'chartjs-adapter-moment';

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const Dashboard = () => {
  const [strategies, setStrategies] = useState([]);
  const [brokers, setBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [historicalValueData, setHistoricalValueData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchHistoricalValues = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/historic_balance_per_strategy', {
        params: { brokers: selectedBrokers, strategies: selectedStrategies }
      });
      setHistoricalValueData(processHistoricalValues(response.data));
    } catch (error) {
      console.error('Error fetching historical values:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedBrokers, selectedStrategies]);

  const processHistoricalValues = useCallback((data) => {
    let historicalData = {};

    data.historic_balance_per_strategy.forEach(item => {
      let key = `${item.strategy} (${item.broker})`;
      if (!historicalData[key]) {
        historicalData[key] = [];
      }
      historicalData[key].push({
        x: item.hour,
        y: item.balance
      });
    });

    let datasets = [];
    Object.keys(historicalData).forEach(key => {
      datasets.push({
        label: key,
        data: historicalData[key],
        fill: false,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      });
    });

    return {
      datasets
    };
  }, []);

  const populateFilters = useCallback(async () => {
    try {
      const response = await axiosInstance.get('/trades_per_strategy');
      const strategiesSet = new Set();
      const brokersSet = new Set();

      response.data.trades_per_strategy.forEach(item => {
        strategiesSet.add(item.strategy);
        brokersSet.add(item.broker);
      });

      setStrategies([...strategiesSet]);
      setBrokers([...brokersSet]);
    } catch (error) {
      console.error('Error populating filters:', error);
    }
  }, []);

  useEffect(() => {
    populateFilters();
    fetchHistoricalValues();
  }, [populateFilters, fetchHistoricalValues]);

  useEffect(() => {
    fetchHistoricalValues();
  }, [selectedStrategies, selectedBrokers, fetchHistoricalValues]);

  return (
    <div className="container-fluid">
      <div className="row mb-3">
        <div className="col-md-6">
          <Select
            isMulti
            options={strategies.map(strategy => ({ value: strategy, label: strategy }))}
            onChange={selectedOptions => setSelectedStrategies(selectedOptions.map(option => option.value))}
            placeholder="Select Strategies"
            className="basic-multi-select"
            classNamePrefix="select"
          />
        </div>
        <div className="col-md-6">
          <Select
            isMulti
            options={brokers.map(broker => ({ value: broker, label: broker }))}
            onChange={selectedOptions => setSelectedBrokers(selectedOptions.map(option => option.value))}
            placeholder="Select Brokers"
            className="basic-multi-select"
            classNamePrefix="select"
          />
        </div>
      </div>
      <div className="row">
        <div className="col-md-12">
          <div className="card">
            <div className="card-header">
              Historical Value per Strategy
            </div>
            <div className="card-body">
              {loading ? (
                <div className="text-center my-5">
                  <Spinner animation="border" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </Spinner>
                </div>
              ) : (
                historicalValueData && <Line data={historicalValueData} options={{ scales: { x: { type: 'time', time: { unit: 'hour' }}}}} />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
