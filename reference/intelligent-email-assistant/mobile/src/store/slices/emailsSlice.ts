import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { EmailsState, EmailResponse, Email, AsyncThunkConfig } from '../../types';
import ApiService from '../../services/ApiService';

// Async thunks
export const fetchEmails = createAsyncThunk<
  EmailResponse,
  { page?: number; size?: number },
  AsyncThunkConfig
>('emails/fetchEmails', async ({ page = 0, size = 20 }, { rejectWithValue }) => {
  try {
    const response = await ApiService.getEmails(page, size);
    return response;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to fetch emails',
      status: error.status,
    });
  }
});

export const fetchEmailById = createAsyncThunk<
  Email,
  string,
  AsyncThunkConfig
>('emails/fetchEmailById', async (emailId, { rejectWithValue }) => {
  try {
    const email = await ApiService.getEmailById(emailId);
    return email;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to fetch email',
      status: error.status,
    });
  }
});

export const refreshEmails = createAsyncThunk<
  EmailResponse,
  void,
  AsyncThunkConfig
>('emails/refresh', async (_, { rejectWithValue }) => {
  try {
    const response = await ApiService.getEmails(0, 20);
    return response;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to refresh emails',
      status: error.status,
    });
  }
});

const initialState: EmailsState = {
  emails: [],
  selectedEmail: null,
  loading: false,
  refreshing: false,
  error: null,
  pagination: {
    currentPage: 0,
    totalPages: 0,
    totalElements: 0,
    hasMore: true,
  },
};

const emailsSlice = createSlice({
  name: 'emails',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    clearSelectedEmail: (state) => {
      state.selectedEmail = null;
    },
    resetPagination: (state) => {
      state.pagination = {
        currentPage: 0,
        totalPages: 0,
        totalElements: 0,
        hasMore: true,
      };
      state.emails = [];
    },
  },
  extraReducers: (builder) => {
    // Fetch emails (with pagination)
    builder
      .addCase(fetchEmails.pending, (state, action) => {
        const { page = 0 } = action.meta.arg;
        if (page === 0) {
          state.loading = true;
        }
        state.error = null;
      })
      .addCase(fetchEmails.fulfilled, (state, action) => {
        state.loading = false;
        const { content, totalPages, totalElements, first, last } = action.payload;
        const { page = 0 } = action.meta.arg;
        
        if (page === 0) {
          // First page - replace all emails
          state.emails = content;
        } else {
          // Subsequent pages - append emails
          state.emails = [...state.emails, ...content];
        }
        
        state.pagination = {
          currentPage: page,
          totalPages,
          totalElements,
          hasMore: !last,
        };
      })
      .addCase(fetchEmails.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload?.message || 'Unknown error';
      })
      // Fetch single email by ID
      .addCase(fetchEmailById.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchEmailById.fulfilled, (state, action) => {
        state.loading = false;
        state.selectedEmail = action.payload;
      })
      .addCase(fetchEmailById.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload?.message || 'Unknown error';
      })
      // Refresh emails
      .addCase(refreshEmails.pending, (state) => {
        state.refreshing = true;
        state.error = null;
      })
      .addCase(refreshEmails.fulfilled, (state, action) => {
        state.refreshing = false;
        const { content, totalPages, totalElements, last } = action.payload;
        state.emails = content;
        state.pagination = {
          currentPage: 0,
          totalPages,
          totalElements,
          hasMore: !last,
        };
      })
      .addCase(refreshEmails.rejected, (state, action) => {
        state.refreshing = false;
        state.error = action.payload?.message || 'Unknown error';
      });
  },
});

export const { clearError, clearSelectedEmail, resetPagination } = emailsSlice.actions;
export default emailsSlice.reducer;
