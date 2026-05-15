import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { SettingsState, UserSettings, AsyncThunkConfig } from '../../types';
import ApiService from '../../services/ApiService';

// Async thunks
export const fetchUserSettings = createAsyncThunk<
  UserSettings,
  void,
  AsyncThunkConfig
>('settings/fetchUserSettings', async (_, { rejectWithValue }) => {
  try {
    const settings = await ApiService.getUserSettings();
    return settings;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to fetch user settings',
      status: error.status,
    });
  }
});

export const updateSettings = createAsyncThunk<
  UserSettings,
  Partial<UserSettings>,
  AsyncThunkConfig
>('settings/updateSettings', async (settingsUpdate, { rejectWithValue }) => {
  try {
    const result = await ApiService.updateUserSettings(settingsUpdate);
    return result.data || result.settings || settingsUpdate as UserSettings;
  } catch (error: any) {
    return rejectWithValue({
      message: error.message || 'Failed to update settings',
      status: error.status,
    });
  }
});

const initialState: SettingsState = {
  settings: {
    pushNotifications: true,
    whatsappNotifications: false,
    autoResponses: true,
    processingSchedule: 'EVERY_5_MINUTES',
    aiProvider: 'DEEPSEEK_WITH_OPENAI_FALLBACK',
  },
  loading: false,
  saving: false,
  error: null,
};

const settingsSlice = createSlice({
  name: 'settings',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    updateLocalSetting: (state, action) => {
      const { key, value } = action.payload;
      state.settings = {
        ...state.settings,
        [key]: value,
      };
    },
    resetSettings: (state) => {
      state.settings = initialState.settings;
    },
  },
  extraReducers: (builder) => {
    // Fetch user settings
    builder
      .addCase(fetchUserSettings.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchUserSettings.fulfilled, (state, action) => {
        state.loading = false;
        state.settings = action.payload;
      })
      .addCase(fetchUserSettings.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload?.message || 'Unknown error';
      })
      // Update settings
      .addCase(updateSettings.pending, (state) => {
        state.saving = true;
        state.error = null;
      })
      .addCase(updateSettings.fulfilled, (state, action) => {
        state.saving = false;
        // Merge the updated settings with current state
        state.settings = {
          ...state.settings,
          ...action.payload,
        };
      })
      .addCase(updateSettings.rejected, (state, action) => {
        state.saving = false;
        state.error = action.payload?.message || 'Failed to save settings';
      });
  },
});

export const { 
  clearError, 
  updateLocalSetting, 
  resetSettings 
} = settingsSlice.actions;

export default settingsSlice.reducer;
