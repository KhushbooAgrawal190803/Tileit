import React from 'react';

const QuoteDisplay = ({ quotes }) => {
  if (!quotes || quotes.length === 0) {
    return (
      <div className="quote-display">
        <h3>No quotes generated yet</h3>
        <p>Upload CSV data and calculate quotes to see results here.</p>
      </div>
    );
  }

  return (
    <div className="quote-display">
      <h3>Generated Quotes ({quotes.length} total)</h3>
      <div className="quotes-grid">
        {quotes.map((quote, index) => (
          <div key={index} className="quote-card">
            <div className="quote-header">
              <h4>{quote.address}</h4>
              <span className="material-badge">{quote.roof_material}</span>
            </div>
            
            <div className="quote-details">
              <div className="detail-row">
                <span>Pitch:</span>
                <span>{quote.pitch}°</span>
              </div>
              <div className="detail-row">
                <span>Area:</span>
                <span>{quote.roof_area.toFixed(0)} sqft</span>
              </div>
              <div className="detail-row">
                <span>Crew Size:</span>
                <span>{quote.crew_size_used} workers</span>
              </div>
              <div className="detail-row">
                <span>Region Multiplier:</span>
                <span>{quote.region_multiplier}x</span>
              </div>
            </div>
            
            <div className="quote-range">
              <strong>{quote.estimated_quote_range}</strong>
            </div>
            
            <div className="cost-breakdown">
              <div className="breakdown-item">
                <span>Material:</span>
                <span>${quote.material_cost.toFixed(0)}</span>
              </div>
              <div className="breakdown-item">
                <span>Labor:</span>
                <span>${quote.labor_cost.toFixed(0)}</span>
              </div>
              <div className="breakdown-item">
                <span>Repair:</span>
                <span>${quote.repair_cost.toFixed(0)}</span>
              </div>
              <div className="breakdown-item total">
                <span>Total:</span>
                <span>${quote.total.toFixed(0)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default QuoteDisplay;
