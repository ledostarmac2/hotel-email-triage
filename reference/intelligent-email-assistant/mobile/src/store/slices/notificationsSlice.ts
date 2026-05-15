import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { NotificationsState, Notification, AsyncThunkConfig } from '../../types';
import ApiService from '../../services/ApiService';

// Async thunks
export const fetchNotifications = createAsyncThunk<
  Notification[],
  void,
  AsyncThunkConfig
>('notifications/fetchNotifications', async (_, { rejectWithValue }) => {
  try {
    const notifications = await ApiService.getNotifications();
    return notifications;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to fetch notifications',
      status: error.status,
    });
  }
});

export const markAsRead = createAsyncThunk<
  string,
  string,
  AsyncThunkConfig
>('notifications/markAsRead', async (notificationId, { rejectWithValue }) => {
  try {
    await ApiService.markNotificationAsRead(notificationId);
    return notificationId;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to mark notification as read',
      status: error.status,
    });
  }
});

const initialState: NotificationsState = {
  notifications: [],
  loading: false,
  error: null,
  unreadCount: 0,
};

const notificationsSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    markAllAsRead: (state) => {
      state.notifications = state.notifications.map(notification => ({
        ...notification,
        read: true,
      }));
      state.unreadCount = 0;
    },
    removeNotification: (state, action) => {
      state.notifications = state.notifications.filter(
        notification => notification.id !== action.payload
      );
      // Recalculate unread count
      state.unreadCount = state.notifications.filter(n => !n.read).length;
    },
    addNotification: (state, action) => {
      state.notifications.unshift(action.payload);
      if (!action.payload.read) {
        state.unreadCount += 1;
      }
    },
  },
  extraReducers: (builder) => {
    // Fetch notifications
    builder
      .addCase(fetchNotifications.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchNotifications.fulfilled, (state, action) => {
        state.loading = false;
        state.notifications = action.payload;
        state.unreadCount = action.payload.filter(n => !n.read).length;
      })
      .addCase(fetchNotifications.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload?.message || 'Unknown error';
      })
      // Mark as read
      .addCase(markAsRead.pending, (state) => {
        state.error = null;
      })
      .addCase(markAsRead.fulfilled, (state, action) => {
        const notificationId = action.payload;
        const notification = state.notifications.find(n => n.id === notificationId);
        if (notification && !notification.read) {
          notification.read = true;
          state.unreadCount = Math.max(0, state.unreadCount - 1);
        }
      })
      .addCase(markAsRead.rejected, (state, action) => {
        state.error = action.payload?.message || 'Failed to mark as read';
      });
  },
});

export const { 
  clearError, 
  markAllAsRead, 
  removeNotification, 
  addNotification 
} = notificationsSlice.actions;

export default notificationsSlice.reducer;
