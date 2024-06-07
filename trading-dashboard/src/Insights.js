import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import { Spinner, Card, Row, Col } from 'react-bootstrap';

const Insights = () => {
  const [metrics, setMetrics] = useState({
    var: 0,
    max_drawdown: 0,
    sharpe_ratio: 0,
  });
  const [loading, setLoading] = useState(true);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    try {
      const [varResponse, drawdownResponse, sharpeResponse] = await Promise.all([
        axiosInstance.get('/var'),
        axiosInstance.get('/max_drawdown'),
        axiosInstance.get('/sharpe_ratio'),
      ]);

      setMetrics({
        var: varResponse.data.var !== undefined ? varResponse.data.var : 0,
        max_drawdown: drawdownResponse.data.max_drawdown !== undefined ? drawdownResponse.data.max_drawdown : 0,
        sharpe_ratio: sharpeResponse.data.sharpe_ratio !== undefined ? sharpeResponse.data.sharpe_ratio : 0,
      });
    } catch (error) {
      console.error('Eror fetching metrics:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return (
    <div className="container-fluid">
      <h1 className="mt-5">Insights</h1>
      {loading ? (
        <div className="text-center my-5">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading...</span>
          </Spinner>
        </div>
      ) : (
        <>
          <Row className="mb-3">
            <Col md={4}>
              <Card>
                <Card.Body>
                  <Card.Title>Value At Risk (VaR)</Card.Title>
                  <Card.Text>{metrics.var.toFixed(2)}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
            <Col md={4}>
              <Card>
                <Card.Body>
                  <Card.Title>Max Drawdown</Card.Title>
                  <Card.Text>{metrics.max_drawdown.toFixed(2)}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
            <Col md={4}>
              <Card>
                <Card.Body>
                  <Card.Title>Sharpe Ratio</Card.Title>
                  <Card.Text>{metrics.sharpe_ratio.toFixed(2)}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
          </Row>
          {/* Add more metrics and charts as needed */}
        </>
      )}
    </div>
  );
};

export default Insights;
