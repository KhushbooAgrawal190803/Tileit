import React, { useState } from 'react';

const RooferOnboarding = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    // Business Information
    business_name: '',
    license_id: '',
    primary_zip_code: '',
    email: '',
    
    // Labor Information
    labor_rate: 45,
    daily_productivity: 2500,
    base_crew_size: 3,
    crew_scaling_rule: 'size_and_complexity',
    
    // Slope Adjustments
    slope_cost_adjustment: {
      flat_low: 0.0,
      moderate: 0.1,
      steep: 0.2,
      very_steep: 0.3
    },
    
    // Material Costs
    material_costs: {
      asphalt: 4.0,
      shingle: 4.5,
      metal: 7.0,
      tile: 8.0,
      concrete: 6.0
    },
    
    // Replacement Costs
    replacement_costs: {
      asphalt: 45,
      shingle: 50,
      metal: 90,
      tile: 70,
      concrete: 60
    },
    
    // Business Margins
    overhead_percent: 0.1,
    profit_margin: 0.2
  });

  const handleInputChange = (field, value) => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      setFormData(prev => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [child]: parseFloat(value) || 0
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [field]: value
      }));
    }
  };

  const nextStep = () => setStep(step + 1);
  const prevStep = () => setStep(step - 1);

  const handleSubmit = () => {
    onComplete(formData);
  };

  return (
    <div className="roofer-onboarding">
      <div className="onboarding-header">
        <h2>Roofer Business Setup</h2>
        <div className="progress-bar">
          <div className="progress" style={{ width: `${(step / 4) * 100}%` }}></div>
        </div>
        <p>Step {step} of 4</p>
      </div>

      {step === 1 && (
        <div className="onboarding-step">
          <h3>Business Information</h3>
          <div className="form-group">
            <label>Business Name</label>
            <input
              type="text"
              value={formData.business_name}
              onChange={(e) => handleInputChange('business_name', e.target.value)}
              placeholder="Your Roofing Company"
            />
          </div>
          <div className="form-group">
            <label>License ID</label>
            <input
              type="text"
              value={formData.license_id}
              onChange={(e) => handleInputChange('license_id', e.target.value)}
              placeholder="LIC123456"
            />
          </div>
          <div className="form-group">
            <label>Primary Service ZIP Code</label>
            <input
              type="text"
              value={formData.primary_zip_code}
              onChange={(e) => handleInputChange('primary_zip_code', e.target.value)}
              placeholder="11221"
            />
          </div>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              placeholder="contact@yourcompany.com"
            />
          </div>
          <button onClick={nextStep} className="btn-primary">Next</button>
        </div>
      )}

      {step === 2 && (
        <div className="onboarding-step">
          <h3>Labor Information</h3>
          <div className="form-group">
            <label>Labor Rate ($/hour per worker)</label>
            <input
              type="number"
              value={formData.labor_rate}
              onChange={(e) => handleInputChange('labor_rate', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Daily Productivity (sqft/day per crew)</label>
            <input
              type="number"
              value={formData.daily_productivity}
              onChange={(e) => handleInputChange('daily_productivity', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Base Crew Size</label>
            <input
              type="number"
              value={formData.base_crew_size}
              onChange={(e) => handleInputChange('base_crew_size', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Crew Scaling Rule</label>
            <select
              value={formData.crew_scaling_rule}
              onChange={(e) => handleInputChange('crew_scaling_rule', e.target.value)}
            >
              <option value="size_only">Size Only</option>
              <option value="size_and_complexity">Size and Complexity</option>
            </select>
          </div>
          <div className="button-group">
            <button onClick={prevStep} className="btn-secondary">Back</button>
            <button onClick={nextStep} className="btn-primary">Next</button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="onboarding-step">
          <h3>Slope Adjustments</h3>
          <p>What additional percentage do you charge for different roof slopes?</p>
          <div className="form-group">
            <label>Flat/Low (0-15°)</label>
            <input
              type="number"
              step="0.1"
              value={formData.slope_cost_adjustment.flat_low}
              onChange={(e) => handleInputChange('slope_cost_adjustment.flat_low', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Moderate (15-30°)</label>
            <input
              type="number"
              step="0.1"
              value={formData.slope_cost_adjustment.moderate}
              onChange={(e) => handleInputChange('slope_cost_adjustment.moderate', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Steep (30-45°)</label>
            <input
              type="number"
              step="0.1"
              value={formData.slope_cost_adjustment.steep}
              onChange={(e) => handleInputChange('slope_cost_adjustment.steep', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Very Steep (>45°)</label>
            <input
              type="number"
              step="0.1"
              value={formData.slope_cost_adjustment.very_steep}
              onChange={(e) => handleInputChange('slope_cost_adjustment.very_steep', e.target.value)}
            />
          </div>
          <div className="button-group">
            <button onClick={prevStep} className="btn-secondary">Back</button>
            <button onClick={nextStep} className="btn-primary">Next</button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="onboarding-step">
          <h3>Business Margins</h3>
          <div className="form-group">
            <label>Overhead Percentage</label>
            <input
              type="number"
              step="0.01"
              value={formData.overhead_percent}
              onChange={(e) => handleInputChange('overhead_percent', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Profit Margin</label>
            <input
              type="number"
              step="0.01"
              value={formData.profit_margin}
              onChange={(e) => handleInputChange('profit_margin', e.target.value)}
            />
          </div>
          <div className="button-group">
            <button onClick={prevStep} className="btn-secondary">Back</button>
            <button onClick={handleSubmit} className="btn-primary">Complete Setup</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RooferOnboarding;
