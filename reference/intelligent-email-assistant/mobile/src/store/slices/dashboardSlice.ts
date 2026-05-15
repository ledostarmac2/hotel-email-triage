import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { DashboardState, DashboardStats, ProcessingResult, AsyncThunkConfig } from '../../types';
import ApiService from '../../services/ApiService';

// Async thunks
export const fetchDashboardStats = createAsyncThunk<
  DashboardStats,
  void,
  AsyncThunkConfig
>('dashboard/fetchStats', async (_, { rejectWithValue }) => {
  try {
    const stats = await ApiService.getDashboardStats();
    return stats;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to fetch dashboard stats',
      status: error.status,
    });
  }
});

export const triggerProcessing = createAsyncThunk<
  ProcessingResult,
  void,
  AsyncThunkConfig
>('dashboard/triggerProcessing', async (_, { rejectWithValue }) => {
  try {
    const result = await ApiService.triggerEmailProcessing();
    return result;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to trigger email processing',
      status: error.status,
    });
  }
});

const initialState: DashboardState = {
  stats: {
    totalEmails: 0,
    urgentEmails: 0,
    autoResponses: 0,
    processedToday: 0,
  },
  loading: false,
  error: null,
  lastProcessingResult: null,
  processingInProgress: false,
};

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    clearProcessingResult: (state) => {
      state.lastProcessingResult = null;
    },
  },
  extraReducers: (builder) => {
    // Fetch stats
    builder
      .addCase(fetchDashboardStats.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchDashboardStats.fulfilled, (state, action) => {
        state.loading = false;
        state.stats = action.payload;
      })
      .addCase(fetchDashboardStats.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload?.message || 'Unknown error';
      })
      // Trigger processing
      .addCase(triggerProcessing.pending, (state) => {
        state.processingInProgress = true;
        state.error = null;
      })
      .addCase(triggerProcessing.fulfilled, (state, action) => {
        state.processingInProgress = false;
        state.lastProcessingResult = action.payload;
        // Optimistically update processed count
        if (action.payload.processedCount) {
          state.stats.processedToday += action.payload.processedCount;
        }
      })
      .addCase(triggerProcessing.rejected, (state, action) => {
        state.processingInProgress = false;
        state.error = action.payload?.message || 'Processing failed';
      });
  },
});

export const { clearError, clearProcessingResult } = dashboardSlice.actions;
export default dashboardSlice.reducer;
