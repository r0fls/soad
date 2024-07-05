import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import Select from 'react-select';
import { Spinner, Table, Card, Row, Col } from 'react-bootstrap';
import './Trades.css'; // Assuming you have a CSS file for custom styles

const Trades = () => {
  const [brokers, setBrokers] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [trades, setTrades] = useState([]);
  const [initialTrades, setInitialTrades] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const filterTrades = useCallback(() => {
    const filteredTrades = initialTrades.filter(trade =>
      (selectedBrokers.length === 0 || selectedBrokers.includes(trade.broker)) &&
      (selectedStrategies.length === 0 || selectedStrategies.includes(trade.strategy))
    );
    setTrades(filteredTrades);
  }, [initialTrades, selectedBrokers, selectedStrategies]);

  const calculateStats = useCallback((filteredTrades) => {
    const average_profit_loss = filteredTrades.reduce((acc, trade) => acc + trade.profit_loss, 0) / filteredTrades.length;
    const win_loss_rate = filteredTrades.filter(trade => trade.profit_loss > 0).length / filteredTrades.length;
    const number_of_trades = filteredTrades.length;
    const trades_per_day = filteredTrades.reduce((acc, trade) => {
      const day = new Date(trade.timestamp).toLocaleDateString();
      acc[day] = (acc[day] || 0) + 1;
      return acc;
    }, {});
    return { average_profit_loss, win_loss_rate, number_of_trades, trades_per_day };
  }, []);

  const fetchTrades = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/trades');
      setInitialTrades(response.data.trades);
      setTrades(response.data.trades);
      setStats(calculateStats(response.data.trades));
    } catch (error) {
      console.error('Error fetching trades:', error);
    } finally {
      setLoading(false);
    }
  }, [calculateStats]);

  const populateFilters = useCallback(async () => {
    try {
      const response = await axiosInstance.get('/trades');
      const brokersSet = new Set(response.data.trades.map(trade => trade.broker));
      const strategiesSet = new Set(response.data.trades.map(trade => trade.strategy));
      setBrokers([...brokersSet]);
      setStrategies([...strategiesSet]);
    } catch (error) {
      console.error('Error populating filters:', error);
    }
  }, []);

  useEffect(() => {
    populateFilters();
    fetchTrades();
  }, [populateFilters, fetchTrades]);

  useEffect(() => {
    filterTrades();
    setStats(calculateStats(trades));
  }, [selectedBrokers, selectedStrategies, filterTrades, calculateStats, trades]);

  return (
    <div className="container-fluid">
      <h1 className="mt-5">Trades</h1>
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
          {stats && (
            <Row className="mb-3">
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Average P/L</Card.Title>
                    <Card.Text>{stats.average_profit_loss.toFixed(2)}</Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Win/Loss Rate</Card.Title>
                    <Card.Text>{(stats.win_loss_rate * 100).toFixed(2)}%</Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Number of Trades</Card.Title>
                    <Card.Text>{stats.number_of_trades}</Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Trades per Day</Card.Title>
                    <Card.Text>{Object.keys(stats.trades_per_day).map(day => (
                      <div key={day}>{day}: {stats.trades_per_day[day]}</div>
                    ))}</Card.Text>
                  </Card.Body>
                </Card>
              </Col>
            </Row>
          )}
          <div className="table-responsive">
            <Table striped bordered hover className="trades-table">
              <thead>
                <tr>
                  <th>Broker</th>
                  <th>Strategy</th>
                  <th>Symbol</th>
                  <th>Quantity</th>
                  <th>Price</th>
                  <th>Type</th>
                  <th>Profit/Loss</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade, index) => (
                  <tr key={index}>
                    <td>{trade.broker}</td>
                    <td>{trade.strategy}</td>
                    <td>{trade.symbol}</td>
                    <td>{trade.quantity}</td>
                    <td>{trade.price}</td>
                    <td>{trade.order_type}</td>
                    <td>{trade.profit_loss}</td>
                    <td>{trade.timestamp}</td>
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

export default Trades;
