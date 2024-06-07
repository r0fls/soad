import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import Select from 'react-select';
import { Spinner, Table } from 'react-bootstrap';

const Positions = () => {
  const [brokers, setBrokers] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/positions', {
        params: { brokers: selectedBrokers, strategies: selectedStrategies }
      });
      setPositions(response.data.positions);
    } catch (error) {
      console.error('Error fetching positions:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedBrokers, selectedStrategies]);

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
    fetchPositions();
  }, [selectedBrokers, selectedStrategies, fetchPositions]);

  return (
    <div className="container-fluid">
      <h1 className="mt-5">Open Positions</h1>
      <div className="row mb-3">
        <div className="col">
          <Select
            isMulti
            options={brokers.map(broker => ({ value: broker, label: broker }))}
            onChange={selectedOptions => setSelectedBrokers(selectedOptions.map(option => option.value))}
            placeholder="Select Brokers"
            className="basic-multi-select"
            classNamePrefix="select"
          />
        </div>
        <div className="col">
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
        <Table striped bordered hover>
          <thead>
            <tr>
              <th>Broker</th>
              <th>Strategy</th>
              <th>Symbol</th>
              <th>Quantity</th>
              <th>Latest Price</th>
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
                <td>{position.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
};

export default Positions;
