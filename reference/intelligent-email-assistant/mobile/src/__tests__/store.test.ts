import { store } from '../store';
import { fetchDashboardStats } from '../store/slices/dashboardSlice';

describe('Redux Store', () => {
  it('should have initial state', () => {
    const state = store.getState();
    expect(state).toHaveProperty('dashboard');
    expect(state).toHaveProperty('emails');
    expect(state).toHaveProperty('notifications');
    expect(state).toHaveProperty('settings');
  });

  it('should handle dashboard actions', () => {
    const initialState = store.getState().dashboard;
    expect(initialState.loading).toBe(false);
    expect(initialState.error).toBe(null);
  });
});
