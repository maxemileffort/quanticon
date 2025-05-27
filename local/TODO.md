# Quanticon TODO List

## High Priority

### Data and Model Persistence
- [ ] Add simulation results storage
- [ ] Add model storage

### Core Functionality
- [x] Add technical indicator calculations (using finta in local version) - Core logic moved to ml_core and debugged.
- [ ] Implement Monte Carlo simulation engine
- [ ] Create strategy evaluation system
- [ ] Set up background job processing
- [ ] Define and manage technical indicator parameter ranges
- [ ] Refine randomization strategy for indicators and parameters
- [x] Define simplified backtesting assumptions (slippage, commissions, position sizing, exit conditions) - Incorporated into ml_core backtesting.
- [ ] Evaluate technical analysis libraries for main web app (e.g., finta, TA-Lib, custom)
- [ ] Explore and implement hyperparameter optimization techniques for feature and model tuning
- [x] Implement Machine Learning Pipeline in local simulator (Data Prep, XGBoost Training, Backtesting, Visualization)

## Medium Priority

### User Experience
- [ ] Add loading states for simulations
- [ ] Implement error handling
- [ ] Add form validation
- [ ] Create success/error notifications
- [ ] Provide simulation progress feedback and time estimation

### Features
- [ ] Add strategy comparison tool
- [ ] Implement CSV export
- [ ] Create strategy replay system
- [ ] Add performance analytics dashboard

## Low Priority

### Optimization
- [ ] Implement caching
- [ ] Add performance monitoring

### Additional Features
- [ ] Create public leaderboard
- [ ] Add API documentation

### Testing
- [ ] Add unit tests
- [ ] Implement integration tests
- [ ] Create end-to-end tests
- [ ] Add performance tests

## Future Considerations

### Scalability
- [ ] Set up load balancing
- [ ] Implement horizontal scaling
- [ ] Add Redis caching
- [ ] Optimize compute resources

### Features
- [ ] Implement real-time data
- [ ] Create mobile app
- [ ] Add advanced analytics

### Integration
- [ ] Add more data providers
- [ ] Implement broker integration
- [ ] Add news feed
- [ ] Create API endpoints
