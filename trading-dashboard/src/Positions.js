import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import Select from 'react-select';
import { Spinner, Table } from 'react-bootstrap';
import { Pie } from 'react-chartjs-2';
import './Positions.css'; // Assuming you have a CSS file for custom styles

const Positions = () => {
  const [brokers, setBrokers] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [positions, setPositions] = useState([]);
  const [initialPositions, setInitialPositions] = useState([]);
  const [totalDelta, setTotalDelta] = useState(0);
  const [totalTheta, setTotalTheta] = useState(0);
  const [loading, setLoading] = useState(true);
  const [totalStocksValue, setTotalStocksValue] = useState(0);
  const [totalOptionsValue, setTotalOptionsValue] = useState(0);
  const [totalCashValue, setTotalCashValue] = useState(0);
  const [initialCashBalances, setInitialCashBalances] = useState({});

  const filterPositions = useCallback(() => {
    const filteredPositions = initialPositions.filter(position =>
      (selectedBrokers.length === 0 || selectedBrokers.includes(position.broker)) &&
      (selectedStrategies.length === 0 || selectedStrategies.includes(position.strategy))
    );
    setPositions(filteredPositions);

    // Calculate the total delta, theta, and values
    const totals = filteredPositions.reduce(
      (acc, position) => {
        acc.totalDelta += position.delta;
        acc.totalTheta += position.theta;
        if (position.is_option) {
          acc.totalOptionsValue += position.quantity * position.latest_price;
        } else {
          acc.totalStocksValue += position.quantity * position.latest_price;
        }
        return acc;
      },
      { totalDelta: 0, totalTheta: 0, totalStocksValue: 0, totalOptionsValue: 0 }
    );
    setTotalDelta(totals.totalDelta);
    setTotalTheta(totals.totalTheta);
    setTotalStocksValue(totals.totalStocksValue);
    setTotalOptionsValue(totals.totalOptionsValue);

    // Calculate total cash value based on the filtered brokers and strategies
    const filteredCashValue = Object.keys(initialCashBalances).reduce((acc, key) => {
      const [broker, strategy] = key.split('_');
      if ((selectedBrokers.length === 0 || selectedBrokers.includes(broker)) &&
          (selectedStrategies.length === 0 || selectedStrategies.includes(strategy))) {
        acc += initialCashBalances[key];
      }
      return acc;
    }, 0);
    setTotalCashValue(filteredCashValue);
  }, [initialPositions, initialCashBalances, selectedBrokers, selectedStrategies]);

  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/positions');
      const { positions, total_delta, total_theta, total_stocks_value, total_options_value, cash_balances } = response.data;
      setInitialPositions(positions);
      setPositions(positions);
      setTotalDelta(total_delta);
      setTotalTheta(total_theta);
      setTotalStocksValue(total_stocks_value);
      setTotalOptionsValue(total_options_value);
      setInitialCashBalances(cash_balances);

      // Calculate initial total cash value
      const initialTotalCashValue = Object.values(cash_balances).reduce((acc, balance) => acc + balance, 0);
      setTotalCashValue(initialTotalCashValue);
    } catch (error) {
      console.error('Error fetching positions:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const populateFilters = useCallback(async () => {
    try {
      const response = await axiosInstance.get('/positions');
      const brokersSet = new Set(response.data.positions.map(position => position.broker));
      const strategiesSet = new Set(response.data.positions.map(position => position.strategy));
      setBrokers([...brokersSet]);
      setStrategies([...strategiesSet]);
    } catch (error) {
      console.error('Error populating filters:', error);
    }
  }, []);

  useEffect(() => {
    populateFilters();
    fetchPositions();
  }, [populateFilters, fetchPositions]);

  useEffect(() => {
    filterPositions();
  }, [selectedBrokers, selectedStrategies, filterPositions]);

  const data = {
    labels: ['Stocks', 'Options', 'Cash'],
    datasets: [
      {
        data: [totalStocksValue, totalOptionsValue, totalCashValue],
        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56'],
        hoverBackgroundColor: ['#FF6384', '#36A2EB', '#FFCE56']
      }
    ]
  };

  return (
    <div className="container-fluid">
      <h1 className="mt-5">Open Positions</h1>
      <div className="row mb-3">
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
      </div>
      {loading ? (
        <div className="text-center my-5">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading...</span>
          </Spinner>
        </div>
      ) : (
        <>
          <div className="info-box-container mb-3">
            <div className="info-box">
              <strong>Total Delta:</strong> {totalDelta.toFixed(2)}
            </div>
            <div className="info-box">
              <strong>Total Theta:</strong> {totalTheta.toFixed(2)}
            </div>
            <div className="pie-chart-container">
              <Pie data={data} />
            </div>
          </div>
          <div className="table-responsive">
            <Table striped bordered hover className="positions-table">
              <thead>
                <tr>
                  <th>Broker</th>
                  <th>Strategy</th>
                  <th>Symbol</th>
                  <th>Quantity</th>
                  <th>Latest Price</th>
                  <th>Cost Basis</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position, index) => (
                  <tr key={index}>
                    <td>{position.broker}</td>
                    <td>{position.strategy}</td>
                    <td>{position.symbol}</td>
                    <td>{position.quantity}</td>
                    <td>{position.latest_price}</td>
                    <td>{(position.cost_basis / position.quantity).toFixed(2)}</td>
                    <td>{position.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </>
      )}
    </div>
  );
};

export default Positions;
