import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import Select from 'react-select';
import { Spinner, Table } from 'react-bootstrap';
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

  const filterPositions = useCallback(() => {
    const filteredPositions = initialPositions.filter(position =>
      (selectedBrokers.length === 0 || selectedBrokers.includes(position.broker)) &&
      (selectedStrategies.length === 0 || selectedStrategies.includes(position.strategy))
    );
    setPositions(filteredPositions);

    // Calculate the total delta and theta
    const totals = filteredPositions.reduce(
      (acc, position) => {
        acc.totalDelta += position.delta;
        acc.totalTheta += position.theta;
        return acc;
      },
      { totalDelta: 0, totalTheta: 0 }
    );
    setTotalDelta(totals.totalDelta);
    setTotalTheta(totals.totalTheta);
  }, [initialPositions, selectedBrokers, selectedStrategies]);

  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/positions');
      setInitialPositions(response.data.positions);
      setPositions(response.data.positions);

      // Calculate the total delta and theta
      const totals = response.data.positions.reduce(
        (acc, position) => {
          acc.totalDelta += position.delta;
          acc.totalTheta += position.theta;
          return acc;
        },
        { totalDelta: 0, totalTheta: 0 }
      );
      setTotalDelta(totals.totalDelta);
      setTotalTheta(totals.totalTheta);
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
          <div className="mb-3">
            <strong>Total Delta:</strong> {totalDelta.toFixed(2)} &nbsp; | &nbsp;
            <strong>Total Theta:</strong> {totalTheta.toFixed(2)}
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
