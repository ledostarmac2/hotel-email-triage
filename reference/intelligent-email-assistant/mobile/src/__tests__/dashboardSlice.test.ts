import { configureStore } from '@reduxjs/toolkit';
import dashboardReducer, { 
  fetchDashboardStats, 
  triggerProcessing, 
  clearError 
} from '../store/slices/dashboardSlice';
import type { DashboardState } from '../types';

// Mock the API service
jest.mock('../services/ApiService', () => ({
  getDashboardStats: jest.fn(),
  triggerEmailProcessing: jest.fn(),
}));

import ApiService from '../services/ApiService';
const mockApiService = ApiService as jest.Mocked<typeof ApiService>;

describe('dashboardSlice', () => {
  let store: any;

  beforeEach(() => {
    store = configureStore({
      reducer: {
        dashboard: dashboardReducer,
      },
    });
    jest.clearAllMocks();
  });

  it('should return the initial state', () => {
    const initialState: DashboardState = {
      stats: {
        totalEmails: 0,
        urgentEmails: 0,
        autoResponses: 0,
        processedToday: 0,
      },
      loading: false,
      error: null,
      processingInProgress: false,
      lastProcessingResult: null,
    };

    expect(dashboardReducer(undefined, { type: 'unknown' })).toEqual(initialState);
  });

  describe('fetchDashboardStats', () => {
    it('should handle fetchDashboardStats.pending', () => {
      const action = { type: fetchDashboardStats.pending.type };
      const state = dashboardReducer(undefined, action);
      
      expect(state.loading).toBe(true);
      expect(state.error).toBe(null);
    });

    it('should handle fetchDashboardStats.fulfilled', async () => {
      const mockStats = {
        totalEmails: 100,
        urgentEmails: 5,
        autoResponses: 20,
        processedToday: 15,
      };

      mockApiService.getDashboardStats.mockResolvedValueOnce(mockStats);

      await store.dispatch(fetchDashboardStats());
      const state = store.getState().dashboard;

      expect(state.loading).toBe(false);
      expect(state.stats).toEqual(mockStats);
      expect(state.error).toBe(null);
    });

    it('should handle fetchDashboardStats.rejected', async () => {
      const errorMessage = 'Failed to fetch stats';
      mockApiService.getDashboardStats.mockRejectedValueOnce({
        message: errorMessage,
        status: 500,
      });

      await store.dispatch(fetchDashboardStats());
      const state = store.getState().dashboard;

      expect(state.loading).toBe(false);
      expect(state.error).toBe(errorMessage);
    });
  });

  describe('triggerProcessing', () => {
    it('should handle triggerProcessing.pending', () => {
      const action = { type: triggerProcessing.pending.type };
      const state = dashboardReducer(undefined, action);
      
      expect(state.processingInProgress).toBe(true);
      expect(state.error).toBe(null);
    });

    it('should handle triggerProcessing.fulfilled', async () => {
      const mockResult = {
        success: true,
        message: 'Processing started',
        processedCount: 5,
      };

      mockApiService.triggerEmailProcessing.mockResolvedValueOnce(mockResult);

      await store.dispatch(triggerProcessing());
      const state = store.getState().dashboard;

      expect(state.processingInProgress).toBe(false);
      expect(state.lastProcessingResult).toEqual(mockResult);
    });
  });

  describe('actions', () => {
    it('should handle clearError', () => {
      const initialState: DashboardState = {
        stats: {
          totalEmails: 0,
          urgentEmails: 0,
          autoResponses: 0,
          processedToday: 0,
        },
        loading: false,
        error: 'Some error',
        processingInProgress: false,
        lastProcessingResult: null,
      };

      const action = clearError();
      const state = dashboardReducer(initialState, action);

      expect(state.error).toBe(null);
    });
  });
});
