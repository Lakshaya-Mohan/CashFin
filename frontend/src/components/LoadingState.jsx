import React from 'react';

export const LoadingState = ({ message = 'Loading financial data...' }) => {
  return (
    <div className="loading-spinner">
      <div className="spinner"></div>
      <span>{message}</span>
    </div>
  );
};
